import shutil

import pytest

from voiceagent.settings import PROJECT_ROOT, ConfigurationError, load_settings


def customize(project):
    (project / "customization").mkdir()
    for name in ("agent.yaml", "prompt.md"):
        shutil.copy2(PROJECT_ROOT / "customization" / name, project / "customization" / name)
    return project / "customization" / ".env.local"


def test_new_folder_does_not_silently_switch_legacy_defaults(project):
    customize(project)
    original = load_settings(project_root=project, environ={})
    assert original.prompt_path == project / "prompt.md"
    assert original.opening.mode == "user_first" and not original.ending.enabled


def test_customization_opt_in_and_precedence_without_credential_mutation(project):
    path = customize(project)
    (project / ".env.local").write_text("GROQ_API_KEY=synthetic-legacy\n")
    path.write_text(
        "VOICEAGENT_CONFIG_PATH=customization/agent.yaml\n"
        "GROQ_API_KEY=synthetic-custom\nVOICEAGENT_TTS__SPEED=1.1\n"
    )
    settings = load_settings(project_root=project, environ={"VOICEAGENT_TTS__SPEED": "1.2"})
    assert settings.prompt_path == project / "customization/prompt.md"
    assert settings.tts.speed == 1.2
    assert settings.credentials.groq_api_key.get_secret_value() == "synthetic-custom"
    assert (project / ".env.local").read_text() == "GROQ_API_KEY=synthetic-legacy\n"


@pytest.mark.parametrize(
    "override",
    [
        {"greeting": {"mode": "custom"}},
        {"greeting": {"mode": "custom", "text": " "}},
        {"greeting": {"mode": "dynamic", "text": "Hello"}},
        {"runtime": {"greeting": "Legacy"}, "greeting": {"mode": "user_first"}},
        {"ending": {"enabled": True}, "limits": {"max_tool_steps": 0}},
        {"tts": {"model": "arbitrary-provider"}},
    ],
)
def test_configuration_rejects_ambiguous_or_unsupported_profiles(project, override):
    with pytest.raises(ConfigurationError):
        load_settings(project_root=project, environ={}, overrides=override)


def test_legacy_static_greeting_maps_to_custom_mode(project):
    settings = load_settings(
        project_root=project, environ={}, overrides={"runtime": {"greeting": "Hello exactly."}}
    )
    assert settings.opening.mode == "custom" and settings.opening.text == "Hello exactly."
