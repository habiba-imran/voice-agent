"""Real SDK state transitions with scripted recognition and synthetic PCM; no network."""

import asyncio

import pytest
from turn_harness import ControlledAdaptive, Harness, Reply, eventually

from voiceagent.settings import load_settings


@pytest.fixture
async def harness(project, request):
    overrides = {
        "listening": {"min_endpoint_delay": 0.15, "max_endpoint_delay": 0.45},
        "interruption": {"false_interruption_timeout": 0.15},
    }
    for section, values in getattr(request, "param", {}).items():
        overrides.setdefault(section, {}).update(values)
    settings = load_settings(
        project_root=project,
        environ={},
        overrides={
            **overrides,
        },
    )
    h = Harness(settings)
    tasks_before = asyncio.all_tasks()
    try:
        async with asyncio.timeout(10):
            await h.start()
        yield h
    finally:
        async with asyncio.timeout(10):
            await h.close()
        await asyncio.sleep(0)
        leaked = [
            t
            for t in asyncio.all_tasks() - tasks_before
            if not t.done() and t is not asyncio.current_task()
        ]
        assert not leaked, [(t.get_name(), str(t.get_coro())) for t in leaked]
        assert h.model.active == h.agent.tts_active == 0


@pytest.mark.parametrize("harness", [{}, {"humanization": {"enabled": True}}], indirect=True)
async def test_normal_turn_commits_once_and_streams(harness):
    h = harness
    reply = Reply(chunks=("Hello. ", "A short answer."))
    h.model.pending.append(reply)
    await h.turn("A complete question")
    await eventually(lambda: len(h.messages("assistant")) == 1)
    assert [m.text_content for m in h.messages("user")] == ["A complete question"]
    assert h.messages("assistant")[0].text_content == "Hello. A short answer."
    assert len(h.model.contexts) == 1
    assert h.sink.played == list(h.agent.markers.values())
    assert reply.closed.is_set()


async def test_pause_then_continuation_produces_one_combined_turn(harness):
    h = harness
    h.model.pending.append(Reply())
    await h.turn("I was thinking, um")
    await asyncio.sleep(0.04)
    assert not h.model.contexts
    await h.turn("about Thursday")
    await eventually(lambda: len(h.messages("assistant")) == 1)
    assert [m.text_content for m in h.messages("user")] == ["I was thinking, um about Thursday"]
    assert len(h.model.contexts) == 1


async def test_long_pause_commits_once_and_silence_creates_no_extra_reply(harness):
    h = harness
    h.model.pending.append(Reply())
    await h.turn("A finished thought")
    await eventually(lambda: len(h.messages("assistant")) == 1)
    await asyncio.sleep(0.5)
    assert len(h.model.contexts) == 1
    assert len(h.messages("user")) == 1


@pytest.mark.parametrize("harness", [{}, {"humanization": {"enabled": True}}], indirect=True)
async def test_noise_pauses_then_resumes_same_generation(harness):
    h = harness
    reply = Reply(chunks=("Opening.", "Continued."), hold=True)
    h.model.pending.append(reply)
    handle = h.session.generate_reply(user_input="A long response please")
    await eventually(lambda: h.sink.played)
    await h.speech_start()
    await eventually(lambda: h.sink.paused)
    reply.release.set()
    frames_at_pause = list(h.sink.played)
    await asyncio.sleep(0.025)
    assert h.sink.played == frames_at_pause
    await h.speech_end()  # No STT transcript: noise/abandoned speech, not a committed turn.
    await eventually(lambda: h.false_interruptions)
    async with asyncio.timeout(3):
        await handle
    assert h.false_interruptions[-1].resumed is True
    assert not handle.interrupted
    assert len(h.model.contexts) == 1
    assert h.sink.played == list(h.agent.markers.values())


@pytest.mark.parametrize("during_tts", [False, True])
@pytest.mark.parametrize("harness", [{}, {"humanization": {"enabled": True}}], indirect=True)
async def test_genuine_barge_in_cancels_old_generation_and_preserves_spoken_history(
    harness, during_tts
):
    h = harness
    old = Reply(chunks=("Old opening.", "Never play this old tail."), hold=True)
    new = Reply(chunks=("New answer.",))
    h.model.pending.extend((old, new))
    if during_tts:
        h.agent.tts_gate = asyncio.Event()
    first = h.session.generate_reply(user_input="The old question")
    await eventually(lambda: h.sink.played)
    h.sink.transcript = "Old opening."
    before = list(h.sink.played)
    await h.speech_start()
    await eventually(lambda: h.sink.paused)
    await h.transcript("Wait stop, the new question")
    await h.speech_end()
    await eventually(lambda: old.closed.is_set())
    h.agent.tts_gate = None
    old.release.set()  # An obsolete provider becoming ready must not leak its tail.
    await eventually(lambda: len(h.model.contexts) == 2)
    await eventually(lambda: any("New answer." == m.text_content for m in h.messages("assistant")))
    assert first.interrupted
    assert h.sink.clear_count >= 1
    assert "Never play this old tail." not in h.agent.markers
    assert not set(before).intersection(h.sink.played[len(before) :])
    assert h.messages("assistant")[0].text_content == "Old opening."
    assert h.messages("assistant")[0].interrupted is True
    assert [m.text_content for m in h.messages("user")] == [
        "The old question",
        "Wait stop, the new question",
    ]
    assert len(h.messages("assistant")) == 2
    assert all(
        m.text_content != "Never play this old tail."
        for m in h.model.contexts[-1].items
        if getattr(m, "role", None) == "assistant"
    )


async def test_rapid_interruptions_have_one_current_generation(harness):
    h = harness
    replies = [Reply(chunks=(f"Answer {i}.", "Obsolete tail."), hold=True) for i in range(3)]
    h.model.pending.extend(replies)
    handles = [h.session.generate_reply(user_input="First request")]
    for index in range(2):
        await eventually(replies[index].started.is_set)
        await eventually(lambda index=index: len(h.sink.played) > index)
        await h.turn(f"Correction {index}")
        await eventually(replies[index].closed.is_set)
        await eventually(replies[index + 1].started.is_set)
        assert h.model.active == 1
        replies[index].release.set()
    replies[-1].release.set()
    await eventually(lambda: len(h.messages("assistant")) == 3)
    assert handles[0].interrupted
    assert len(h.model.contexts) == 3
    assert len(h.messages("user")) == 3
    assert [m.interrupted for m in h.messages("assistant")] == [True, True, False]


@pytest.mark.parametrize("release_failure", [False, True])
async def test_shutdown_or_cancellation_at_provider_failure_closes_all_streams(
    harness, release_failure
):
    h = harness
    reply = Reply(chunks=("Partial.", "Unreachable."), hold=True, fail=True)
    h.model.pending.append(reply)
    handle = h.session.generate_reply(user_input="Request")
    await eventually(lambda: h.sink.played)
    if release_failure:
        reply.release.set()
        await eventually(reply.failed.is_set)
        # Cancel after the provider has actually raised, while SDK cleanup settles.
        handle.interrupt()
    async with asyncio.timeout(3):
        await h.session.aclose()
    assert reply.closed.is_set()
    assert h.model.active == h.agent.tts_active == 0
    assert handle.done()


async def test_interruption_before_first_llm_token_never_commits_unspoken_output(harness):
    h = harness
    old = Reply(chunks=("Never spoken.",), before_first=True)
    h.model.pending.extend((old, Reply(chunks=("Latest reply.",))))
    handle = h.session.generate_reply(user_input="Initial request")
    await eventually(old.started.is_set)
    assert not h.sink.played
    await h.turn("Replace that request")
    await eventually(old.closed.is_set)
    old.release.set()
    await eventually(lambda: len(h.messages("assistant")) == 1)
    assert handle.interrupted
    assert h.messages("assistant")[0].text_content == "Latest reply."
    assert "Never spoken." not in h.agent.markers


@pytest.fixture
def controlled_adaptive(monkeypatch):
    from livekit.agents import inference

    ControlledAdaptive.instances = []
    monkeypatch.setattr(inference, "AdaptiveInterruptionDetector", ControlledAdaptive)
    yield ControlledAdaptive
    assert all(s.closed for d in ControlledAdaptive.instances for s in d.streams)


@pytest.mark.parametrize(
    "harness",
    [
        {
            "interruption": {
                "mode": "adaptive",
                "allow_cloud_inference": True,
                "backchannel_boundary": None,
            }
        }
    ],
    indirect=True,
)
@pytest.mark.parametrize("acknowledgment", ["yeah", "hmm", "right"])
async def test_adaptive_backchannel_does_not_replace_reply(
    controlled_adaptive, harness, acknowledgment
):
    from livekit.agents import inference

    h = harness
    reply = Reply(chunks=("Keep speaking.", "Finish."), hold=True)
    h.model.pending.append(reply)
    handle = h.session.generate_reply(user_input="Explain this")
    await eventually(lambda: h.sink.played)
    detector = controlled_adaptive.instances[0]
    await eventually(lambda: detector.streams)
    await h.speech_start(duration=0.1)
    await h.transcript(acknowledgment)
    await h.speech_end()
    detector.send(inference.OverlappingSpeechEvent(is_interruption=False))
    await asyncio.sleep(0.25)
    assert not handle.interrupted
    assert len(h.model.contexts) == 1
    assert len(h.messages("user")) == 1
    reply.release.set()
    async with asyncio.timeout(3):
        await handle
    assert len(h.messages("assistant")) == 1


@pytest.mark.parametrize(
    "harness",
    [
        {
            "interruption": {
                "mode": "adaptive",
                "allow_cloud_inference": True,
                "backchannel_boundary": None,
            }
        }
    ],
    indirect=True,
)
async def test_adaptive_failure_falls_back_to_native_vad(controlled_adaptive, harness):
    from livekit.agents import inference

    h = harness
    old = Reply(chunks=("Old answer.", "Stale."), hold=True)
    h.model.pending.extend((old, Reply(chunks=("Updated.",))))
    handle = h.session.generate_reply(user_input="Question")
    await eventually(lambda: h.sink.played)
    detector = controlled_adaptive.instances[0]
    detector.emit(
        "error",
        inference.InterruptionDetectionError(
            label="offline-fault",
            error=RuntimeError("synthetic"),
            recoverable=False,
        ),
    )
    await h.speech_start()
    await eventually(lambda: h.sink.paused)
    await h.transcript("Stop, corrected question")
    await h.speech_end()
    await eventually(old.closed.is_set)
    await eventually(lambda: len(h.messages("assistant")) == 2)
    assert handle.interrupted
    assert "Stale." not in h.agent.markers
    assert len(h.model.contexts) == 2


@pytest.mark.parametrize("harness", [{"interruption": {"min_words": 2}}], indirect=True)
async def test_word_gate_ignores_one_word_interim_but_accepts_real_correction(harness):
    h = harness
    old = Reply(chunks=("Original.", "Obsolete."), hold=True)
    h.model.pending.extend((old, Reply(chunks=("Corrected.",))))
    handle = h.session.generate_reply(user_input="Question")
    await eventually(lambda: h.sink.played)
    await h.speech_start()
    await h.transcript("yeah", final=False)
    await asyncio.sleep(0.025)
    assert not h.sink.paused
    assert not handle.interrupted
    await h.transcript("Wait change that", final=False)
    # A VAD inference tick rechecks the minimum word gate against the interim text.
    from livekit.agents import vad

    h.vad.send(vad.VADEventType.INFERENCE_DONE, duration=0.7)
    await eventually(lambda: h.sink.paused)
    await h.transcript("Wait change that")
    await h.speech_end()
    await eventually(lambda: len(h.messages("assistant")) == 2)
    assert handle.interrupted


async def test_ten_turns_remain_ordered_without_duplicate_or_unbounded_history(harness):
    h = harness
    for index in range(10):
        h.model.pending.append(Reply(chunks=(f"Reply {index}.",)))
        await h.turn(f"Request {index}")
        await eventually(lambda index=index: len(h.messages("assistant")) == index + 1)
    assert [m.text_content for m in h.messages("user")] == [f"Request {i}" for i in range(10)]
    assert [m.text_content for m in h.messages("assistant")] == [f"Reply {i}." for i in range(10)]
    assert len(h.model.contexts) == 10
    assert all(len(ctx.items) <= 25 for ctx in h.model.contexts)


@pytest.mark.parametrize(
    "harness",
    [
        {
            "stt": {"model": "flux-general-en"},
            "listening": {"turn_detection": "stt"},
        }
    ],
    indirect=True,
)
async def test_flux_waits_for_provider_eot_and_does_not_commit_on_vad_silence(harness):
    from livekit.agents import stt

    h = harness
    h.model.pending.append(Reply(chunks=("Flux response.",)))
    await h.turn("Provider has not ended this turn")
    await asyncio.sleep(0.2)
    assert not h.model.contexts
    h.agent.transcripts.send_nowait(stt.SpeechEvent(type=stt.SpeechEventType.END_OF_SPEECH))
    await eventually(lambda: len(h.messages("assistant")) == 1)
    await asyncio.sleep(0.05)
    assert len(h.model.contexts) == len(h.messages("user")) == 1


@pytest.fixture
def controlled_eot(monkeypatch):
    from livekit.agents.inference.eot import transports

    class EOT:
        probability = 0.0
        calls = 0

        def predict(self, pcm):
            type(self).calls += 1
            return self.probability

    monkeypatch.setattr(transports, "_EOT", EOT)
    return EOT


@pytest.mark.parametrize("harness", [{"listening": {"turn_detection": "semantic"}}], indirect=True)
@pytest.mark.parametrize("continue_turn", [True, False])
async def test_semantic_negative_eot_waits_for_continuation_or_max_delay(
    controlled_eot, harness, continue_turn
):
    from livekit.agents import vad

    h = harness
    h.model.pending.append(Reply())
    await h.speech_start()
    await h.transcript("Let me think, um")
    # Real native streaming detector plumbing, with only its CPU probability scripted.
    h.vad.send(vad.VADEventType.INFERENCE_DONE, silence=0.3)
    await eventually(lambda: controlled_eot.calls >= 1)
    await h.speech_end()
    await asyncio.sleep(0.2)  # Beyond min_delay but below max_delay.
    assert not h.model.contexts
    if continue_turn:
        controlled_eot.probability = 1.0
        await h.speech_start()
        await h.transcript("Thursday works")
        h.vad.send(vad.VADEventType.INFERENCE_DONE, silence=0.3)
        await eventually(lambda: controlled_eot.calls >= 2)
        await h.speech_end()
    await eventually(lambda: len(h.messages("assistant")) == 1)
    expected = "Let me think, um Thursday works" if continue_turn else "Let me think, um"
    assert [m.text_content for m in h.messages("user")] == [expected]
    assert len(h.model.contexts) == 1


@pytest.mark.parametrize("harness", [{"humanization": {"enabled": True}}], indirect=True)
async def test_interruption_mid_delivery_tag_closes_guard_and_prevents_stale_output(harness):
    h = harness
    old = Reply(chunks=('Kept sentence. <emotion value="', 'calm"/>Obsolete.'), hold=True)
    h.model.pending.extend((old, Reply(chunks=("Current reply.",))))
    handle = h.session.generate_reply(user_input="First request")
    await eventually(lambda: h.sink.played)
    h.sink.transcript = "Kept sentence."
    await h.turn("Stop, replace that")
    await eventually(old.closed.is_set)
    old.release.set()
    await eventually(lambda: len(h.messages("assistant")) == 2)
    assert handle.interrupted
    assert h.messages("assistant")[0].text_content.rstrip() == "Kept sentence."
    assert h.messages("assistant")[1].text_content == "Current reply."
    assert all("emotion" not in text and "Obsolete" not in text for text in h.agent.markers)
