"""Direct provider clients, owned by one session and closed in reverse order."""

from __future__ import annotations

from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass, field

from livekit.plugins import cartesia, deepgram, groq

from .settings import ConfigurationError, Settings


@dataclass(frozen=True)
class ProviderChain:
    stt: deepgram.STT = field(repr=False)
    llm: groq.LLM = field(repr=False)
    tts: cartesia.TTS = field(repr=False)


def validate_baseline(settings: Settings) -> None:
    if settings.stt.model != "nova-3" or settings.listening.turn_detection != "vad":
        raise ConfigurationError("Phase 2 requires nova-3 and vad; other profiles await Phase 3")
    if settings.humanization.enabled:
        raise ConfigurationError("Keep humanization disabled until Phase 4 audio verification")
    if settings.latency.preemptive_llm:
        raise ConfigurationError("Keep preemptive generation disabled until Phase 5 comparison")


@asynccontextmanager
async def provider_chain(settings: Settings):
    validate_baseline(settings)
    settings.require_credentials(room=False)
    async with AsyncExitStack() as cleanup:
        stt = deepgram.STT(
            api_key=settings.credentials.deepgram_api_key.get_secret_value(),
            model=settings.stt.model,
            language=settings.stt.language,
            keyterm=list(settings.stt.keyterms),
            interim_results=True,
            filler_words=True,
        )
        cleanup.push_async_callback(stt.aclose)
        model = groq.LLM(
            api_key=settings.credentials.groq_api_key.get_secret_value(),
            model=settings.llm.model,
            reasoning_effort=settings.llm.reasoning_effort,
            temperature=settings.llm.temperature,
            max_completion_tokens=settings.llm.max_output_tokens,
            max_retries=0,
        )
        cleanup.push_async_callback(model.aclose)
        speech = cartesia.TTS(
            api_key=settings.credentials.cartesia_api_key.get_secret_value(),
            model=settings.tts.model,
            voice=str(settings.tts.voice_id),
            language=settings.tts.language,
            speed=settings.tts.speed,
            volume=settings.tts.volume,
            emotion=settings.tts.emotion,
        )
        cleanup.push_async_callback(speech.aclose)
        yield ProviderChain(stt, model, speech)
