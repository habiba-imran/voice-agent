from __future__ import annotations

import json
import subprocess
import sys

import pytest
import yaml

from voiceagent.settings import ConfigurationError, Settings, load_settings

VOICE = "00000000-0000-4000-8000-000000000001"


def test_defaults_reproduced_by_example(project):
    actual = load_settings(project_root=project, environ={})
    assert actual.model_dump(exclude={"prompt_path"}) == Settings().model_dump(
        exclude={"prompt_path"}
    )


def test_precedence_and_nested_merge(project):
    (project / ".env.local").write_text("VOICEAGENT_TTS__SPEED=1.1\nGROQ_API_KEY=local-secret\n")
    loaded = load_settings(
        project_root=project,
        environ={"VOICEAGENT_TTS__SPEED": "1.2", "GROQ_API_KEY": "env-secret"},
        overrides={"tts": {"speed": 1.3}},
    )
    assert loaded.tts.speed == 1.3
    assert loaded.tts.model == "sonic-3"
    assert loaded.credentials.groq_api_key.get_secret_value() == "env-secret"


def test_env_list_and_false(project):
    loaded = load_settings(
        project_root=project,
        environ={
            "VOICEAGENT_STT__KEYTERMS": '["Ada", "CPU"]',
            "VOICEAGENT_INTERRUPTION__ENABLED": "false",
        },
    )
    assert loaded.stt.keyterms == ("Ada", "CPU")
    assert loaded.interruption.enabled is False


def test_missing_names_are_exact(settings):
    with pytest.raises(ConfigurationError) as error:
        settings.require_credentials(room=True)
    for name in (
        "DEEPGRAM_API_KEY",
        "GROQ_API_KEY",
        "CARTESIA_API_KEY",
        "LIVEKIT_API_KEY",
        "LIVEKIT_API_SECRET",
        "LIVEKIT_URL",
    ):
        assert name in str(error.value)


def test_console_does_not_require_room_credentials(project):
    loaded = load_settings(
        project_root=project,
        environ={
            "DEEPGRAM_API_KEY": "synthetic",
            "GROQ_API_KEY": "synthetic",
            "CARTESIA_API_KEY": "synthetic",
            "VOICEAGENT_TTS__VOICE_ID": VOICE,
        },
    )
    loaded.require_credentials(room=False)
    with pytest.raises(ConfigurationError, match="LIVEKIT"):
        loaded.require_credentials(room=True)


@pytest.mark.parametrize(
    "override",
    [
        {"tts": {"voice_id": "not-a-uuid"}},
        {"tts": {"model": "unknown-model"}},
        {"tts": {"speed": 0.1}},
        {"tts": {"volume": 3}},
        {"tts": {"speed": float("inf")}},
        {"runtime": {"idle_timeout_seconds": -1}},
        {"runtime": {"agent_name": "bad name"}},
        {"llm": {"max_output_tokens": 0}},
        {"llm": {"history_messages": -1}},
        {"listening": {"min_endpoint_delay": 4, "max_endpoint_delay": 1}},
        {"stt": {"model": "flux-general-en"}},
        {"listening": {"turn_detection": "stt"}},
        {"stt": {"eot_threshold": 0.7}},
        {"humanization": {"markup": True}},
        {"latency": {"preemptive_tts": True}},
        {"interruption": {"mode": "adaptive"}},
        {"unknown": True},
    ],
)
def test_invalid_settings(project, override):
    with pytest.raises(ConfigurationError, match="Invalid configuration"):
        load_settings(project_root=project, environ={}, overrides=override)


def test_flux_profile_validates_conditionally(project):
    loaded = load_settings(
        project_root=project,
        environ={},
        overrides={
            "stt": {"model": "flux-general-en", "eot_threshold": 0.7},
            "listening": {"turn_detection": "stt"},
        },
    )
    assert loaded.stt.eot_threshold == 0.7


def test_profile_error_explains_required_fix(project):
    with pytest.raises(ConfigurationError, match="Flux requires stt turn detection"):
        load_settings(
            project_root=project, environ={}, overrides={"stt": {"model": "flux-general-en"}}
        )


@pytest.mark.parametrize("content", ["", "- list\n- not mapping", "x: [broken", "credentials: {}"])
def test_malformed_yaml(project, content):
    (project / "config.example.yaml").write_text(content)
    with pytest.raises(ConfigurationError):
        load_settings(project_root=project, environ={})


@pytest.mark.parametrize("path", [42, "invalid\x00path"])
def test_invalid_path_is_actionable(project, path):
    with pytest.raises(ConfigurationError, match="paths must be valid"):
        load_settings(project_root=project, environ={}, overrides={"prompt_path": path})


def test_conflicting_nested_env_is_actionable(project):
    with pytest.raises(ConfigurationError, match="Conflicting nested"):
        load_settings(
            project_root=project,
            environ={
                "VOICEAGENT_TTS__SPEED": "1",
                "VOICEAGENT_TTS__SPEED__UNKNOWN": "1",
            },
        )


def test_no_secret_values_in_error_or_effective_config(project):
    secret = "synthetic-do-not-print"
    loaded = load_settings(project_root=project, environ={"GROQ_API_KEY": secret})
    assert secret not in json.dumps(loaded.redacted())
    assert secret not in repr(loaded)
    with pytest.raises(ConfigurationError) as error:
        load_settings(project_root=project, environ={}, overrides={"tts": {"speed": secret}})
    assert secret not in str(error.value)
    assert "tts.speed" in str(error.value)


def test_local_env_does_not_interpolate_or_modify_process(project, monkeypatch):
    monkeypatch.setenv("TEST_VARIABLE", "do-not-expand")
    (project / ".env.local").write_text("GROQ_API_KEY=${TEST_VARIABLE}\n")
    loaded = load_settings(project_root=project, environ={})
    assert loaded.credentials.groq_api_key.get_secret_value() == "${TEST_VARIABLE}"


def test_paths_do_not_depend_on_cwd(project, monkeypatch, tmp_path):
    other = tmp_path / "unrelated-host"
    other.mkdir()
    (other / ".env").write_text("GROQ_API_KEY=must-not-load\n")
    monkeypatch.chdir(other)
    loaded = load_settings(project_root=project, environ={}, overrides={"prompt_path": "prompt.md"})
    assert loaded.prompt_path == project / "prompt.md"
    assert not loaded.credentials.groq_api_key.get_secret_value()


def test_explicit_config_path_wins_environment(project):
    content = yaml.safe_load((project / "config.example.yaml").read_text())
    content["tts"]["speed"] = 1.1
    (project / "custom.yaml").write_text(yaml.safe_dump(content))
    loaded = load_settings(
        project_root=project,
        environ={"VOICEAGENT_CONFIG_PATH": "missing"},
        config_path="custom.yaml",
    )
    assert loaded.tts.speed == 1.1


def test_negative_cli_has_no_network_dependency(tmp_path, monkeypatch):
    # Supply an isolated invalid config, so developer credentials cannot affect this check.
    config = tmp_path / "invalid.yaml"
    config.write_text("tts:\n  speed: -1\n")
    result = subprocess.run(
        [sys.executable, "-m", "voiceagent.cli", "validate", "--config-path", str(config)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "tts.speed" in result.stderr
    assert "Traceback" not in result.stderr
