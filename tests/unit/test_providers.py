from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest

from voiceagent import providers
from voiceagent.settings import ConfigurationError, Credentials


@pytest.fixture
def configured(settings):
    from uuid import UUID

    return settings.model_copy(
        update={
            "credentials": Credentials(
                deepgram_api_key="dg-synthetic",
                groq_api_key="groq-synthetic",
                cartesia_api_key="tts-synthetic",
            ),
            "tts": settings.tts.model_copy(
                update={"voice_id": UUID("00000000-0000-4000-8000-000000000001")}
            ),
        }
    )


async def test_direct_provider_options_and_reverse_cleanup(configured, monkeypatch):
    closed = []

    def client(name):
        async def close():
            closed.append(name)

        return Mock(aclose=AsyncMock(side_effect=close))

    stt, model, tts = client("stt"), client("llm"), client("tts")
    factories = [Mock(return_value=value) for value in (stt, model, tts)]
    for module, name, factory in zip(
        (providers.deepgram, providers.groq, providers.cartesia),
        ("STT", "LLM", "TTS"),
        factories,
        strict=True,
    ):
        monkeypatch.setattr(module, name, factory)
    async with providers.provider_chain(configured) as chain:
        assert (chain.stt, chain.llm, chain.tts) == (stt, model, tts)
        assert not closed
    assert closed == ["tts", "llm", "stt"]
    assert factories[0].call_args.kwargs["model"] == "nova-3"
    assert factories[0].call_args.kwargs["interim_results"] is True
    assert factories[0].call_args.kwargs["api_key"] == "dg-synthetic"
    assert factories[1].call_args.kwargs["model"] == "openai/gpt-oss-20b"
    assert factories[1].call_args.kwargs["reasoning_effort"] == "low"
    assert factories[1].call_args.kwargs["max_retries"] == 0
    assert factories[2].call_args.kwargs["voice"] == str(configured.tts.voice_id)
    assert factories[2].call_args.kwargs["model"] == "sonic-3"


async def test_partial_factory_failure_closes_created_clients(configured, monkeypatch):
    stt, model = Mock(aclose=AsyncMock()), Mock(aclose=AsyncMock())
    monkeypatch.setattr(providers.deepgram, "STT", Mock(return_value=stt))
    monkeypatch.setattr(providers.groq, "LLM", Mock(return_value=model))
    monkeypatch.setattr(providers.cartesia, "TTS", Mock(side_effect=ValueError("synthetic")))
    with pytest.raises(ValueError):
        async with providers.provider_chain(configured):
            pytest.fail("Construction must fail")
    stt.aclose.assert_awaited_once()
    model.aclose.assert_awaited_once()


def test_baseline_rejects_unverified_profiles(settings):
    with pytest.raises(ConfigurationError, match="Phase 3"):
        providers.validate_baseline(
            settings.model_copy(
                update={
                    "listening": settings.listening.model_copy(
                        update={"turn_detection": "semantic"}
                    )
                }
            )
        )
    with pytest.raises(ConfigurationError, match="Phase 4"):
        providers.validate_baseline(
            settings.model_copy(
                update={"humanization": settings.humanization.model_copy(update={"enabled": True})}
            )
        )
