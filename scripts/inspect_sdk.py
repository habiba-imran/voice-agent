"""Print public SDK compatibility evidence without contacting providers."""

import inspect
from importlib.metadata import PackageNotFoundError, version

from livekit import agents
from livekit.agents import cli
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
    agents.AgentSession,
    agents.AgentSession.start,
    agents.AgentSession.aclose,
    agents.Agent,
    cli.run_app,
    deepgram.STT,
    deepgram.STTv2,
    groq.LLM,
    cartesia.TTS,
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
