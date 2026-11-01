"""Check indexed source against configured credentials without printing their values."""

from __future__ import annotations

import subprocess
from pathlib import Path

from voiceagent.settings import PROJECT_ROOT, SECRET_NAMES, load_settings


def main() -> None:
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=PROJECT_ROOT, capture_output=True, check=True, timeout=30
    )
    files = [Path(name.decode("utf-8")) for name in result.stdout.split(b"\x00") if name]
    settings = load_settings()
    credentials = [
        getattr(settings.credentials, name).get_secret_value().encode("utf-8")
        for name in SECRET_NAMES.values()
        if getattr(settings.credentials, name).get_secret_value()
    ]
    failures = []
    for path in files:
        if (path.name.startswith(".env") and path.name != ".env.example") or (
            path.name.startswith("livekit") and path.suffix == ".toml"
        ):
            failures.append(str(path))
            continue
        # Scan the index contents, rather than assuming the worktree matches staged changes.
        indexed = subprocess.run(
            ["git", "show", f":{path.as_posix()}"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            check=True,
            timeout=30,
        ).stdout
        if any(secret in indexed for secret in credentials):
            failures.append(str(path))
    if not files:
        raise SystemExit("BLOCKED: no indexed source files to scan")
    if failures:
        raise SystemExit(
            "FAIL: indexed secrets or deployment identities in: " + ", ".join(failures)
        )
    print(
        f"PASS: {len(files)} indexed files checked against {len(credentials)} configured "
        "credential values; no private env/deployment files indexed."
    )
    print("Scope: configured values and filenames only; not a general secret-detection guarantee.")


if __name__ == "__main__":
    main()
