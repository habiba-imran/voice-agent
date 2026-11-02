"""Exercise the installed native mini binary, not acoustic speech accuracy."""

import asyncio
import math

import pytest
from livekit import rtc
from livekit.agents import inference


@pytest.mark.integration
async def test_local_mini_predicts_synthetic_silence_without_cloud():
    detector = inference.TurnDetector(version="v1-mini")
    assert detector.model == "turn-detector-v1-mini"
    stream = detector.stream()
    try:
        stream.push_audio(rtc.AudioFrame(bytes(38400), 16000, 1, 19200))
        # Let the actual SDK drain the PCM channel before requesting a prediction.
        await asyncio.sleep(0.01)
        event = await asyncio.wait_for(stream.predict(), timeout=10)
        assert event.type == "eot_prediction"
        assert math.isfinite(event.end_of_turn_probability)
        assert 0 <= event.end_of_turn_probability <= 1
        assert stream.model == "turn-detector-v1-mini"
    finally:
        await stream.aclose()
