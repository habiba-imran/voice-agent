from __future__ import annotations

from dataclasses import dataclass, field, fields
from pathlib import Path
from urllib.parse import urlsplit


@dataclass(frozen=True)
class AdmissionLimits:
    session_seconds: int = 300
    worker_hard_seconds: int = 1800
    token_seconds: int = 60
    global_concurrent: int = 3
    principal_concurrent: int = 1
    network_concurrent: int = 2
    global_per_minute: int = 20
    principal_per_minute: int = 3
    network_per_minute: int = 6
    global_daily_sessions: int = 20
    principal_daily_sessions: int = 5
    network_daily_sessions: int = 10
    global_daily_seconds: int = 36000
    principal_daily_seconds: int = 9000
    network_daily_seconds: int = 18000

    def __post_init__(self):
        if any(
            type(getattr(self, item.name)) is not int
            or not 1 <= getattr(self, item.name) <= 10_000_000
            for item in fields(self)
        ):
            raise ValueError("Admission limits must be positive bounded integers")
        if not 30 <= self.token_seconds <= min(120, self.session_seconds):
            raise ValueError("Token TTL must be 30..120 seconds and no longer than the session")
        if not self.session_seconds <= self.worker_hard_seconds <= 14400:
            raise ValueError("Session duration must fit the verified worker hard duration")


@dataclass(frozen=True)
class GatewaySettings:
    database: Path
    livekit_url: str = field(repr=False)
    api_key: str = field(repr=False)
    api_secret: str = field(repr=False)
    assertion_secret: str = field(repr=False)
    web_origin: str
    agent_name: str = "voiceagent"
    limits: AdmissionLimits = field(default_factory=AdmissionLimits)

    def __post_init__(self):
        import re

        if not self.database.is_absolute() or self.database.name == ":memory:":
            raise ValueError("An absolute persistent database file is required")
        if not self.api_key or not self.api_secret or len(self.assertion_secret.encode()) < 32:
            raise ValueError("Gateway server credentials/assertion secret are required")
        url = urlsplit(self.livekit_url)
        if not (
            url.scheme in {"wss", "https"}
            and url.hostname
            and url.hostname.endswith(".livekit.cloud")
            and url.username is None
            and url.password is None
            and not url.query
            and not url.fragment
            and url.port != 0
        ):
            raise ValueError(
                "Gateway requires a secure LiveKit Cloud URL for strict token revocation"
            )
        origin = urlsplit(self.web_origin)
        if (
            origin.scheme != "https"
            or not origin.hostname
            or origin.path
            or origin.query
            or origin.fragment
            or origin.username is not None
            or origin.password is not None
        ):
            raise ValueError("web_origin must be an exact HTTPS origin")
        if re.fullmatch(r"[a-z][a-z0-9_-]{0,62}", self.agent_name) is None:
            raise ValueError("Invalid explicit agent dispatch name")


def from_environment(environ):
    """No dotenv search, defaults for secrets or diagnostic dumps of input values."""
    limits = {
        item.name: int(environ[f"VOICE_GATEWAY_{item.name.upper()}"])
        for item in fields(AdmissionLimits)
        if f"VOICE_GATEWAY_{item.name.upper()}" in environ
    }
    return GatewaySettings(
        database=Path(environ["VOICE_GATEWAY_DATABASE"]),
        livekit_url=environ["LIVEKIT_URL"],
        api_key=environ["LIVEKIT_API_KEY"],
        api_secret=environ["LIVEKIT_API_SECRET"],
        assertion_secret=environ["VOICE_GATEWAY_ASSERTION_SECRET"],
        web_origin=environ["VOICE_GATEWAY_WEB_ORIGIN"],
        agent_name=environ.get("VOICE_GATEWAY_AGENT_NAME", "voiceagent"),
        limits=AdmissionLimits(**limits),
    )
