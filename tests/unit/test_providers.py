from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest

from voiceagent import providers
from voiceagent.settings import Credentials


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


@pytest.mark.parametrize("humanized", [False, True])
async def test_direct_provider_options_and_reverse_cleanup(configured, monkeypatch, humanized):
    configured = configured.model_copy(
        update={"humanization": configured.humanization.model_copy(update={"enabled": humanized})}
    )
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
    assert factories[2].call_args.kwargs["emotion"] == (None if humanized else "neutral")
    assert factories[2].call_args.kwargs["speed"] == 1


async def test_flux_factory_uses_v2_only_and_closes_it(configured, monkeypatch):
    from voiceagent.settings import Settings

    data = configured.model_dump()
    data["stt"].update(model="flux-general-en", eot_threshold=0.8, eot_timeout_ms=4000)
    data["listening"]["turn_detection"] = "stt"
    settings = Settings.model_validate(data)
    v2 = Mock(aclose=AsyncMock())
    factory = Mock(return_value=v2)
    v1 = Mock(side_effect=AssertionError("Nova must not be constructed for Flux"))
    monkeypatch.setattr(providers.deepgram, "STT", v1)
    monkeypatch.setattr(providers.deepgram, "STTv2", factory)
    monkeypatch.setattr(providers.groq, "LLM", Mock(return_value=Mock(aclose=AsyncMock())))
    monkeypatch.setattr(providers.cartesia, "TTS", Mock(return_value=Mock(aclose=AsyncMock())))
    async with providers.provider_chain(settings) as chain:
        assert chain.stt is v2
    v2.aclose.assert_awaited_once()
    assert factory.call_args.kwargs == {
        "api_key": "dg-synthetic",
        "model": "flux-general-en",
        "keyterm": [],
        "eot_threshold": 0.8,
        "eot_timeout_ms": 4000,
    }


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


def test_preemptive_tts_remains_disabled():
    from pydantic import ValidationError

    from voiceagent.settings import LatencySettings

    with pytest.raises(ValidationError):
        LatencySettings(preemptive_tts=True)


@pytest.mark.parametrize("failure", ["timeout", "exception", "cancel"])
async def test_cleanup_attempts_every_client_despite_failed_close(configured, monkeypatch, failure):
    import asyncio

    configured = configured.model_copy(
        update={"runtime": configured.runtime.model_copy(update={"shutdown_timeout_seconds": 0.01})}
    )
    closed = []

    async def close(name):
        closed.append(name)
        if name == "tts":
            if failure == "timeout":
                await asyncio.Event().wait()
            if failure == "cancel":
                raise asyncio.CancelledError()
            raise RuntimeError("private provider payload")

    def client(label):
        async def close_this():
            await close(label)

        return Mock(aclose=AsyncMock(side_effect=close_this))

    for module, name, label in (
        (providers.deepgram, "STT", "stt"),
        (providers.groq, "LLM", "llm"),
        (providers.cartesia, "TTS", "tts"),
    ):
        monkeypatch.setattr(
            module,
            name,
            Mock(return_value=client(label)),
        )

    with pytest.raises(
        asyncio.CancelledError if failure == "cancel" else providers.ProviderCleanupError
    ):
        async with providers.provider_chain(configured):
            pass
    assert closed == ["tts", "llm", "stt"]
