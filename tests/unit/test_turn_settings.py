from unittest.mock import Mock

import pytest
from livekit.agents import inference

from voiceagent import turns
from voiceagent.settings import ConfigurationError, load_settings


@pytest.mark.parametrize(
    "override",
    [
        {"listening": {"endpointing_mode": "custom"}},
        {"listening": {"endpointing_alpha": 0}},
        {"listening": {"endpointing_alpha": 1}},
        {"listening": {"vad": {"activation_threshold": 1}}},
        {"listening": {"vad": {"min_silence_duration": -1}}},
        {"listening": {"turn_detection": "semantic", "vad": {"min_silence_duration": 0.2}}},
        {"interruption": {"min_duration": 0}},
        {"interruption": {"min_words": -1}},
        {"interruption": {"false_interruption_timeout": 0}},
        {"interruption": {"backchannel_boundary": [1, -1]}},
        {"interruption": {"backchannel_boundary": [1]}},
        {"interruption": {"mode": "adaptive"}},
        {"stt": {"eot_timeout_ms": 1000}},
        {
            "stt": {"model": "flux-general-en", "eager_eot_threshold": 0.8},
            "listening": {"turn_detection": "stt"},
        },
        {
            "stt": {"model": "flux-general-en"},
            "listening": {"turn_detection": "stt", "endpointing_mode": "dynamic"},
        },
    ],
)
def test_turn_invariants_reject_invalid_combinations(project, override):
    with pytest.raises(ConfigurationError):
        load_settings(project_root=project, environ={}, overrides=override)


def test_semantic_profile_pins_local_supported_audio_detector(project):
    settings = load_settings(
        project_root=project,
        environ={},
        overrides={
            "listening": {"turn_detection": "semantic", "endpointing_mode": "dynamic"},
        },
    )
    options = turns.turn_options(settings)
    detector = options["turn_detection"]
    assert isinstance(detector, inference.TurnDetector)
    assert detector.model == "turn-detector-v1-mini"
    assert options["endpointing"] == {
        "mode": "dynamic",
        "alpha": 0.9,
        "min_delay": 0.5,
        "max_delay": 3.0,
    }


def test_flux_has_no_competing_endpoint_config(project):
    settings = load_settings(
        project_root=project,
        environ={},
        overrides={
            "stt": {"model": "flux-general-en"},
            "listening": {"turn_detection": "stt"},
        },
    )
    options = turns.turn_options(settings)
    assert options["turn_detection"] == "stt"
    assert options["endpointing"] == {"mode": "fixed", "min_delay": 0.0, "max_delay": 0.0}
    assert options["preemptive_generation"] == {"enabled": False, "preemptive_tts": False}


def test_adaptive_opt_in_requires_cloud_keys_even_in_console(project):
    settings = load_settings(
        project_root=project,
        environ={},
        overrides={
            "interruption": {"mode": "adaptive", "allow_cloud_inference": True},
        },
    )
    with pytest.raises(ConfigurationError, match="LIVEKIT_API_KEY, LIVEKIT_API_SECRET"):
        settings.require_credentials(room=False)
    options = turns.turn_options(settings)
    assert options["interruption"]["mode"] == "adaptive"
    assert "allow_cloud_inference" not in options["interruption"]


def test_vad_options_are_centralized(settings, monkeypatch):
    factory = Mock()
    monkeypatch.setattr(turns.silero.VAD, "load", factory)
    turns.load_vad(settings)
    factory.assert_called_once_with(**settings.listening.vad.model_dump())


def test_only_semantic_profile_prewarms_local_detector(project, monkeypatch):
    from livekit import local_inference

    initialize = Mock()
    monkeypatch.setattr(local_inference, "init_eot", initialize)
    settings = load_settings(project_root=project, environ={})
    turns.prewarm_detector(settings)
    initialize.assert_not_called()
    semantic = load_settings(
        project_root=project,
        environ={},
        overrides={
            "listening": {"turn_detection": "semantic"},
        },
    )
    turns.prewarm_detector(semantic)
    initialize.assert_called_once_with()


def test_native_dynamic_endpointing_learns_pauses_and_stays_bounded():
    # This behavioral check intentionally targets the locked SDK's implementation;
    # production code uses only public TurnHandlingOptions.
    from livekit.agents.voice.endpointing import DynamicEndpointing

    endpoint = DynamicEndpointing(min_delay=0.5, max_delay=3, alpha=0.9)
    endpoint.on_start_of_speech(0)
    endpoint.on_end_of_speech(1)
    endpoint.on_start_of_speech(2)
    endpoint.on_end_of_speech(3)
    assert 0.5 < endpoint.min_delay <= 3
    learned = endpoint.min_delay
    # A long silence can raise patience only up to the configured ceiling.
    endpoint.on_start_of_speech(100)
    endpoint.on_end_of_speech(101)
    assert learned <= endpoint.min_delay <= endpoint.max_delay == 3
