"""Offline packaging contracts, not a Docker build or deployment certification."""

from __future__ import annotations

import json
import re
import tomllib
from http.client import BadStatusLine
from unittest.mock import Mock

import pathspec
import pytest
import yaml

from voiceagent import healthcheck, runtime
from voiceagent.prompts import session_prompt
from voiceagent.settings import PROJECT_ROOT, ConfigurationError, load_settings


def instructions():
    text = (PROJECT_ROOT / "Dockerfile").read_text()
    return [
        line.strip()
        for line in text.replace("\\\n", " ").splitlines()
        if line.strip() and not line.startswith("#")
    ]


def test_container_pins_match_recorded_public_manifests():
    pins = json.loads((PROJECT_ROOT / "docs/CONTAINER_PINS.json").read_text())
    source = instructions()
    for name in ("python", "uv"):
        pin = pins[name]
        assert re.fullmatch(r"sha256:[a-f0-9]{64}", pin["digest"])
        assert any(f"{pin['image']}@{pin['digest']} AS " in line for line in source)


def test_image_uses_locked_build_and_nonroot_exec_runtime():
    source = instructions()
    assert sum(line.startswith("FROM ") for line in source) == 4
    installs = [line for line in source if line.startswith("RUN uv sync")]
    assert len(installs) == 2
    assert all("--locked --no-dev" in line for line in installs)
    assert any("--network=none" in line and "prepare_models.py" in line for line in source)
    assert not any(line.startswith("ARG ") for line in source)
    assert not any(re.search(r"\bCOPY\s+\.\s", line) for line in source)
    final = source[source.index("FROM base AS runtime") :]
    assert "USER 10001:10001" in final
    assert "STOPSIGNAL SIGTERM" in final
    assert json.loads(final[-1].removeprefix("CMD ")) == ["python", "agent.py", "start"]
    health = next(line for line in final if line.startswith("HEALTHCHECK"))
    assert json.loads(health.split("CMD ", 1)[1]) == ["python", "-m", "voiceagent.healthcheck"]
    assert not any("uv sync" in line or "pip install" in line for line in final)
    assert all("--from=build" in line for line in final if line.startswith("COPY "))
    env = " ".join(line for line in source if line.startswith("ENV "))
    assert not any(word in env for word in ("API_KEY", "API_SECRET", "TOKEN", "LIVEKIT_URL"))


@pytest.mark.parametrize(
    "name,excluded",
    [
        ("Dockerfile", False),
        ("agent.py", False),
        ("src/voiceagent/healthcheck.py", False),
        ("scripts/prepare_models.py", False),
        ("uv.lock", False),
        (".env.local", True),
        (".env.example", True),
        ("src/voiceagent/.env.production", True),
        ("src/voiceagent/__pycache__/settings.cpython-312.pyc", True),
        ("src/voiceagent/credentials.json", True),
        ("credentials.json", True),
        (".tools/wheelhouse/private.whl", True),
        (".git/config", True),
        ("deploy/livekit.toml.example", True),
        ("livekit.toml", True),
        ("src/voiceagent/livekit.other.toml", True),
        ("evals/results/private.wav", True),
        ("docs/private.md", True),
        ("private-project/new-file.txt", True),
        ("compose.yaml", True),
    ],
)
def test_docker_context_allowlist(name, excluded):
    # pathspec models this glob subset; Docker's actual sent context is still unverified.
    rules = pathspec.GitIgnoreSpec.from_lines(
        (PROJECT_ROOT / ".dockerignore").read_text().splitlines()
    )
    assert rules.match_file(name) is excluded


def test_compose_runtime_contract_has_no_secrets_or_public_ports():
    service = yaml.safe_load((PROJECT_ROOT / "compose.yaml").read_text())["services"]["voiceagent"]
    assert service["build"] == {"context": ".", "target": "runtime"}
    assert service["platform"] == "linux/amd64"
    assert service["env_file"] == [
        {"path": "${VOICEAGENT_ENV_FILE:-.env.local}", "required": True, "format": "raw"}
    ]
    assert service["read_only"] and service["init"]
    assert service["cap_drop"] == ["ALL"]
    assert service["security_opt"] == ["no-new-privileges:true"]
    assert service["stop_signal"] == "SIGTERM" and service["stop_grace_period"] == "62m"
    assert service["restart"] == "no"
    assert not {"ports", "privileged", "volumes", "environment"}.intersection(service)
    assert service["logging"]["options"] == {"max-size": "10m", "max-file": "3"}


def test_cloud_template_is_inert_and_project_independent():
    template = tomllib.loads((PROJECT_ROOT / "deploy/livekit.toml.example").read_text())
    assert template == {
        "project": {"subdomain": "REPLACE_WITH_APPROVED_PROJECT"},
        "agent": {"id": "REPLACE_WITH_GENERATED_AGENT_ID"},
    }


@pytest.mark.parametrize("drain,close,start", [(5, 10, 30), (1, 2, 12)])
def test_sdk_process_limits_cover_cooperative_cleanup(settings, monkeypatch, drain, close, start):
    configured = settings.model_copy(
        update={
            "runtime": settings.runtime.model_copy(
                update={
                    "drain_timeout_seconds": drain,
                    "shutdown_timeout_seconds": close,
                    "startup_timeout_seconds": start,
                }
            )
        }
    )
    factory = Mock()
    monkeypatch.setattr(runtime, "AgentServer", factory)
    runtime.build_server(configured)
    assert factory.call_args.kwargs["initialize_process_timeout"] == start
    assert factory.call_args.kwargs["shutdown_process_timeout"] == drain + 5 * close + 5
    # Preserve the SDK's native worker drain budget and signal handling.
    assert "drain_timeout" not in factory.call_args.kwargs


@pytest.mark.parametrize(
    "status,body,expected", [(200, b"OK", True), (503, b"bad", False), (200, b"wrong", False)]
)
def test_probe_closes_connection_and_checks_sdk_response(monkeypatch, status, body, expected):
    connection = Mock()
    connection.getresponse.return_value.status = status
    connection.getresponse.return_value.read.return_value = body
    constructor = Mock(return_value=connection)
    monkeypatch.setattr(healthcheck, "HTTPConnection", constructor)
    assert healthcheck.healthy(8123) is expected
    constructor.assert_called_once_with("127.0.0.1", 8123, timeout=2)
    connection.request.assert_called_once_with("GET", "/")
    connection.close.assert_called_once()


@pytest.mark.parametrize("error", [TimeoutError(), ConnectionRefusedError(), BadStatusLine("bad")])
def test_probe_fails_closed_without_exception_payloads(monkeypatch, capsys, error):
    connection = Mock()
    connection.request.side_effect = error
    monkeypatch.setattr(healthcheck, "HTTPConnection", Mock(return_value=connection))
    assert not healthcheck.healthy()
    connection.close.assert_called_once()
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("result,exit_code", [(True, 0), (False, 1)])
def test_health_command_exit_status(monkeypatch, result, exit_code):
    monkeypatch.setattr(healthcheck, "healthy", lambda: result)
    with pytest.raises(SystemExit) as error:
        healthcheck.main()
    assert error.value.code == exit_code


def test_cloud_injected_env_and_self_host_config_share_validation(project):
    environment = {
        "LIVEKIT_URL": "wss://example.invalid",
        "LIVEKIT_API_KEY": "synthetic-livekit",
        "LIVEKIT_API_SECRET": "synthetic-livekit-secret",
        "DEEPGRAM_API_KEY": "synthetic-deepgram",
        "GROQ_API_KEY": "synthetic-groq",
        "CARTESIA_API_KEY": "synthetic-cartesia",
        "VOICEAGENT_TTS__VOICE_ID": "00000000-0000-4000-8000-000000000001",
    }
    configured = load_settings(project_root=project, environ=environment)
    configured.require_credentials(room=True)
    assert session_prompt(configured).text
    assert configured.runtime.dispatch == "explicit"
    assert "synthetic-" not in json.dumps(configured.redacted())
    environment.pop("LIVEKIT_API_SECRET")
    with pytest.raises(ConfigurationError, match="LIVEKIT_API_SECRET"):
        load_settings(project_root=project, environ=environment).require_credentials(room=True)
