import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from livekit.agents import llm
from turn_harness import Harness, eventually

from voiceagent.conversation import SessionControl, explicit_ending_intent
from voiceagent.hooks import HookError, SessionExtensions, prepare_extensions
from voiceagent.prompts import session_prompt
from voiceagent.runtime import VoiceAgent
from voiceagent.settings import Settings


class Handle:
    def __init__(self):
        self.finished = asyncio.Event()
        self.interrupted = False

    def done(self):
        return self.finished.is_set()

    def interrupt(self, *, force):
        self.interrupted = True
        self.finished.set()

    async def wait_for_playout(self):
        await self.finished.wait()


def control_for(settings, **ending):
    handle = Handle()
    session = SimpleNamespace(
        say=Mock(return_value=handle), generate_reply=Mock(return_value=handle), shutdown=Mock()
    )
    settings = settings.model_copy(update={"ending": settings.ending.model_copy(update=ending)})
    return SessionControl(session, settings), handle


@pytest.mark.parametrize("mode", ["user_first", "custom", "dynamic"])
async def test_greeting_once_and_static_has_no_llm_call(settings, mode):
    greeting = settings.greeting.model_copy(
        update={"mode": mode, "text": "Exact." if mode == "custom" else None}
    )
    control, _ = control_for(settings.model_copy(update={"greeting": greeting}))
    await asyncio.gather(control.greet(), control.greet(), control.greet())
    assert control.session.say.call_count == (mode == "custom")
    assert control.session.generate_reply.call_count == (mode == "dynamic")
    if mode == "custom":
        control.session.say.assert_called_once_with("Exact.", allow_interruptions=True)


async def test_greeting_skipped_when_user_already_started_or_closed(settings):
    settings = settings.model_copy(
        update={"greeting": settings.greeting.model_copy(update={"mode": "dynamic"})}
    )
    for closed in (False, True):
        control, _ = control_for(settings)
        if closed:
            await control.aclose()
        else:
            control.user_started = True
        await control.greet()
        control.session.generate_reply.assert_not_called()


@pytest.mark.parametrize("mode", ["custom", "generated", "none"])
async def test_ending_waits_and_is_idempotent(settings, mode):
    control, handle = control_for(settings, farewell_mode=mode)
    tasks = [asyncio.create_task(control.request_end()) for _ in range(3)]
    await asyncio.sleep(0)
    if mode != "none":
        assert not control.session.shutdown.called
        handle.finished.set()
    assert await asyncio.gather(*tasks) == [True, True, True]
    control.session.shutdown.assert_called_once_with(drain=False)
    assert control.session.generate_reply.call_count == (mode == "generated")
    await control.aclose()


@pytest.mark.parametrize("cause", ["interruption", "cancellation", "timeout", "close"])
async def test_pending_ending_does_not_leak_or_ignore_user_interruption(settings, cause):
    control, handle = control_for(settings, timeout_seconds=0.02)
    before = asyncio.all_tasks()
    task = asyncio.create_task(control.request_end())
    await eventually(lambda: control.session.say.called)
    if cause == "interruption":
        handle.interrupt(force=True)
        assert await task is False
    elif cause == "cancellation":
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert handle.interrupted
    elif cause == "close":
        await control.aclose()
        assert await task is False
    else:
        assert await task is True
        assert handle.interrupted
    assert control.session.shutdown.call_count == (cause == "timeout")
    await control.aclose()
    assert not [task for task in asyncio.all_tasks() - before if not task.done()]


@pytest.mark.parametrize("failure", ["playout_error", "timeout"])
async def test_new_user_activity_prevents_shutdown_even_when_playout_fails(settings, failure):
    control, handle = control_for(settings, timeout_seconds=0.02)

    async def failed_playout():
        control.note_user_activity()
        if failure == "playout_error":
            raise RuntimeError("synthetic interrupted playout")
        await asyncio.Event().wait()

    handle.wait_for_playout = failed_playout
    assert await control.request_end() is False
    control.session.shutdown.assert_not_called()
    assert handle.interrupted
    await control.aclose()


@pytest.mark.parametrize("text", ["bye", "Goodbye!", "Please end the call.", "I need to go now."])
def test_conservative_explicit_ending_intent(text):
    assert explicit_ending_intent(text)


@pytest.mark.parametrize(
    "text",
    [
        "She said bye",
        "Don't end the call",
        "What does bye mean?",
        'Say "bye"',
        "goodbye is a word",
        "bye, but first answer this",
    ],
)
def test_casual_or_negated_goodbye_is_not_an_end_request(text):
    assert not explicit_ending_intent(text)


async def test_tool_requires_confirmation_and_real_intent_and_uses_context_playout(settings):
    control, handle = control_for(settings)
    context = SimpleNamespace(wait_for_playout=AsyncMock())
    assert "Not ended" in await control.end_from_tool(context, True, "She said bye")
    assert "Not ended" in await control.end_from_tool(context, False, "bye")
    handle.finished.set()
    assert await control.end_from_tool(context, True, "bye") == "Session ended."
    context.wait_for_playout.assert_awaited_once()


async def test_native_sdk_tool_farewell_plays_before_shutdown_without_circular_wait():
    settings = Settings.model_validate({"ending": {"enabled": True}})
    h = Harness(settings)
    closed = asyncio.Event()
    calls = []

    @asynccontextmanager
    async def chat(**kwargs):
        calls.append(kwargs)

        async def chunks():
            yield llm.ChatChunk(
                id="synthetic",
                delta=llm.ChoiceDelta(
                    role="assistant",
                    tool_calls=[
                        llm.FunctionToolCall(
                            name="end_session",
                            arguments='{"confirmed": true}',
                            call_id="synthetic-call",
                        )
                    ],
                ),
            )

        yield chunks()

    h.model.chat = chat
    h.session.on("close", lambda _: closed.set())
    try:
        await h.start()
        h.session.generate_reply(user_input="bye")
        await asyncio.wait_for(closed.wait(), timeout=3)
        assert "".join(h.agent.markers) == "Goodbye!"
        assert len(calls) == 1  # Static farewell never adds an LLM round trip.
    finally:
        await h.close()


def test_identity_ending_and_session_context_keep_instruction_boundaries(settings):
    configured = settings.model_copy(
        update={
            "identity": settings.identity.model_copy(update={"name": "Example Agent"}),
            "ending": settings.ending.model_copy(update={"enabled": True}),
        }
    )
    agent = VoiceAgent(
        session_prompt(configured),
        configured,
        SessionExtensions(metadata={"topic": "synthetic context"}),
    )
    assert "Example Agent" in agent.instructions.render_static()
    assert "synthetic context" in agent.instructions.dynamic
    assert len(agent.tools) == 1


async def test_async_callable_ending_policy_is_rejected():
    class AsyncPolicy:
        async def __call__(self, _text):
            return True

    async def hook():
        return SessionExtensions(ending_policy=AsyncPolicy())

    with pytest.raises(HookError):
        await prepare_extensions(hook)


async def test_host_policy_can_extend_intent_but_must_return_a_boolean(settings):
    control, handle = control_for(settings)
    handle.finished.set()
    control.ending_policy = lambda _: "truthy is not authorization"
    context = SimpleNamespace(wait_for_playout=AsyncMock())
    assert "Not ended" in await control.end_from_tool(context, True, "custom phrase")
    control.ending_policy = lambda text: text == "custom phrase"
    assert await control.end_from_tool(context, True, "custom phrase") == "Session ended."


async def test_native_barge_in_cancels_farewell_and_does_not_end_the_conversation():
    settings = Settings.model_validate(
        {
            "ending": {"enabled": True},
            "listening": {"min_endpoint_delay": 0.02, "max_endpoint_delay": 0.1},
        }
    )
    h = Harness(settings)
    closed = asyncio.Event()
    gate = asyncio.Event()
    h.agent.tts_gate = gate
    requests = []

    @asynccontextmanager
    async def chat(**kwargs):
        user = next(
            item
            for item in reversed(kwargs["chat_ctx"].items)
            if getattr(item, "role", None) == "user"
        )
        requests.append(user.text_content)

        async def chunks():
            if user.text_content == "bye":
                yield llm.ChatChunk(
                    id="synthetic",
                    delta=llm.ChoiceDelta(
                        role="assistant",
                        tool_calls=[
                            llm.FunctionToolCall(
                                name="end_session", arguments='{"confirmed":true}', call_id="end"
                            )
                        ],
                    ),
                )
            else:
                yield "Let's continue."

        yield chunks()

    h.model.chat = chat
    h.session.on("close", lambda _: closed.set())
    try:
        await h.start()
        h.session.generate_reply(user_input="bye")
        await eventually(lambda: h.sink.played)
        before_activity = h.agent.control.user_activity
        await h.speech_start()
        # Wait until the native SDK actually observes the injected VAD event before releasing
        # its held TTS generator. Merely enqueueing an event is not an acoustic interruption.
        await eventually(lambda: h.agent.control.user_activity > before_activity)
        await h.transcript("Wait, let's keep talking.")
        await h.speech_end()
        gate.set()
        await eventually(
            lambda: any(item.text_content == "Let's continue." for item in h.messages("assistant"))
        )
        assert not closed.is_set()
        assert requests.count("bye") == 1
    finally:
        gate.set()
        await h.close()
