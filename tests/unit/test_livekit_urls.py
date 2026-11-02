"""Synthetic configuration/SDK transport regressions; never registers a real worker."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from unittest.mock import AsyncMock, Mock

import pytest

from voiceagent import runtime
from voiceagent.settings import ConfigurationError, livekit_url_diagnostics, load_settings

SYNTHETIC_ENV = {
    "LIVEKIT_API_KEY": "synthetic-livekit-key",
    "LIVEKIT_API_SECRET": "synthetic-livekit-secret-not-a-real-key",
    "DEEPGRAM_API_KEY": "synthetic-deepgram",
    "GROQ_API_KEY": "synthetic-groq",
    "CARTESIA_API_KEY": "synthetic-cartesia",
    "VOICEAGENT_TTS__VOICE_ID": "00000000-0000-4000-8000-000000000001",
}


def configured(project, url):
    return load_settings(project_root=project, environ={**SYNTHETIC_ENV, "LIVEKIT_URL": url})


@pytest.mark.parametrize(
    "url",
    [
        "https://example.invalid",
        "http://127.0.0.1:7880",
        "http://[::1]:7880",
        "http://localhost:7880",
    ],
)
def test_supported_http_alias_passes_application_startup_validation(project, url):
    configured(project, url).require_credentials(room=True)


@pytest.mark.parametrize(
    "url,registration_url",
    [
        ("https://example.invalid", "wss://example.invalid/agent"),
        ("https://example.invalid:7443/prefix/", "wss://example.invalid:7443/prefix/agent"),
        ("http://127.0.0.1:7880", "ws://127.0.0.1:7880/agent"),
        ("http://[::1]:7880", "ws://[::1]:7880/agent"),
        ("wss://example.invalid", "wss://example.invalid/agent"),
        ("ws://localhost:7880", "ws://localhost:7880/agent"),
    ],
)
async def test_installed_worker_converts_http_alias_for_registration(
    project, monkeypatch, url, registration_url
):
    monkeypatch.delenv("LIVEKIT_WORKER_TOKEN", raising=False)
    monkeypatch.delenv("LIVEKIT_AGENT_DEPLOYMENT", raising=False)
    server = runtime.build_server(configured(project, url))
    # Intentionally independent of the application guard: prove the locked SDK accepts these
    # forms. Stop at the transport boundary, before network/registration or retries can occur.
    connect = AsyncMock(side_effect=asyncio.CancelledError)
    server._http_session = Mock(ws_connect=connect)
    server._closed = False  # A newly constructed server has not entered run() yet.
    with pytest.raises(asyncio.CancelledError):
        await server._connection_task()
    assert connect.await_count == 1
    assert connect.call_args.args == (registration_url,)
    assert connect.call_args.kwargs["params"] == {}


@pytest.mark.parametrize(
    "url",
    [
        "http://example.invalid",
        "ws://example.invalid",
        "http://localhost.example.invalid",
        "https://user:private@example.invalid",
        "https://@example.invalid",
        "wss://@example.invalid",
        "http://user:private@localhost:7880",
        "https://example.invalid?token=private",
        "http://localhost:7880?token=private",
        "https://example.invalid#private",
        "http://localhost:7880#private",
        "https://",
        "https://example.invalid:invalid",
        "https://example.invalid:0",
        "https://example.invalid:65536",
        "https://[invalid",
        "httpx://example.invalid",
        "file:///private",
    ],
)
def test_alias_support_preserves_tls_and_url_security_guards(project, url):
    with pytest.raises(ConfigurationError) as caught:
        configured(project, url).require_credentials(room=True)
    assert "LIVEKIT_URL" in str(caught.value)
    assert "example.invalid" not in str(caught.value)
    assert "private" not in str(caught.value)


def test_cloud_markers_do_not_bypass_remote_tls(project, monkeypatch):
    monkeypatch.setenv("LIVEKIT_WORKER_TOKEN", "synthetic-worker-token")
    monkeypatch.setenv("LIVEKIT_AGENT_DEPLOYMENT", "synthetic-deployment")
    with pytest.raises(ConfigurationError):
        configured(project, "http://example.invalid").require_credentials(room=True)


@pytest.mark.parametrize("scheme", ["wss", "https"])
def test_injected_process_url_wins_over_local_dotenv_unchanged(project, monkeypatch, scheme):
    (project / ".env.local").write_text("LIVEKIT_URL=wss://local-only.invalid\n")
    url = f"{scheme}://injected.invalid"
    for key, value in {**SYNTHETIC_ENV, "LIVEKIT_URL": url}.items():
        monkeypatch.setenv(key, value)
    loaded = load_settings(project_root=project)
    loaded.require_credentials(room=True)
    assert loaded.credentials.livekit_url == url
    assert os.environ["LIVEKIT_URL"] == url
    assert (project / ".env.local").read_text() == "LIVEKIT_URL=wss://local-only.invalid\n"


@pytest.mark.parametrize(
    "url,scheme,category",
    [
        ("wss://private.example.invalid/path?private#private", "wss", "non-loopback"),
        ("https://user:private@private.invalid", "https", "non-loopback"),
        ("http://127.0.0.1:7880", "http", "loopback"),
        ("http://127.0.0.2:7880", "http", "loopback"),
        ("ws://[::1]:7880", "ws", "loopback"),
        ("ws://LOCALHOST:7880", "ws", "loopback"),
        ("private://private.invalid", "unsupported", "non-loopback"),
        ("private", "unsupported", "unknown"),
        ("https://[private", "unparseable", "unknown"),
    ],
)
def test_diagnostic_is_bounded_and_omits_sensitive_url_parts(url, scheme, category):
    result = livekit_url_diagnostics(url)
    assert result == {"livekit_url_scheme": scheme, "livekit_url_host_category": category}
    assert "private" not in json.dumps(result)


@pytest.mark.parametrize("mode", ["start", "dev", "console"])
def test_startup_checks_env_and_delegates_to_sdk_without_provider_calls(
    project, monkeypatch, capsys, mode
):
    loaded = configured(project, "https://injected.invalid")
    monkeypatch.setattr(runtime, "load_settings", lambda: loaded)
    monkeypatch.setattr(runtime, "protect_logging", Mock())
    monkeypatch.setattr(sys, "argv", ["agent.py", mode])
    delegate = Mock()
    monkeypatch.setattr(runtime.runpy, "run_module", delegate)
    runtime.run()
    delegate.assert_called_once_with("livekit.agents", run_name="__main__")
    assert "start" in sys.argv or mode == "console"
    captured = capsys.readouterr()
    assert captured.out == ""
    if mode == "console":
        assert captured.err == ""
    else:
        assert json.loads(captured.err) == {
            "livekit_url_scheme": "https",
            "livekit_url_host_category": "non-loopback",
        }


def test_failed_startup_emits_only_safe_diagnostic_before_fixed_error(project, monkeypatch, capsys):
    loaded = configured(project, "wss://user:private@private.invalid?token=private")
    monkeypatch.setattr(runtime, "load_settings", lambda: loaded)
    monkeypatch.setattr(sys, "argv", ["agent.py", "start"])
    delegate = Mock()
    monkeypatch.setattr(runtime.runpy, "run_module", delegate)
    with pytest.raises(ConfigurationError):
        runtime.run()
    delegate.assert_not_called()
    captured = capsys.readouterr()
    assert json.loads(captured.err) == {
        "livekit_url_scheme": "wss",
        "livekit_url_host_category": "non-loopback",
    }
    assert "private" not in captured.err and "synthetic" not in captured.err
