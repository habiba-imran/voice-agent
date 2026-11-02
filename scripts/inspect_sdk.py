"""Print public SDK compatibility evidence without contacting providers."""

import inspect
from importlib.metadata import PackageNotFoundError, version

from livekit import agents
from livekit.agents import cli, inference, room_io
from livekit.agents.llm.chat_context import Instructions, MetricsReport
from livekit.agents.metrics import LLMMetrics, STTMetrics, TTSMetrics
from livekit.agents.voice import io
from livekit.agents.voice.run_result import ChatMessageAssert, RunAssert
from livekit.agents.voice.speech_handle import SpeechHandle
from livekit.plugins import cartesia, deepgram, groq, silero

for name in (
    "livekit-agents",
    "livekit-plugins-deepgram",
    "livekit-plugins-groq",
    "livekit-plugins-cartesia",
    "livekit-plugins-silero",
    "livekit-plugins-turn-detector",
    "pydantic",
    "pytest",
    "pytest-asyncio",
    "ruff",
):
    try:
        print(f"{name}=={version(name)}")
    except PackageNotFoundError:
        print(f"{name}: NOT INSTALLED")

for target in (
    agents.AgentServer,
    agents.AgentServer.rtc_session,
    agents.AgentServer.run,
    agents.AgentServer.drain,
    agents.AgentServer.aclose,
    agents.AgentSession,
    agents.AgentSession.start,
    agents.AgentSession.aclose,
    agents.AgentSession.shutdown,
    agents.APIConnectOptions,
    room_io.RoomOptions,
    agents.AgentSession.interrupt,
    agents.AgentSession.generate_reply,
    agents.AgentSession.say,
    agents.RunContext.wait_for_playout,
    agents.JobContext.wait_for_participant,
    agents.function_tool,
    agents.AgentSession.run,
    RunAssert.next_event,
    RunAssert.no_more_events,
    ChatMessageAssert.event,
    SpeechHandle.interrupt,
    SpeechHandle.wait_for_playout,
    SpeechHandle.add_done_callback,
    SpeechHandle.remove_done_callback,
    Instructions,
    agents.Agent.on_user_turn_completed,
    inference.TurnDetector,
    inference.AdaptiveInterruptionDetector,
    io.AudioOutput,
    io.AudioOutput.pause,
    io.AudioOutput.resume,
    io.AudioOutput.clear_buffer,
    agents.Agent,
    cli.run_app,
    deepgram.STT,
    deepgram.STTv2,
    groq.LLM,
    cartesia.TTS,
    cartesia.TTS.update_options,
    cartesia.TTS.stream,
    cartesia.TTS.aclose,
    agents.Agent.default.tts_node,
    silero.VAD.load,
):
    print(f"\n{target.__module__}.{target.__qualname__}{inspect.signature(target)}")

for name in (
    "TurnHandlingOptions",
    "InterruptionOptions",
    "EndpointingOptions",
    "PreemptiveGenerationOptions",
):
    target = getattr(agents, name, None)
    print(f"\n{name}: {getattr(target, '__annotations__', 'not exported')}")

for target in (MetricsReport, LLMMetrics, STTMetrics, TTSMetrics):
    print(f"\n{target.__name__}: {target.__annotations__}")
