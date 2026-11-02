"""Select one native LiveKit turn detector; never maintain competing turn state."""

from livekit.agents import TurnHandlingOptions, inference
from livekit.plugins import silero

from .settings import Settings


def load_vad(settings: Settings):
    return silero.VAD.load(**settings.listening.vad.model_dump())


def prewarm_detector(settings: Settings) -> None:
    if settings.listening.turn_detection == "semantic":
        from livekit.local_inference import init_eot

        # Bundled native CPU weights; idempotent, with no model download or provider request.
        init_eot()


def load_models(settings: Settings):
    prewarm_detector(settings)
    return load_vad(settings)


def turn_options(settings: Settings) -> TurnHandlingOptions:
    listening, interruption = settings.listening, settings.interruption
    detector = listening.turn_detection
    if detector == "semantic":
        # Pin the local CPU model; auto-selection could enable Cloud inference in dev mode.
        detector = inference.TurnDetector(version="v1-mini")
    options: TurnHandlingOptions = {
        "turn_detection": detector,
        "interruption": interruption.model_dump(exclude={"allow_cloud_inference"}),
        "preemptive_generation": {
            "enabled": settings.latency.preemptive_llm,
            "preemptive_tts": False,
        },
    }
    # STTv2 owns EOT. The SDK otherwise adds its default 0.5 s endpoint wait.
    # Zero only that redundant wait; VAD still handles barge-in.
    if listening.turn_detection == "stt":
        options["endpointing"] = {"mode": "fixed", "min_delay": 0.0, "max_delay": 0.0}
    else:
        options["endpointing"] = {
            "mode": listening.endpointing_mode,
            "min_delay": listening.min_endpoint_delay,
            "max_delay": listening.max_endpoint_delay,
            "alpha": listening.endpointing_alpha,
        }
    return options
