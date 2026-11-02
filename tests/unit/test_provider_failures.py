"""Actual SDK stream error propagation; only the provider _run implementations are fake."""

import asyncio

import pytest
from livekit import rtc
from livekit.agents import (
    APIConnectionError,
    APIConnectOptions,
    APIError,
    APIStatusError,
    APITimeoutError,
    llm,
    stt,
    tts,
)
from turn_harness import ScriptedLLM, ScriptedSTT, ScriptedTTS, eventually

from voiceagent.settings import Settings
from voiceagent.telemetry import protect_logging


def fault(kind):
    if kind == "timeout":
        return APITimeoutError("private request body")
    if kind == "network":
        return APIConnectionError("private network payload")
    return APIStatusError("private response body", status_code=int(kind))


@pytest.mark.parametrize("component", ["stt", "llm", "tts"])
@pytest.mark.parametrize("kind", ["401", "403", "429", "503", "timeout", "network"])
@pytest.mark.parametrize("partial", [False, True])
async def test_native_streams_fail_once_without_replay_and_close_every_task(
    component, kind, partial
):
    protect_logging(Settings())
    before = asyncio.all_tasks()
    errors, outputs, attempts = [], [], []
    options = APIConnectOptions(max_retry=0, timeout=0.1)

    class LLMStream(llm.LLMStream):
        async def _run(self):
            attempts.append(1)
            if partial:
                self._event_ch.send_nowait(
                    llm.ChatChunk(
                        id="synthetic",
                        delta=llm.ChoiceDelta(role="assistant", content="Partial output."),
                    )
                )
            raise fault(kind)

    class STTStream(stt.RecognizeStream):
        async def _run(self):
            attempts.append(1)
            if partial:
                self._event_ch.send_nowait(
                    stt.SpeechEvent(
                        type=stt.SpeechEventType.FINAL_TRANSCRIPT,
                        alternatives=[
                            stt.SpeechData(language="en", text="Synthetic", confidence=1)
                        ],
                    )
                )
            raise fault(kind)

    class TTSStream(tts.SynthesizeStream):
        async def _run(self, output_emitter):
            attempts.append(1)
            if partial:
                output_emitter.initialize(
                    request_id="synthetic",
                    sample_rate=16000,
                    num_channels=1,
                    mime_type="audio/pcm",
                    stream=True,
                )
                output_emitter.start_segment(segment_id="one")
                output_emitter.push_frame(rtc.AudioFrame(bytes(640), 16000, 1, 320))
                await eventually(lambda: outputs)
            raise fault(kind)

    client = {"llm": ScriptedLLM, "stt": ScriptedSTT, "tts": ScriptedTTS}[component]()
    client.on("error", errors.append)
    if component == "llm":
        stream = LLMStream(client, chat_ctx=llm.ChatContext(), tools=[], conn_options=options)
    elif component == "stt":
        stream = STTStream(stt=client, conn_options=options)
    else:
        stream = TTSStream(tts=client, conn_options=options)
        stream.push_text("Synthetic complete sentence.")
        stream.end_input()
    try:
        async with asyncio.timeout(5), stream:
            with pytest.raises(APIError):
                async for event in stream:
                    outputs.append(event)
    finally:
        await stream.aclose()
        await client.aclose()
    await asyncio.sleep(0)
    assert attempts == [1]
    assert len(errors) == 1 and errors[0].recoverable is False
    assert len(outputs) == int(partial)
    assert not [task for task in asyncio.all_tasks() - before if not task.done()]
