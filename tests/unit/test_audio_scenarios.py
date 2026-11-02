"""Signal reproducibility/plumbing only: no speech recognition, prosody or acoustic scores."""

import asyncio
import hashlib
import math
import struct

import pytest
from audio_fixtures import catalog, frames
from turn_harness import Harness, Reply, eventually

from voiceagent.settings import Settings


@pytest.mark.parametrize("scenario", catalog()["scenarios"], ids=lambda value: value["id"])
def test_signal_fixture_is_repeatable_bounded_and_framed(scenario):
    first = list(frames(scenario))
    raw = b"".join(frame.data for frame in first)
    assert (
        hashlib.sha256(raw).digest()
        == hashlib.sha256(b"".join(frame.data for frame in frames(scenario))).digest()
    )
    assert len(first) * 20 == sum(item["duration_ms"] for item in scenario["segments"])
    assert all(frame.sample_rate == 16000 and frame.samples_per_channel == 320 for frame in first)
    assert all(abs(value) <= 5000 for value in struct.unpack(f"<{len(raw) // 2}h", raw))
    assert (not any(raw)) if scenario["id"] == "silence" else any(raw)


@pytest.mark.parametrize("humanization", [False, True])
async def test_signal_feed_with_scripted_recognition_retains_rapid_followup_order(humanization):
    settings = Settings.model_validate(
        {
            "humanization": {"enabled": humanization},
            "listening": {"min_endpoint_delay": 0.02, "max_endpoint_delay": 0.1},
        }
    )
    h = Harness(settings)
    try:
        await h.start()
        for scenario in catalog()["scenarios"]:
            for frame in frames(scenario):
                h.input.frames.send_nowait(frame)
            await asyncio.sleep(0)
        # Input is genuine generated PCM, but VAD/STT verdicts below are SCRIPTED.
        for index in range(3):
            h.model.pending.append(Reply(chunks=(f"Answer {index}.",)))
            await h.turn(f"Rapid request {index}")
            await eventually(lambda index=index: len(h.messages("assistant")) == index + 1)
        assert len(h.model.contexts) == 3
        assert [item.text_content for item in h.messages("user")] == [
            f"Rapid request {index}" for index in range(3)
        ]
    finally:
        await h.close()
    assert h.model.active == h.agent.tts_active == 0


@pytest.mark.integration
async def test_actual_local_silero_accepts_generated_pcm_without_provider_or_device():
    from livekit.agents.vad import VADEventType
    from livekit.plugins import silero

    before = asyncio.all_tasks()
    model = silero.VAD.load(force_cpu=True)
    # This is real CPU model inference over synthetic signals, not scripted VAD verdicts.
    for scenario in (catalog()["scenarios"][0], catalog()["scenarios"][2]):
        stream = model.stream()
        try:
            for frame in frames(scenario):
                stream.push_frame(frame)
            stream.end_input()
            async with asyncio.timeout(10):
                events = [event async for event in stream]
            predictions = [event for event in events if event.type == VADEventType.INFERENCE_DONE]
            assert predictions
            assert all(
                math.isfinite(event.probability) and 0 <= event.probability <= 1
                for event in predictions
            )
        finally:
            await stream.aclose()
    await asyncio.sleep(0)
    assert not [task for task in asyncio.all_tasks() - before if not task.done()]
