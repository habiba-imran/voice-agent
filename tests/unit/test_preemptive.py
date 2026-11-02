"""Native speculative LLM adoption/cancellation; speculative TTS stays disabled."""

import asyncio

import pytest
from livekit.agents import stt
from turn_harness import Harness, Reply, eventually

from voiceagent.performance import PerformanceObserver
from voiceagent.settings import Settings


@pytest.mark.parametrize("humanization", [False, True])
@pytest.mark.parametrize("corrected", [False, True])
async def test_speculative_adoption_or_stale_cancellation_without_early_audio(
    humanization, corrected
):
    settings = Settings.model_validate(
        {
            "latency": {"preemptive_llm": True},
            "humanization": {"enabled": humanization},
            "listening": {"min_endpoint_delay": 0.02, "max_endpoint_delay": 0.1},
        }
    )
    tasks_before = asyncio.all_tasks()
    h = Harness(settings)
    observer = PerformanceObserver(settings)
    observer.attach(h.session)
    h.agent.performance = observer
    original = Reply(chunks=("Initial answer.", "Obsolete tail."), hold=True)
    h.model.pending.append(original)
    try:
        await h.start()
        observer.wrap_output()
        await h.speech_start()
        h.agent.transcripts.send_nowait(
            stt.SpeechEvent(
                type=stt.SpeechEventType.PREFLIGHT_TRANSCRIPT,
                alternatives=[stt.SpeechData(language="en", text="Initial request", confidence=1)],
            )
        )
        await eventually(original.started.is_set)
        # The native LLM has yielded its first chunk; no TTS or output before commitment.
        await asyncio.sleep(0.02)
        assert not h.sink.frames and not h.agent.markers and h.agent.tts_active == 0
        if corrected:
            await h.transcript("Corrected request", final=False)
            await eventually(original.closed.is_set)
            h.model.pending.append(Reply(chunks=("Corrected answer.",)))
        await h.transcript("Corrected request" if corrected else "Initial request")
        await h.speech_end()
        original.release.set()
        await eventually(lambda: len(h.messages("assistant")) == 1)
        await eventually(lambda: not observer.active)
        assert len(h.model.contexts) == (2 if corrected else 1)
        assert len(h.messages("user")) == 1
        if corrected:
            assert h.messages("assistant")[0].text_content == "Corrected answer."
            assert "Obsolete tail." not in h.agent.markers
            assert observer.report()["counts"]["speech_cancelled"] == 1
            assert h.model.contexts[-1].items[-1].text_content == "Corrected request"
        else:
            assert h.messages("assistant")[0].text_content == "Initial answer.Obsolete tail."
        assert observer.report()["counts"]["speech_completed"] == 1
    finally:
        await h.close()
        observer.detach()
    await asyncio.sleep(0)
    assert h.model.active == h.agent.tts_active == 0
    assert not [task for task in asyncio.all_tasks() - tasks_before if not task.done()]
