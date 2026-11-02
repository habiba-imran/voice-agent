from __future__ import annotations

import shutil
import socket
from pathlib import Path

import pytest

from voiceagent.settings import PROJECT_ROOT, load_settings


@pytest.fixture
def project(tmp_path: Path) -> Path:
    for name in ("config.example.yaml", "prompt.md"):
        shutil.copy2(PROJECT_ROOT / name, tmp_path / name)
    return tmp_path


@pytest.fixture
def settings(project):
    return load_settings(project_root=project, environ={})


@pytest.fixture(autouse=True)
def no_external_network(monkeypatch):
    """Every automated test is offline, including the copied project's unit suite."""
    # Windows asyncio needs IPv4 loopback to construct its wakeup socket pair.
    for owner, name in (
        (socket, "getaddrinfo"),
        (socket.socket, "connect"),
        (socket.socket, "connect_ex"),
    ):
        original = getattr(owner, name)

        def guarded(*args, _original=original, _name=name, **kwargs):
            host = args[0] if _name == "getaddrinfo" else args[1][0]
            if host not in ("127.0.0.1", "::1", "localhost"):
                raise AssertionError("External network access is forbidden in automated tests")
            return _original(*args, **kwargs)

        monkeypatch.setattr(owner, name, guarded)
