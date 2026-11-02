"""Entrypoint failure/stop races with local event emitters, no Room or provider access."""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from livekit import rtc
from livekit.agents import APIStatusError, llm
from turn_harness import eventually

from voiceagent import runtime
from voiceagent.providers import ProviderChain


@pytest.mark.parametrize(
    "mode",
    [
        "disconnect",
        "room_disconnect",
        "connect_error",
        "start_timeout",
        "connect_timeout",
        "idle",
        "duration",
        "provider_error",
        "job_shutdown",
        "cancel_start",
        "cancel_active",
    ],
)
async def test_entrypoint_closes_once_under_start_stop_and_disconnect_races(
    settings, monkeypatch, caplog, mode
):
    settings = settings.model_copy(
        update={
            "runtime": settings.runtime.model_copy(
                update={
                    "startup_timeout_seconds": 0.1,
                    "max_session_seconds": 0.04,
                    "drain_timeout_seconds": 0.01,
                    "shutdown_timeout_seconds": 0.1,
                }
            )
        }
    )
    ready = asyncio.Event()
    cleanup, callbacks = [], []
    before = asyncio.all_tasks()

    class Session(rtc.EventEmitter):
        def __init__(self):
            super().__init__()
            self.close_count = 0
            self.shutdown_calls = []
            self.current_speech = None
            self.say = Mock()

        async def start(self, agent, **options):
            self.options = options
            assert options["record"] is False and options["session_host"] is False
            assert options["room_options"].close_on_disconnect is True
            assert options["room_options"].delete_room_on_close is False
            if mode in {"start_timeout", "cancel_start"}:
                ready.set()
                await asyncio.Event().wait()

        def shutdown(self, **options):
            self.shutdown_calls.append(options)
            self.emit("close", SimpleNamespace(reason="user_initiated"))

        async def aclose(self):
            self.close_count += 1
            self.emit("close", SimpleNamespace(reason="user_initiated"))

    session = Session()
    monkeypatch.setattr(runtime, "build_session", lambda *_: session)

    @asynccontextmanager
    async def chain(_settings):
        try:
            yield ProviderChain(object(), object(), object())
        finally:
            cleanup.append("closed")

    monkeypatch.setattr(runtime, "provider_chain", chain)

    async def connect():
        ready.set()
        if mode == "connect_error":
            raise ConnectionError("private connection data")
        if mode == "connect_timeout":
            await asyncio.Event().wait()

    ctx = SimpleNamespace(
        proc=SimpleNamespace(userdata={"voiceagent_vad": object()}),
        room=rtc.EventEmitter(),
        connect=connect,
        shutdown=Mock(),
        add_shutdown_callback=callbacks.append,
    )
    task = asyncio.create_task(runtime.run_session(ctx, settings=settings))
    async with asyncio.timeout(2):
        await ready.wait()
    if mode == "disconnect":
        session.emit("close", SimpleNamespace(reason="participant_disconnected"))
    elif mode == "room_disconnect":
        ctx.room.emit("reconnecting")  # Transient reconnect must not duplicate greetings or stop.
        assert not session.shutdown_calls
        ctx.room.emit("disconnected", rtc.DisconnectReason.UNKNOWN_REASON)
    elif mode == "idle":
        session.emit("user_state_changed", SimpleNamespace(old_state="listening", new_state="away"))
    elif mode == "provider_error":
        error = llm.LLMError(
            timestamp=0,
            label="private label",
            recoverable=False,
            error=APIStatusError("private body", status_code=429),
        )
        session.emit("error", SimpleNamespace(error=error))
        session.emit("error", SimpleNamespace(error=error))
    elif mode == "job_shutdown":
        await callbacks[0]()
    elif mode in {"cancel_start", "cancel_active"}:
        task.cancel()
    if mode.startswith("cancel_"):
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        async with asyncio.timeout(2):
            await task
    expected = {
        "disconnect": "participant_disconnected",
        "room_disconnect": "room_disconnected",
        "idle": "idle_limit",
        "duration": "session_limit",
        "provider_error": "provider_error",
        "job_shutdown": "job_shutdown",
        "start_timeout": "startup_timeout",
        "connect_timeout": "startup_timeout",
        "connect_error": "session_failure",
        "cancel_start": "cancelled",
        "cancel_active": "cancelled",
    }[mode]
    ctx.shutdown.assert_called_once_with(reason=expected)
    assert session.close_count == 1 and cleanup == ["closed"]
    assert len(session.shutdown_calls) <= 1
    await callbacks[0]()  # SDK may invoke the job callback again after entrypoint completion.
    assert session.close_count == 1
    assert "private" not in caplog.text
    await asyncio.sleep(0)
    assert not [item for item in asyncio.all_tasks() - before if not item.done()]


@pytest.mark.parametrize("mode", ["input_limit", "request_limit"])
async def test_operational_input_and_request_caps_stop_before_new_provider_call(mode):
    from turn_harness import Harness, Reply

    from voiceagent.lifecycle import SessionLifecycle
    from voiceagent.settings import Settings

    settings = Settings.model_validate(
        {
            "limits": {"max_llm_requests": 1, "max_input_bytes": 128},
            "listening": {"min_endpoint_delay": 0.02, "max_endpoint_delay": 0.1},
        }
    )
    h = Harness(settings)
    life = SessionLifecycle(h.session, settings)
    h.agent.lifecycle = life
    h.session.on("close", life.on_close)
    try:
        await h.start()
        if mode == "request_limit":
            h.model.pending.append(Reply())
            await h.turn("First request")
            await eventually(lambda: len(h.messages("assistant")) == 1)
        await h.turn("x" * 129 if mode == "input_limit" else "Second request")
        async with asyncio.timeout(5):
            await life.closed.wait()
        assert life.reason == mode
        assert len(h.model.contexts) == (0 if mode == "input_limit" else 1)
    finally:
        await life.close()
        await h.close()
        life.complete()
