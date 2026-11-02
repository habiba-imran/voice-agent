"""Native session failure policy, isolation and forced-drain cleanup without providers."""

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from livekit.agents import APIStatusError, APITimeoutError, llm, stt, tts
from turn_harness import Harness, Reply, eventually

from voiceagent.lifecycle import SessionLifecycle, failure_details
from voiceagent.settings import Settings


@pytest.mark.parametrize(
    "status,category",
    [
        (401, "authentication"),
        (403, "authentication"),
        (429, "rate_limit"),
        (503, "server"),
        (400, "request"),
    ],
)
def test_failure_details_never_include_payload(status, category):
    error = llm.LLMError(
        timestamp=0,
        label="private",
        recoverable=False,
        error=APIStatusError("private response", status_code=status, body={"api_key": "private"}),
    )
    assert failure_details(error) == {
        "component": "llm_error",
        "category": category,
        "status_code": status,
        "recoverable": False,
    }


async def native_case(component, *, humanization, partial):
    settings = Settings.model_validate(
        {
            "humanization": {"enabled": humanization},
            "listening": {"min_endpoint_delay": 0.02, "max_endpoint_delay": 0.1},
        }
    )
    h = Harness(settings)
    life = SessionLifecycle(h.session, settings)
    h.session.on("close", life.on_close)
    h.session.on("error", life.on_error)
    old = Reply(
        chunks=(f"Only {component}.", "Obsolete continuation."),
        hold=partial,
        before_first=not partial,
    )
    h.model.pending.append(old)
    try:
        await h.start()
        if component == "stt" and not partial:
            await h.speech_start()
            await h.transcript(f"Fact for {component}", final=False)
        else:
            await h.turn(f"Fact for {component}")
            await eventually(old.started.is_set)
        if partial:
            await eventually(lambda: h.sink.played)
        count = len(h.sink.played)
        client, error_class = {
            "stt": (h.stt, stt.STTError),
            "llm": (h.model, llm.LLMError),
            "tts": (h.tts, tts.TTSError),
        }[component]
        client.emit(
            "error",
            error_class(
                timestamp=time.time(),
                label="private-label",
                error=APITimeoutError("private timeout"),
                recoverable=False,
            ),
        )
        async with asyncio.timeout(5):
            await life.closed.wait()
        assert life.reason == "provider_error"
        old.release.set()
        await asyncio.sleep(0)
        assert len(h.sink.played) == count
        assert "Obsolete continuation." not in h.agent.markers
        expected = 0 if component == "stt" and not partial else 1
        assert len(h.model.contexts) == expected
        for context in h.model.contexts:
            text = context.to_dict()
            assert all(
                f"Fact for {other}" not in str(text)
                for other in {"stt", "llm", "tts"} - {component}
            )
    finally:
        await life.close()
        await h.close()
        life.complete()
    assert h.model.active == h.agent.tts_active == 0
    assert all(stream._task.done() for stream in h.vad.streams)


@pytest.mark.parametrize("humanization", [False, True])
@pytest.mark.parametrize("partial", [False, True])
async def test_three_simultaneous_sessions_fail_independently_and_leave_no_tasks(
    humanization, partial
):
    before = asyncio.all_tasks()
    loop = asyncio.get_running_loop()
    unhandled = []
    previous = loop.get_exception_handler()
    loop.set_exception_handler(lambda _loop, context: unhandled.append(context))
    try:
        await asyncio.gather(
            *(
                native_case(component, humanization=humanization, partial=partial)
                for component in ("stt", "llm", "tts")
            )
        )
        await asyncio.sleep(0)
        assert not unhandled
        assert not [task for task in asyncio.all_tasks() - before if not task.done()]
    finally:
        loop.set_exception_handler(previous)


async def test_native_graceful_drain_deadline_interrupts_held_generation():
    settings = Settings.model_validate(
        {
            "listening": {"min_endpoint_delay": 0.02, "max_endpoint_delay": 0.1},
            "runtime": {"drain_timeout_seconds": 0.02},
        }
    )
    h = Harness(settings)
    life = SessionLifecycle(h.session, settings)
    h.session.on("close", life.on_close)
    old = Reply(chunks=("Partial.", "Never replay."), hold=True)
    h.model.pending.append(old)
    try:
        await h.start()
        await h.turn("Question")
        await eventually(lambda: h.sink.played)
        life.stop("session_limit", drain=True)
        life.stop("idle_limit", drain=True)
        async with asyncio.timeout(5):
            await life.closed.wait()
        assert life.reason == "session_limit"
        assert old.closed.is_set() and "Never replay." not in h.agent.markers
    finally:
        await life.close()
        await h.close()
        life.complete()


async def test_cleanup_timeout_is_bounded_and_does_not_claim_success():
    async def stuck():
        await asyncio.Event().wait()

    session = SimpleNamespace(aclose=stuck)
    settings = Settings()
    settings = settings.model_copy(
        update={"runtime": settings.runtime.model_copy(update={"shutdown_timeout_seconds": 0.01})}
    )
    life = SessionLifecycle(session, settings)
    await life.close()
    assert life.reason == "shutdown_timeout"


async def test_recoverable_event_does_not_replay_or_close_session():
    settings = Settings()
    session = SimpleNamespace(shutdown=Mock(), aclose=AsyncMock())
    life = SessionLifecycle(session, settings)
    life.on_error(
        SimpleNamespace(
            error=llm.LLMError(
                timestamp=0, label="synthetic", error=APITimeoutError(), recoverable=True
            )
        )
    )
    session.shutdown.assert_not_called()
    assert life.watchdog is None
    await life.close()
