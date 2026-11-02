"""Persistent reservations. One central gateway host; SQLite is not a multi-host database."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from uuid import uuid4


class AdmissionDenied(Exception):
    pass


@dataclass(frozen=True)
class Reservation:
    id: str
    principal: str
    network: str
    room: str
    identity: str
    deadline: int
    state: str
    issued: int
    attempts: int
    retry_at: int


class QuotaStore:
    def __init__(self, database, limits):
        self.database, self.limits = database, limits
        if not database.is_absolute() or database.name == ":memory:":
            raise ValueError("Persistent absolute SQLite path required")
        database.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        new_database = not database.exists()
        with self.connection() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                  id TEXT PRIMARY KEY, principal TEXT NOT NULL, network TEXT NOT NULL,
                  room TEXT UNIQUE NOT NULL, identity TEXT NOT NULL, deadline INTEGER NOT NULL,
                  state TEXT NOT NULL, issued INTEGER NOT NULL DEFAULT 0,
                  attempts INTEGER NOT NULL DEFAULT 0, retry_at INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS usage (
                  day INTEGER NOT NULL, scope TEXT NOT NULL, sessions INTEGER NOT NULL,
                  seconds INTEGER NOT NULL, PRIMARY KEY(day,scope));
                CREATE TABLE IF NOT EXISTS rates (
                  minute INTEGER NOT NULL, scope TEXT NOT NULL, count INTEGER NOT NULL,
                  PRIMARY KEY(minute,scope));
                CREATE INDEX IF NOT EXISTS sessions_deadline ON sessions(state,deadline,retry_at);
            """)
        if new_database:
            database.chmod(0o600)

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(self.database, timeout=5, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA synchronous=FULL")
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def transaction(self):
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    def reserve(self, principal, network, now):
        limits = self.limits
        scopes = (
            ("global", "global"),
            (f"p:{principal}", "principal"),
            (f"n:{network}", "network"),
        )
        denied = False
        with self.transaction() as db:
            db.execute("DELETE FROM rates WHERE minute < ?", (now // 60 - 2,))
            db.execute("DELETE FROM usage WHERE day < ?", (now // 86400 - 7,))
            db.execute(
                "DELETE FROM sessions WHERE state='closed' AND deadline < ?", (now - 7 * 86400,)
            )
            for scope, kind in scopes:
                count = db.execute(
                    "SELECT count FROM rates WHERE minute=? AND scope=?", (now // 60, scope)
                ).fetchone()
                if count and count[0] >= getattr(limits, f"{kind}_per_minute"):
                    denied = True
            if not denied:
                for scope, _ in scopes:
                    db.execute(
                        "INSERT INTO rates VALUES(?,?,1) ON CONFLICT(minute,scope) "
                        "DO UPDATE SET count=count+1",
                        (now // 60, scope),
                    )
            for scope, kind in scopes:
                usage = db.execute(
                    "SELECT sessions,seconds FROM usage WHERE day=? AND scope=?",
                    (now // 86400, scope),
                ).fetchone()
                if usage and (
                    usage[0] >= getattr(limits, f"{kind}_daily_sessions")
                    or usage[1] + limits.worker_hard_seconds
                    > getattr(limits, f"{kind}_daily_seconds")
                ):
                    denied = True
                if not usage and limits.worker_hard_seconds > getattr(
                    limits, f"{kind}_daily_seconds"
                ):
                    denied = True
                where, values = (
                    ("", ())
                    if kind == "global"
                    else (
                        f"AND {kind if kind == 'principal' else 'network'}=?",
                        (principal if kind == "principal" else network,),
                    )
                )
                active = db.execute(
                    f"SELECT count(*) FROM sessions WHERE state!='closed' {where}", values
                ).fetchone()[0]
                if active >= getattr(limits, f"{kind}_concurrent"):
                    denied = True
            if not denied:
                identifier = uuid4().hex
                db.execute(
                    "INSERT INTO sessions(id,principal,network,room,identity,deadline,state) "
                    "VALUES(?,?,?,?,?,?,?)",
                    (
                        identifier,
                        principal,
                        network,
                        f"voice_{identifier}",
                        f"listener_{identifier}",
                        now + limits.session_seconds,
                        "reserved",
                    ),
                )
                for scope, _ in scopes:
                    db.execute(
                        "INSERT INTO usage VALUES(?,?,1,?) ON CONFLICT(day,scope) "
                        "DO UPDATE SET sessions=sessions+1,seconds=seconds+excluded.seconds",
                        (now // 86400, scope, limits.worker_hard_seconds),
                    )
        if denied:
            raise AdmissionDenied("limit_reached")
        return self.get(identifier)

    def get(self, identifier):
        with self.connection() as db:
            row = db.execute("SELECT * FROM sessions WHERE id=?", (identifier,)).fetchone()
            return Reservation(**dict(row)) if row else None

    def activate(self, identifier):
        with self.transaction() as db:
            db.execute(
                "UPDATE sessions SET state='active', issued=1 WHERE id=? AND state='reserved'",
                (identifier,),
            )

    def closing(self, identifier, now):
        with self.transaction() as db:
            db.execute(
                "UPDATE sessions SET state='closing',deadline=min(deadline,?) "
                "WHERE id=? AND state!='closed'",
                (now, identifier),
            )

    def claim_cleanup(self, identifier, now):
        with self.transaction() as db:
            changed = db.execute(
                "UPDATE sessions SET state='closing',attempts=attempts+1,retry_at=? "
                "WHERE id=? AND state!='closed' AND deadline<=? AND retry_at<=? AND attempts<6",
                (now + 60, identifier, now, now),
            ).rowcount
        return self.get(identifier) if changed else None

    def due(self, now):
        with self.connection() as db:
            return [
                row[0]
                for row in db.execute(
                    "SELECT id FROM sessions WHERE state!='closed' AND deadline<=? "
                    "AND retry_at<=? AND attempts<6 ORDER BY deadline LIMIT 100",
                    (now, now),
                )
            ]

    def cleaned(self, identifier):
        with self.transaction() as db:
            db.execute("UPDATE sessions SET state='closed' WHERE id=?", (identifier,))

    def cleanup_failed(self, identifier, now):
        # Capacity remains held after all six attempts. An operator must investigate/reconcile.
        with self.transaction() as db:
            db.execute("UPDATE sessions SET retry_at=? WHERE id=?", (now + 60, identifier))

    def control_rate(self, principal, network, now):
        denied = False
        with self.transaction() as db:
            db.execute("DELETE FROM rates WHERE minute < ?", (now // 60 - 2,))
            for scope, limit in (
                ("end:global", self.limits.global_per_minute),
                (f"end:p:{principal}", self.limits.principal_per_minute),
                (f"end:n:{network}", self.limits.network_per_minute),
            ):
                row = db.execute(
                    "SELECT count FROM rates WHERE minute=? AND scope=?", (now // 60, scope)
                ).fetchone()
                if row and row[0] >= limit:
                    denied = True
                elif not denied:
                    db.execute(
                        "INSERT INTO rates VALUES(?,?,1) ON CONFLICT(minute,scope) "
                        "DO UPDATE SET count=count+1",
                        (now // 60, scope),
                    )
        if denied:
            raise AdmissionDenied("limit_reached")
