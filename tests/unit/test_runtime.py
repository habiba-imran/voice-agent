from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from voiceagent import runtime
from voiceagent.hooks import SessionExtensions
from voiceagent.prompts import session_prompt
from voiceagent.providers import ProviderChain


def test_session_uses_explicit_direct_clients_and_local_vad(settings, monkeypatch):
    constructor = Mock()
    monkeypatch.setattr(runtime, "AgentSession", constructor)
    chain = ProviderChain(object(), object(), object())
    vad = object()
    runtime.build_session(settings, chain, vad)
    options = constructor.call_args.kwargs
    assert options["stt"] is chain.stt and options["llm"] is chain.llm
    assert options["tts"] is chain.tts and options["vad"] is vad
    assert options["expressive"] is False
    assert options["conn_options"].llm_conn_options.max_retry == 0
    assert options["turn_handling"]["turn_detection"] == "vad"
    assert not options["turn_handling"]["preemptive_generation"]["enabled"]


@pytest.mark.parametrize("failure", [False, True])
async def test_job_cleanup_normal_and_start_failure(settings, monkeypatch, failure):
    events, cleanup = {}, []
    fake_session = SimpleNamespace(
        aclose=AsyncMock(),
        say=Mock(),
        shutdown=Mock(),
    )

    def on(name, callback=None):
        def attach(function):
            events[name] = function
            return function

        return attach(callback) if callback else attach

    fake_session.on = on
    fake_session.start = AsyncMock(
        side_effect=RuntimeError("private-synthetic") if failure else None
    )
    monkeypatch.setattr(runtime, "build_session", Mock(return_value=fake_session))

    @asynccontextmanager
    async def chain(_settings):
        try:
            yield ProviderChain(object(), object(), object())
        finally:
            cleanup.append("providers_closed")

    monkeypatch.setattr(runtime, "provider_chain", chain)
    callbacks = []

    async def connect():
        events["close"](SimpleNamespace(reason="participant_disconnected"))

    ctx = SimpleNamespace(
        proc=SimpleNamespace(userdata={"voiceagent_vad": object()}),
        room=object(),
        connect=AsyncMock(side_effect=connect),
        shutdown=Mock(),
        add_shutdown_callback=callbacks.append,
    )
    await runtime.run_session(ctx, settings=settings)
    fake_session.aclose.assert_awaited_once()
    assert cleanup == ["providers_closed"]
    options = fake_session.start.call_args.kwargs
    assert options["record"] is False and options["session_host"] is False
    assert ctx.shutdown.call_args.kwargs["reason"] == (
        "session_failure" if failure else "participant_disconnected"
    )
    assert len(callbacks) == 1


async def test_duration_limit_requests_graceful_drain():
    stop = Mock()
    await runtime.stop_after(0.001, stop)
    stop.assert_called_once_with("session_limit", drain=True)


async def test_llm_cancellation_closes_provider_stream(settings):
    from livekit.agents import APIConnectOptions, llm

    entered, closed = asyncio.Event(), asyncio.Event()

    async def tokens():
        entered.set()
        await asyncio.Event().wait()
        yield "unreachable"

    @asynccontextmanager
    async def chat(**kwargs):
        try:
            yield tokens()
        finally:
            closed.set()

    class TestAgent(runtime.VoiceAgent):
        @property
        def session(self):
            return SimpleNamespace(
                llm=SimpleNamespace(chat=chat),
                conn_options=SimpleNamespace(llm_conn_options=APIConnectOptions(max_retry=0)),
            )

    agent = TestAgent(session_prompt(settings), settings, SessionExtensions())

    async def consume():
        async for _ in agent.llm_node(llm.ChatContext(), [], None):
            pass

    task = asyncio.create_task(consume())
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert closed.is_set()


async def test_llm_node_bounds_history_and_drops_no_stream_chunks(settings):
    from livekit.agents import APIConnectOptions, llm
    from livekit.agents.voice.agent import ModelSettings

    observed = {}

    class Stream:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            observed["closed"] = True

        async def __aiter__(self):
            yield "first "
            await asyncio.sleep(0)
            yield "second"

    class FakeModel:
        def chat(self, **kwargs):
            observed["chat"] = kwargs
            return Stream()

    session = SimpleNamespace(
        llm=FakeModel(),
        conn_options=SimpleNamespace(llm_conn_options=APIConnectOptions(max_retry=0)),
    )

    class TestAgent(runtime.VoiceAgent):
        @property
        def session(self):
            return session

    agent = TestAgent(session_prompt(settings), settings, SessionExtensions())
    context = llm.ChatContext()
    context.add_message(role="system", content="static policy")
    for index in range(40):
        context.add_message(role="user", content=f"synthetic {index}")
    output = [chunk async for chunk in agent.llm_node(context, [], ModelSettings())]
    assert output == ["first ", "second"]
    assert observed["closed"]
    assert len(context.items) <= settings.llm.history_messages + 2
    assert context.items[0].text_content == "static policy"
    assert observed["chat"]["extra_kwargs"] == {"extra_body": {"include_reasoning": False}}


def test_prompt_prefix_and_session_metadata_are_isolated(settings):
    prompt = session_prompt(settings)
    first = runtime.VoiceAgent(prompt, settings, SessionExtensions(metadata={"topic": "alpha"}))
    second = runtime.VoiceAgent(prompt, settings, SessionExtensions(metadata={"topic": "beta"}))
    assert first.instructions.startswith(prompt.text)
    assert second.instructions.startswith(prompt.text)
    assert "alpha" not in second.instructions
    assert "beta" not in first.instructions


def test_server_registers_configured_dispatch_without_provider_construction(settings, monkeypatch):
    server = Mock()
    factory = Mock(return_value=server)
    monkeypatch.setattr(runtime, "AgentServer", factory)
    assert runtime.build_server(settings) is server
    assert server.rtc_session.call_args.kwargs["agent_name"] == "voiceagent"
    assert callable(factory.call_args.kwargs["setup_fnc"])
