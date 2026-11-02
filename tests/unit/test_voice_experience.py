"""Offline host opt-ins, real SDK speech lifecycle, no provider requests."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pathspec
import pytest
from turn_harness import Harness, Reply, eventually

from voiceagent.conversation import explicit_ending_intent
from voiceagent.playback import PLAYBACK_READY_ATTRIBUTE, ClientPlaybackReady, prime_playback
from voiceagent.settings import PROJECT_ROOT, ConfigurationError, Settings, load_settings


@pytest.mark.parametrize(
    "text",
    [
        "Goodbye.",
        "Bye.",
        "That's all, thanks.",
        "I don't want to know anything else.",
        "I don't want to know anything more",
        "No more questions.",
        "I'm done.",
        "You can end the call.",
        "Thanks, bye.",
        "Okay, that's it.",
        "Thank you, goodbye.",
        "Goodbye, I don't want to know anything more.",
        "Thanks, that's all. Goodbye.",
        "That’s all, thank you. Goodbye!",
        "Please end the call.",
        "I need to go now.",
    ],
)
def test_complete_exit_utterances(text):
    assert explicit_ending_intent(text)


@pytest.mark.parametrize(
    "text",
    [
        "What does goodbye mean?",
        "She said goodbye.",
        'Say "bye"',
        "'bye'",
        '"Goodbye"',
        "Don't end the call.",
        "Please don't end the call.",
        "I'm not done.",
        "I'm done with that project; what about another?",
        "No more questions about that, but what are her skills?",
        "Bye, but first answer this.",
        "Thanks for explaining.",
        "Thanks.",
        "Okay.",
        "If I say bye, what happens?",
        "Can you explain 'no more questions'?",
        "goodbye is a word",
        "That's all?",
        "Did she say goodbye?",
        "I don't want you to end the call",
    ],
)
def test_mentions_negations_quotes_and_continuations_do_not_hang_up(text):
    assert not explicit_ending_intent(text)


def configured(**updates):
    return Settings.model_validate(
        {
            "ending": {
                "enabled": True,
                "detect_explicit": True,
                "farewell": "Thanks for chatting!",
            },
            "listening": {"min_endpoint_delay": 0.02, "max_endpoint_delay": 0.1},
            **updates,
        }
    )


@pytest.mark.parametrize(
    "text", ["Bye.", "That's all, thanks.", "I don't want to know anything more."]
)
async def test_native_completed_turn_ends_without_a_model_call_after_static_playout(text):
    h = Harness(configured())
    closed = asyncio.Event()
    gate = asyncio.Event()
    h.agent.tts_gate = gate
    model_chat = Mock(side_effect=AssertionError("An explicit exit must not invoke an LLM"))
    h.model.chat = model_chat
    h.session.on("close", lambda _: closed.set())
    try:
        await h.start()
        await h.turn(text)
        await eventually(lambda: h.sink.played)
        assert not closed.is_set()  # Farewell stream is still held before native flush.
        assert "Thanks for chatting!".startswith("".join(h.agent.markers))
        model_chat.assert_not_called()
        gate.set()
        await asyncio.wait_for(closed.wait(), 3)
        model_chat.assert_not_called()
        assert h.agent.control._ending_result.result() is True
    finally:
        gate.set()
        await h.close()


async def test_native_question_with_goodbye_word_still_uses_normal_conversation():
    h = Harness(configured())
    h.model.pending.append(Reply())
    try:
        await h.start()
        await h.turn("What does goodbye mean?")
        await eventually(lambda: h.messages("assistant"))
        assert len(h.model.contexts) == 1
        assert not h.agent.control._ending_result
    finally:
        await h.close()


async def test_native_static_greeting_and_silent_readiness_probe_make_zero_llm_calls():
    h = Harness(
        configured(greeting={"mode": "custom", "text": "Hello, from a reusable assistant."})
    )
    h.model.chat = Mock(side_effect=AssertionError("No LLM on opening"))
    try:
        await h.start()
        await prime_playback(h.session)
        assert h.agent.markers == {}  # Preprovided silent PCM bypasses the TTS node as well.
        assert h.messages("assistant") == []
        handle = await h.agent.control.greet()
        await handle.wait_for_playout()
        assert "".join(h.agent.markers) == "Hello, from a reusable assistant."
        await h.agent.control.greet()  # Reconnect callbacks must never replay it.
        assert h.agent.tts_closed == 1
        h.model.chat.assert_not_called()
    finally:
        await h.close()


class Room:
    def __init__(self):
        self.listeners = {}

    def on(self, name, callback):
        self.listeners[name] = callback

    def off(self, name, callback):
        assert self.listeners.pop(name) == callback


async def test_playback_acknowledgement_is_linked_to_room_member_and_detaches():
    room = Room()
    participant = SimpleNamespace(identity="synthetic-visitor", attributes={})
    gate = ClientPlaybackReady(room)
    before = asyncio.all_tasks()
    task = asyncio.create_task(gate.wait(participant, asyncio.Event()))
    await asyncio.sleep(0)
    callback = room.listeners["participant_attributes_changed"]
    callback(
        {}, SimpleNamespace(identity="someone-else", attributes={PLAYBACK_READY_ATTRIBUTE: "true"})
    )
    callback({}, participant)
    await asyncio.sleep(0)
    assert not task.done()
    participant.attributes[PLAYBACK_READY_ATTRIBUTE] = "true"
    callback({}, participant)
    await asyncio.wait_for(task, 1)
    gate.close()
    assert room.listeners == {}
    assert not [t for t in asyncio.all_tasks() - before if not t.done()]


@pytest.mark.parametrize("cause", ["already_ready", "room_closed", "timeout"])
async def test_playback_wait_races_never_leak_tasks(cause):
    room = Room()
    gate = ClientPlaybackReady(room)
    participant = SimpleNamespace(identity="synthetic-visitor", attributes={})
    closed = asyncio.Event()
    if cause == "already_ready":
        participant.attributes[PLAYBACK_READY_ATTRIBUTE] = "true"
    elif cause == "room_closed":
        closed.set()
    before = asyncio.all_tasks()
    try:
        async with asyncio.timeout(0.05 if cause == "timeout" else 1):
            await gate.wait(participant, closed)
        assert cause != "timeout"
    except TimeoutError:
        assert cause == "timeout"
    finally:
        gate.close()
    assert not [t for t in asyncio.all_tasks() - before if not t.done()]


@pytest.mark.parametrize(
    "payload",
    [
        {"greeting": {"wait_for_playback_ready": True}},
        {"ending": {"detect_explicit": True}},
        {"ending": {"enabled": True, "detect_explicit": True}, "latency": {"preemptive_llm": True}},
    ],
)
def test_invalid_cost_or_readiness_profiles_fail_closed(payload):
    with pytest.raises(ValueError):
        Settings.model_validate(payload)


def test_host_overlay_stays_public_portable_and_below_env_overrides(project):
    host = project / "customization" / "host"
    host.mkdir(parents=True)
    (host / "prompt.md").write_text("A synthetic public profile.")
    (host / "agent.yaml").write_text(
        json.dumps(
            {
                "prompt_path": "customization/host/prompt.md",
                "greeting": {
                    "mode": "custom",
                    "text": "Static welcome.",
                    "wait_for_playback_ready": True,
                },
                "ending": {"enabled": True, "detect_explicit": True},
            }
        )
    )
    settings = load_settings(
        project_root=project, environ={"VOICEAGENT_GREETING__TEXT": "Env welcome."}
    )
    assert settings.opening.text == "Env welcome."
    assert settings.opening.wait_for_playback_ready
    assert settings.ending.detect_explicit
    assert settings.prompt_path == host / "prompt.md"
    from voiceagent.prompts import session_prompt

    assert session_prompt(settings).text == "A synthetic public profile."
    assert settings.stt.model == "nova-3"  # Base tuning not discarded by a partial overlay.


@pytest.mark.parametrize("content", ['{"credentials": {}}', "[]", "bad: [", "a" * 65537])
def test_private_invalid_or_oversized_host_overlay_is_rejected(project, content):
    host = project / "customization" / "host"
    host.mkdir(parents=True)
    (host / "agent.yaml").write_text(content)
    with pytest.raises(ConfigurationError):
        load_settings(project_root=project, environ={})


def test_only_two_public_host_assets_enter_image_and_neither_enters_reusable_git():
    docker = pathspec.GitIgnoreSpec.from_lines(
        (PROJECT_ROOT / ".dockerignore").read_text().splitlines()
    )
    git = pathspec.GitIgnoreSpec.from_lines((PROJECT_ROOT / ".gitignore").read_text().splitlines())
    for name in ("agent.yaml", "prompt.md"):
        assert not docker.match_file("customization/host/" + name)
        assert git.match_file("customization/host/" + name)
    for name in (".env.local", "secret.json", "livekit.toml", "audio.wav", "nested/prompt.md"):
        assert docker.match_file("customization/host/" + name)
        assert git.match_file("customization/host/" + name)


@pytest.mark.parametrize("ready", [True, False])
async def test_entrypoint_waits_for_client_playback_before_greeting_and_bounds_missing_ack(
    settings, monkeypatch, ready
):
    from contextlib import asynccontextmanager
    from unittest.mock import AsyncMock

    from voiceagent import runtime
    from voiceagent.providers import ProviderChain

    events = {}
    session = SimpleNamespace(
        say=Mock(),
        generate_reply=Mock(),
        start=AsyncMock(),
        aclose=AsyncMock(),
        shutdown=Mock(),
        input=SimpleNamespace(set_audio_enabled=Mock()),
    )

    def on(name, callback=None):
        def attach(fn):
            events.setdefault(name, []).append(fn)
            return fn

        return attach(callback) if callback else attach

    session.on = on
    session.off = lambda name, fn: events[name].remove(fn)
    room = Room()
    participant = SimpleNamespace(identity="synthetic-visitor", attributes={})
    ctx = SimpleNamespace(
        proc=SimpleNamespace(userdata={"voiceagent_vad": object()}),
        room=room,
        connect=AsyncMock(),
        wait_for_participant=AsyncMock(return_value=participant),
        shutdown=Mock(),
        add_shutdown_callback=Mock(),
    )
    configured = settings.model_copy(
        update={
            "greeting": settings.greeting.model_copy(
                update={
                    "mode": "custom",
                    "text": "Exact opening.",
                    "wait_for_playback_ready": True,
                }
            ),
            "runtime": settings.runtime.model_copy(
                update={"startup_timeout_seconds": 1 if ready else 0.2}
            ),
        }
    )

    @asynccontextmanager
    async def chain(_settings):
        yield ProviderChain(object(), object(), object())

    monkeypatch.setattr(runtime, "provider_chain", chain)
    monkeypatch.setattr(runtime, "build_session", lambda *_args: session)
    probe = AsyncMock()
    monkeypatch.setattr(runtime, "prime_playback", probe)
    task = asyncio.create_task(runtime.run_session(ctx, settings=configured))
    try:
        await eventually(lambda: probe.await_count == 1)
        session.input.set_audio_enabled.assert_called_once_with(False)
        session.say.assert_not_called()
        if ready:
            callback = room.listeners["participant_attributes_changed"]
            callback(
                {}, SimpleNamespace(identity="other", attributes={PLAYBACK_READY_ATTRIBUTE: "true"})
            )
            await asyncio.sleep(0)
            session.say.assert_not_called()
            participant.attributes[PLAYBACK_READY_ATTRIBUTE] = "true"
            callback({}, participant)
            await eventually(lambda: session.say.called)
            session.say.assert_called_once_with("Exact opening.", allow_interruptions=True)
            assert session.input.set_audio_enabled.call_args.args == (True,)
            callback({}, participant)  # Repeated/reconnect acknowledgement never re-greets.
            for callback in events["close"]:
                callback(SimpleNamespace(reason="participant_disconnected"))
        await asyncio.wait_for(task, 2)
        session.generate_reply.assert_not_called()
        assert session.say.call_count == int(ready)
        assert room.listeners == {}
        session.aclose.assert_awaited_once()
        ctx.shutdown.assert_called_once_with(
            reason="participant_disconnected" if ready else "startup_timeout"
        )
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_native_deterministic_farewell_yields_to_a_new_user_turn():
    h = Harness(configured())
    gate = asyncio.Event()
    closed = asyncio.Event()
    h.agent.tts_gate = gate
    h.model.pending.append(Reply(chunks=("Let's continue.",)))
    h.session.on("close", lambda _: closed.set())
    try:
        await h.start()
        await h.turn("Bye.")
        await eventually(lambda: h.sink.played)
        activity = h.agent.control.user_activity
        await h.speech_start()
        await eventually(lambda: h.agent.control.user_activity > activity)
        await h.transcript("Wait, let's keep talking.")
        await h.speech_end()
        gate.set()
        await eventually(
            lambda: any(m.text_content == "Let's continue." for m in h.messages("assistant"))
        )
        assert not closed.is_set()
        assert len(h.model.contexts) == 1  # The bye turn did not call the model.
        assert h.model.contexts[0].items[-1].text_content == "Wait, let's keep talking."
    finally:
        gate.set()
        await h.close()


async def test_native_deterministic_farewell_stall_still_closes_without_model_call():
    settings = configured()
    settings = settings.model_copy(
        update={"ending": settings.ending.model_copy(update={"timeout_seconds": 0.2})}
    )
    h = Harness(settings)
    gate = asyncio.Event()
    h.agent.tts_gate = gate
    h.model.chat = Mock(side_effect=AssertionError("No LLM for an explicit exit"))
    closed = asyncio.Event()
    h.session.on("close", lambda _: closed.set())
    try:
        await h.start()
        await h.turn("That's all, thanks.")
        await asyncio.wait_for(closed.wait(), 3)
        h.model.chat.assert_not_called()
        assert h.agent.control._ending_result.result() is True
    finally:
        gate.set()
        await h.close()


async def test_native_static_host_knowledge_stays_in_requests_and_followup_context(tmp_path):
    # Scripted replies prove request construction/context, not any real model's factual accuracy.
    prompt = tmp_path / "public-prompt.md"
    facts = {
        "person": "Example Person",
        "skills": ["Python"],
        "project": "Atlas",
        "experience": "API development",
    }
    prompt.write_text(
        "You are an assistant, not the person. Use third person. Say when a detail is unknown.\n"
        + json.dumps(facts)
    )
    h = Harness(configured(prompt_path=prompt))
    turns = [
        ("Who is this person?", "Example Person builds software."),
        ("What are their skills?", "They use Python."),
        ("What projects have they built?", "Their project is Atlas."),
        ("Tell me more about that project.", "Atlas is the documented project."),
        ("Tell me about their experience.", "They develop APIs."),
        ("What's their favorite movie?", "I don't have that specific detail."),
    ]
    try:
        await h.start()
        for index, (question, reply) in enumerate(turns):
            h.model.pending.append(Reply(chunks=(reply,)))
            await h.turn(question)
            await eventually(lambda index=index: len(h.messages("assistant")) == index + 1)
        assert len(h.model.contexts) == len(turns)
        for index, context in enumerate(h.model.contexts):
            wire, _ = context.to_provider_format("openai")
            assert json.dumps(facts) in wire[0]["content"]
            assert wire[0]["content"].count(json.dumps(facts)) == 1
            assert context.items[-1].text_content == turns[index][0]
        followup = h.model.contexts[3]
        assert any(
            getattr(m, "text_content", "") == "Their project is Atlas." for m in followup.items
        )
    finally:
        await h.close()
