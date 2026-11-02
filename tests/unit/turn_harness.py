"""Offline devices for the real 1.8.10 session. No microphone, sockets or provider SDKs.

VAD/STT verdicts are scripted, not inferred from sound. Silent PCM carries numbered
output markers so assertions can distinguish stale output without claiming audio quality.
"""

from __future__ import annotations

import asyncio
import struct
import time
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from functools import partial
from unittest.mock import patch

from livekit import rtc
from livekit.agents import AgentSession, APIStatusError, APITimeoutError, llm, stt, tts, vad
from livekit.agents.utils import aio
from livekit.agents.voice import io

from voiceagent.hooks import SessionExtensions
from voiceagent.prompts import session_prompt
from voiceagent.providers import ProviderChain
from voiceagent.runtime import VoiceAgent, build_session


async def eventually(predicate):
    async with asyncio.timeout(3):
        while not predicate():  # noqa: ASYNC110 - bounded observation of native SDK state
            await asyncio.sleep(0.005)


@dataclass
class Reply:
    chunks: tuple[str, ...] = ("A short answer.",)
    hold: bool = False
    fail: bool = False
    before_first: bool = False
    first_delay: float = 0
    chunk_delay: float = 0
    fault_status: int | None = None
    fault_timeout: bool = False
    release: asyncio.Event = field(default_factory=asyncio.Event)
    started: asyncio.Event = field(default_factory=asyncio.Event)
    closed: asyncio.Event = field(default_factory=asyncio.Event)
    failed: asyncio.Event = field(default_factory=asyncio.Event)


class ScriptedLLM(llm.LLM):
    def __init__(self):
        super().__init__()
        self.pending = deque()
        self.contexts = []
        self.active = 0

    @asynccontextmanager
    async def chat(self, *, chat_ctx, **kwargs):
        reply = self.pending.popleft()
        self.contexts.append(chat_ctx.copy())

        async def tokens():
            reply.started.set()
            self.active += 1
            try:
                if reply.first_delay:
                    await asyncio.sleep(reply.first_delay)
                if reply.before_first:
                    await reply.release.wait()
                yield reply.chunks[0]
                if reply.hold:
                    await reply.release.wait()
                if reply.fail:
                    reply.failed.set()
                    if reply.fault_status is not None or reply.fault_timeout:
                        self.emit(
                            "error",
                            llm.LLMError(
                                timestamp=time.time(),
                                label="synthetic",
                                recoverable=False,
                                error=APITimeoutError("synthetic timeout")
                                if reply.fault_timeout
                                else APIStatusError(
                                    "synthetic fault", status_code=reply.fault_status
                                ),
                            ),
                        )
                    raise RuntimeError("synthetic provider failure")
                for chunk in reply.chunks[1:]:
                    if reply.chunk_delay:
                        await asyncio.sleep(reply.chunk_delay)
                    yield chunk
            finally:
                self.active -= 1

        try:
            yield tokens()
        finally:
            reply.closed.set()


class ScriptedSTT(stt.STT):
    def __init__(self):
        super().__init__(capabilities=stt.STTCapabilities(streaming=True, interim_results=True))

    async def _recognize_impl(self, *args, **kwargs):
        raise AssertionError("Batch STT is outside this offline test")


class ScriptedTTS(tts.TTS):
    def __init__(self):
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=True), sample_rate=16000, num_channels=1
        )

    def synthesize(self, *args, **kwargs):
        raise AssertionError("The synthetic agent supplies PCM directly")


class ScriptedVAD(vad.VAD):
    def __init__(self):
        super().__init__(capabilities=vad.VADCapabilities(update_interval=0.02))
        self.streams = []

    def stream(self):
        stream = ScriptedVADStream(self)
        self.streams.append(stream)
        return stream

    def send(self, kind, *, duration=0, silence=0):
        event = vad.VADEvent(
            type=kind,
            samples_index=0,
            timestamp=time.time(),
            speech_duration=duration,
            silence_duration=silence,
            speaking=kind != vad.VADEventType.END_OF_SPEECH,
            probability=1,
            raw_accumulated_speech=duration,
            raw_accumulated_silence=silence,
        )
        for stream in self.streams:
            stream._event_ch.send_nowait(event)


class ScriptedVADStream(vad.VADStream):
    async def _main_task(self):
        async for _ in self._input_ch:
            pass


class ControlledAdaptive(rtc.EventEmitter):
    """Feed acoustic verdicts through the SDK's actual overlap/transcript gate."""

    instances = []

    def __init__(self):
        super().__init__()
        self.streams = []
        self.instances.append(self)

    def stream(self):
        stream = ControlledOverlapStream()
        self.streams.append(stream)
        return stream

    def send(self, event):
        for stream in self.streams:
            if not stream.closed:
                stream.events.send_nowait(event)


class ControlledOverlapStream:
    def __init__(self):
        self.events = aio.Chan()
        self.closed = False

    def push_frame(self, frame):
        pass

    def __aiter__(self):
        return self.events.__aiter__()

    async def aclose(self):
        self.closed = True
        self.events.close()


class AudioInput(io.AudioInput):
    def __init__(self):
        super().__init__(label="synthetic input")
        self.frames = aio.Chan()

    async def __anext__(self):
        return await self.frames.__anext__()


class AudioSink(io.AudioOutput):
    """Controllable playout clock; never opens a device or persists PCM."""

    def __init__(self):
        super().__init__(label="memory", capabilities=io.AudioOutputCapabilities(pause=True))
        self.frames = []
        self.played = []
        self.clear_count = 0
        self.paused = False
        self.resume_count = 0
        self.ready = asyncio.Event()
        self.ready.set()
        self.transcript = None
        self._segment = False

    async def capture_frame(self, frame):
        await self.ready.wait()
        await super().capture_frame(frame)
        if not self._segment:
            self._segment = True
            self.on_playback_started(created_at=time.time())
        marker = struct.unpack_from("h", frame.data)[0]
        self.frames.append(marker)
        self.played.append(marker)

    def flush(self):
        super().flush()
        if self._segment:
            self._segment = False
            self.on_playback_finished(playback_position=0.02, interrupted=False)

    def clear_buffer(self):
        self.clear_count += 1
        super().flush()
        if self._segment:
            self._segment = False
            self.on_playback_finished(
                playback_position=0.02, interrupted=True, synchronized_transcript=self.transcript
            )

    def pause(self):
        self.paused = True
        self.ready.clear()

    def resume(self):
        self.paused = False
        self.resume_count += 1
        self.ready.set()


class SyntheticAgent(VoiceAgent):
    def __init__(self, settings, extensions=None):
        super().__init__(session_prompt(settings), settings, extensions or SessionExtensions())
        self.transcripts = aio.Chan()
        self.stt_ready = asyncio.Event()
        self.tts_active = 0
        self.tts_closed = 0
        self.tts_gate = None
        self.markers = {}
        self.audio_delay = 0

    async def stt_node(self, audio, model_settings):
        self.stt_ready.set()
        async for event in self.transcripts:
            yield event

    async def tts_node(self, text, model_settings):
        self.tts_active += 1
        try:
            async for chunk in text:
                if not chunk.strip():
                    continue
                if self.audio_delay:
                    await asyncio.sleep(self.audio_delay)
                marker = self.markers.setdefault(chunk, len(self.markers) + 1)
                yield rtc.AudioFrame(struct.pack("h", marker) * 320, 16000, 1, 320)
                if self.tts_gate is not None:
                    await self.tts_gate.wait()
        finally:
            self.tts_active -= 1
            self.tts_closed += 1


class Harness:
    def __init__(self, settings, extensions=None):
        self.model = ScriptedLLM()
        self.stt = ScriptedSTT()
        self.tts = ScriptedTTS()
        self.vad = ScriptedVAD()
        self.agent = SyntheticAgent(settings, extensions)
        self.sink = AudioSink()
        self.input = AudioInput()
        # Synthetic audio cannot echo. Exercise warmed interruption logic; production
        # retains the SDK's automatic first-speech echo-cancellation warmup (3 s).
        with patch(
            "voiceagent.runtime.AgentSession", partial(AgentSession, aec_warmup_duration=None)
        ):
            self.session = build_session(
                settings, ProviderChain(self.stt, self.model, self.tts), self.vad
            )
        self.session.input.audio = self.input
        self.session.output.audio = self.sink
        self.items = []
        self.false_interruptions = []
        self.session.on("conversation_item_added", lambda ev: self.items.append(ev.item))
        self.session.on("agent_false_interruption", self.false_interruptions.append)

    async def start(self):
        await self.session.start(self.agent, record=False, session_host=False)
        await self.agent.stt_ready.wait()
        await eventually(lambda: self.vad.streams)

    async def close(self):
        await self.session.aclose()
        self.agent.transcripts.close()
        self.input.frames.close()
        await self.model.aclose()
        await self.stt.aclose()
        await self.tts.aclose()

    async def speech_start(self, *, duration=0.7):
        self.vad.send(vad.VADEventType.START_OF_SPEECH)
        self.vad.send(vad.VADEventType.INFERENCE_DONE, duration=duration)
        await asyncio.sleep(0)

    async def speech_end(self):
        self.vad.send(vad.VADEventType.END_OF_SPEECH, duration=0.7)
        await asyncio.sleep(0)

    async def transcript(self, text, *, final=True):
        self.agent.transcripts.send_nowait(
            stt.SpeechEvent(
                type=stt.SpeechEventType.FINAL_TRANSCRIPT
                if final
                else stt.SpeechEventType.INTERIM_TRANSCRIPT,
                alternatives=[stt.SpeechData(language="en", text=text, confidence=1)],
            )
        )
        await asyncio.sleep(0)

    async def turn(self, text):
        await self.speech_start()
        await self.transcript(text)
        await self.speech_end()

    def messages(self, role):
        return [item for item in self.items if getattr(item, "role", None) == role]
