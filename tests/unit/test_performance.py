import asyncio
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from livekit import rtc
from livekit.agents import APIStatusError, APITimeoutError
from livekit.agents.metrics import LLMMetrics
from turn_harness import AudioSink, Harness, Reply, eventually

from voiceagent.hooks import SessionExtensions
from voiceagent.performance import ObservedAudioOutput, PerformanceObserver, distribution
from voiceagent.settings import load_settings


def test_percentiles_are_defined_and_empty_is_not_zero():
    assert distribution([]) == {"sample_count": 0, "p50": None, "p95": None}
    assert distribution([1]) == {"sample_count": 1, "p50": 1, "p95": 1}
    assert distribution([0, 10]) == {"sample_count": 2, "p50": 5, "p95": 9.5}


def test_window_is_bounded_and_invalid_or_negative_values_are_not_samples(settings):
    observer = PerformanceObserver(settings)
    for i in range(1000):
        observer.sample("sdk_llm_ttft_s", i)
    for invalid in (float("nan"), float("inf"), -1, True, None, "secret"):
        observer.sample("sdk_llm_ttft_s", invalid)
    observer.sample("arbitrary-injected-name", 1)
    report = observer.report()
    assert report["metrics"]["sdk_llm_ttft_s/observed"]["sample_count"] == 256
    assert report["metrics"]["sdk_llm_ttft_s/observed"]["total_count"] == 1000
    assert len(observer.series) == 1
    assert report["caller_heard_latency"] is None and report["retry_attempt_count"] is None


class Handle:
    def __init__(self, *, scheduled=True):
        self.id = "opaque-speech"
        self.scheduled = scheduled
        self.interrupted = False
        self.callbacks = []

    def add_done_callback(self, callback):
        self.callbacks.append(callback)

    def remove_done_callback(self, callback):
        self.callbacks.remove(callback)


def test_monotonic_eot_frame_and_completion_have_exact_correlation(settings):
    now = [10.0]
    log = Mock()
    observer = PerformanceObserver(settings, clock=lambda: now[0], logger=log)
    handle = Handle()
    observer.session = SimpleNamespace(current_speech=handle)
    observer.end_of_turn()
    now[0] = 10.1
    observer.speech_created(SimpleNamespace(speech_handle=handle))
    now[0] = 10.3
    observer.frame_accepted(handle)
    now[0] = 99
    observer.frame_accepted(handle)  # Second frame cannot overwrite the first.
    now[0] = 10.9
    observer.speech_done(handle)
    observer.speech_done(handle)  # Duplicate completion ignored.
    report = observer.report()
    assert report["metrics"]["eot_hook_to_sink_accept_s/completed"]["p50"] == pytest.approx(0.3)
    assert report["metrics"]["eot_hook_to_handle_done_s/completed"]["p50"] == pytest.approx(0.9)
    assert report["counts"]["speech_completed"] == 1
    assert "opaque-speech" not in str(log.mock_calls)


def test_errors_and_cache_preserve_unknowns_without_payloads(settings):
    log = Mock()
    observer = PerformanceObserver(settings, logger=log)
    for error in (
        APIStatusError("private request body", status_code=429),
        APITimeoutError("secret"),
    ):
        observer.error(SimpleNamespace(error=SimpleNamespace(error=error, recoverable=True)))
    for cached in (0, 5):
        observer.metric(
            SimpleNamespace(
                metrics=LLMMetrics(
                    label="private-provider-label",
                    request_id="opaque-request",
                    timestamp=1,
                    duration=0.4,
                    ttft=0.1,
                    cancelled=False,
                    completion_tokens=3,
                    prompt_tokens=10,
                    prompt_cached_tokens=cached,
                    total_tokens=13,
                    tokens_per_second=10,
                )
            )
        )
    report = observer.report()
    assert report["counts"]["provider_timeouts"] == 1
    assert report["counts"]["recoverable_error_events"] == 2
    assert report["counts"]["cache_reporting_unknown_or_zero"] == 1
    assert report["sdk_usage_totals"] == {
        "prompt_tokens": 20,
        "completion_tokens": 6,
        "positive_cached_tokens": 5,
    }
    assert "private" not in str(log.mock_calls) and "secret" not in str(log.mock_calls)
    assert "opaque-request" not in str(log.mock_calls)
    observer.item_added(
        SimpleNamespace(
            item=SimpleNamespace(
                id="id",
                role="assistant",
                interrupted=False,
                content="private conversation",
                metrics={"tts_node_ttfb": 0.2, "e2e_latency": 0.8, "transcript": "secret"},
            )
        )
    )
    assert "conversation" not in str(log.mock_calls)


async def test_output_wrapper_delegates_audio_pause_clear_and_completion(settings):
    observer = PerformanceObserver(settings)
    handle = Handle()
    observer.session = SimpleNamespace(current_speech=handle)
    observer.speech_created(SimpleNamespace(speech_handle=handle))
    sink = AudioSink()
    output = ObservedAudioOutput(sink, observer)
    events = []
    output.on("playback_finished", events.append)
    output.pause()
    assert sink.paused and output.can_pause
    output.resume()
    frame = rtc.AudioFrame(bytes(640), 16000, 1, 320)
    await output.capture_frame(frame)
    output.clear_buffer()
    output.flush()
    assert sink.clear_count == 1 and len(sink.frames) == 1
    assert events and events[0].interrupted


@pytest.mark.parametrize("humanization", [False, True])
async def test_native_sessions_with_observer_preserve_streaming_recovery_and_cleanup(
    project, humanization
):
    settings = load_settings(
        project_root=project,
        environ={},
        overrides={
            "humanization": {"enabled": humanization},
            "listening": {"min_endpoint_delay": 0.1, "max_endpoint_delay": 0.4},
            "interruption": {"false_interruption_timeout": 0.1},
        },
    )
    before = asyncio.all_tasks()
    h = Harness(settings)
    observer = PerformanceObserver(settings, origin="synthetic_native_session")
    h.agent.performance = observer
    observer.attach(h.session)
    try:
        await h.start()
        observer.wrap_output()
        old = Reply(chunks=("Old.", "Stale."), hold=True)
        h.model.pending.extend((old, Reply(chunks=("New.",))))
        await h.turn("Initial question")
        await eventually(lambda: h.sink.played)
        await h.turn("Replace it")
        await eventually(old.closed.is_set)
        old.release.set()
        await eventually(lambda: len(h.messages("assistant")) == 2)
        await eventually(lambda: not observer.active)
        report = observer.report()
        assert report["counts"]["speech_interrupted"] == 1
        assert report["counts"]["speech_completed"] == 1
        assert "eot_hook_to_sink_accept_s/completed" in report["metrics"]
        assert "Stale." not in h.agent.markers
        assert "Initial question" not in json.dumps(report)
    finally:
        await h.close()
        observer.detach()
    await asyncio.sleep(0)
    assert not [
        task
        for task in asyncio.all_tasks() - before
        if not task.done() and task is not asyncio.current_task()
    ]


async def test_ten_turn_native_prefix_and_metadata_survive_bounded_request_history(project):
    settings = load_settings(
        project_root=project,
        environ={},
        overrides={
            "llm": {"history_messages": 4},
            "listening": {"min_endpoint_delay": 0.02, "max_endpoint_delay": 0.1},
        },
    )
    h = Harness(settings, SessionExtensions(metadata={"topic": "synthetic-session-data"}))
    try:
        await h.start()
        prefix = h.agent.instructions.render_static()
        for index in range(10):
            h.model.pending.append(Reply(chunks=(f"Answer {index}.",)))
            await h.turn(f"Question {index}")
            await eventually(lambda index=index: len(h.messages("assistant")) == index + 1)
        assert len(h.model.contexts) == 10
        for index, context in enumerate(h.model.contexts):
            instructions = [
                item for item in context.items if getattr(item, "role", None) == "system"
            ]
            assert len(instructions) == 2
            assert instructions[0].text_content == prefix
            assert "synthetic-session-data" in instructions[1].text_content
            assert len(context.items) <= 6  # four recent items plus static/dynamic instructions
            assert context.items[-1].text_content == f"Question {index}"
            wire, _ = context.to_provider_format("openai")
            # Groq's installed serializer merges dynamic instructions back into this message;
            # static tokens still precede all variable data, with no duplicate instruction.
            assert wire[0]["content"].startswith(prefix)
            assert wire[0]["content"].count(prefix) == 1
            assert "synthetic-session-data" in wire[0]["content"]
            assert len(wire) <= 5
    finally:
        await h.close()


async def test_frame_identity_survives_downstream_backpressure_and_turn_change(settings):
    observer = PerformanceObserver(settings)
    old, new = Handle(), Handle()
    old.id, new.id = "old", "new"
    observer.session = SimpleNamespace(current_speech=old)
    for handle in (old, new):
        observer.speech_created(SimpleNamespace(speech_handle=handle))
    sink = AudioSink()
    sink.ready.clear()
    output = ObservedAudioOutput(sink, observer)
    task = asyncio.create_task(output.capture_frame(rtc.AudioFrame(bytes(640), 16000, 1, 320)))
    await asyncio.sleep(0)
    observer.session.current_speech = new
    sink.ready.set()
    await task
    assert observer.active["old"]["first_frame"] is not None
    assert observer.active["new"]["first_frame"] is None
    observer.detach()
