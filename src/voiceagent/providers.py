"""Direct provider clients, owned by one session and closed in reverse order."""

from __future__ import annotations

import asyncio
import logging
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass, field

from livekit.plugins import cartesia, deepgram, groq

from .expression import tts_controls
from .settings import Settings

logger = logging.getLogger(__name__)


class ProviderCleanupError(RuntimeError):
    """A fixed cleanup failure code, with no provider exception payload."""


async def close_client(client, component, timeout_seconds):
    try:
        async with asyncio.timeout(timeout_seconds):
            await client.aclose()
    except TimeoutError:
        logger.error("provider_cleanup_timeout", extra={"component": component})
        raise ProviderCleanupError("provider_cleanup_timeout") from None
    except Exception:
        logger.error("provider_cleanup_failed", extra={"component": component})
        raise ProviderCleanupError("provider_cleanup_failed") from None


@dataclass(frozen=True)
class ProviderChain:
    stt: deepgram.STT | deepgram.STTv2 = field(repr=False)
    llm: groq.LLM = field(repr=False)
    tts: cartesia.TTS = field(repr=False)


@asynccontextmanager
async def provider_chain(settings: Settings):
    settings.require_credentials(room=False)
    async with AsyncExitStack() as cleanup:
        stt_options = dict(
            api_key=settings.credentials.deepgram_api_key.get_secret_value(),
            model=settings.stt.model,
            keyterm=list(settings.stt.keyterms),
        )
        if settings.stt.model == "nova-3":
            stt = deepgram.STT(
                **stt_options,
                language=settings.stt.language,
                interim_results=True,
                filler_words=True,
            )
        else:
            flux_options = settings.stt.model_dump(
                include={"eot_threshold", "eager_eot_threshold", "eot_timeout_ms"},
                exclude_none=True,
            )
            stt = deepgram.STTv2(**stt_options, **flux_options)
        cleanup.push_async_callback(
            close_client, stt, "stt", settings.runtime.shutdown_timeout_seconds
        )
        model = groq.LLM(
            api_key=settings.credentials.groq_api_key.get_secret_value(),
            model=settings.llm.model,
            reasoning_effort=settings.llm.reasoning_effort,
            temperature=settings.llm.temperature,
            max_completion_tokens=settings.llm.max_output_tokens,
            max_retries=0,
        )
        cleanup.push_async_callback(
            close_client, model, "llm", settings.runtime.shutdown_timeout_seconds
        )
        speech = cartesia.TTS(
            api_key=settings.credentials.cartesia_api_key.get_secret_value(),
            model=settings.tts.model,
            voice=str(settings.tts.voice_id),
            language=settings.tts.language,
            **tts_controls(settings),
        )
        cleanup.push_async_callback(
            close_client, speech, "tts", settings.runtime.shutdown_timeout_seconds
        )
        yield ProviderChain(stt, model, speech)
