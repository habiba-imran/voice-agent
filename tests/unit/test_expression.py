"""Text/control contracts only. No claim about subjective or audible qualities."""

import asyncio
from contextlib import aclosing

import pytest
from livekit.agents import llm

from voiceagent.expression import (
    FillerBudget,
    SpeechMarkupGuard,
    delivery_instructions,
    humanize_stream,
    tts_controls,
)
from voiceagent.settings import ConfigurationError, HumanizationSettings, load_settings


async def chunks(values):
    for value in values:
        yield value


async def render(values, budget=None):
    budget = budget or FillerBudget(HumanizationSettings(enabled=True))
    return "".join([item async for item in humanize_stream(chunks(values), budget)])


@pytest.mark.parametrize(
    "text",
    [
        "The value is 3.14159; ID AB_92-x.",
        "https://example.test/api?x=1&unit=mm#part-2",
        "vector<T> and value < 3, x >= 2; arr[limit] = foo_bar.",
        "Actually, the correct date is Thursday.",
        "Well depth is 25 m; humeral head is a technical name.",
        "Café — 東京: a thoughtful answer, with a natural pause.",
        "hmm.example.test is a hostname, and um_id is an identifier.",
        "&lt;= is an escaped comparison; foo<breakpoint> is a type.",
    ],
)
async def test_plain_factual_and_technical_text_is_preserved_at_every_split(text):
    for index in range(len(text) + 1):
        assert await render([text[:index], text[index:]]) == text
    assert await render(list(text)) == text


@pytest.mark.parametrize(
    "tag",
    [
        '<break time="300ms"/>',
        '<emotion value="calm"/>',
        '<speed ratio="1.1"/>',
        '<volume ratio="1.1"/>',
        '<prosody pitch="high">',
        "</prosody>",
        '&lt;emotion value="curious"/&gt;',
        "[laughter]",
        "[sigh]",
    ],
)
async def test_recognized_controls_never_reach_speech_at_any_chunk_boundary(tag):
    for index in range(len(tag) + 1):
        assert await render(["Before ", tag[:index], tag[index:], "after."]) == "Before after."
    assert await render(list("Before " + tag + "after.")) == "Before after."


@pytest.mark.parametrize(
    "text,expected",
    [
        ('<speak><emotion value="calm">Keep 42.</emotion></speak>', "Keep 42."),
        ('Hello <break time="300ms"', "Hello "),
        ('Hello <emotion value="bad"\nSafe tail.', "Hello \nSafe tail."),
        ("A <emotion " + "x" * 10000 + ">B.", "A B."),
        ("A <emo", "A "),
        ("A ", "A "),
        ("", ""),
    ],
)
async def test_malformed_empty_nested_and_oversized_controls_fail_to_plain_text(text, expected):
    assert await render(list(text)) == expected


async def test_filler_budget_spacing_repetition_and_no_injection():
    budget = FillerBudget(HumanizationSettings(enabled=True, filler_cooldown_turns=2))
    assert await render(list("Hmm... Umm... First thought."), budget) == "Hmm, First thought."
    assert await render(["Uh, Second thought."], budget) == "Second thought."
    assert await render(["Um, Third thought."], budget) == "Third thought."
    assert await render(["Hmm, Same filler."], budget) == "Same filler."
    assert await render(["Uh, Different filler."], budget) == "Uh, Different filler."
    assert await render(["A normal statement."], budget) == "A normal statement."


@pytest.mark.parametrize(
    "text,expected",
    [
        ('Hello<break time="300ms"/>world.', "Hello world."),
        ('The result is<emotion value="calm"/>42.', "The result is 42."),
        ("Hello[laughter]world.", "Hello world."),
        ('<emotion value="calm">Hello.</emotion>', "Hello."),
    ],
)
async def test_removed_controls_preserve_word_boundaries_without_duplicate_punctuation(
    text, expected
):
    for index in range(len(text) + 1):
        assert await render([text[:index], text[index:]]) == expected
    assert await render(list(text)) == expected


@pytest.mark.parametrize(
    "overrides",
    [
        {"disfluencies": "off"},
        {"max_leading_fillers_per_turn": 0},
    ],
)
async def test_filler_off_or_zero_limit(overrides):
    budget = FillerBudget(HumanizationSettings(enabled=True, **overrides))
    assert await render(list("Hmm... Uh... The number is 42."), budget) == "The number is 42."


@pytest.mark.parametrize("text", ["Hmm...", "Uh, ", "Umm", "", "   "])
async def test_filler_only_output_does_not_trigger_synthesis(text):
    assert await render(list(text)) == ""


async def test_streaming_emits_before_completion_and_cancellation_drops_partial_tag():
    never = asyncio.Event()
    closed = asyncio.Event()

    async def source():
        try:
            yield "First sentence."
            yield '<emotion value="'
            await never.wait()
            yield 'calm"/>Stale tail.'
        finally:
            closed.set()

    async with aclosing(source()) as stream:
        async with aclosing(
            humanize_stream(stream, FillerBudget(HumanizationSettings()))
        ) as output:
            assert await anext(output) == "First sentence."
            task = asyncio.create_task(anext(output))
            await asyncio.sleep(0)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
    assert closed.is_set()


async def test_chat_chunk_tools_usage_and_input_objects_are_not_corrupted():
    tool = llm.FunctionToolCall(call_id="synthetic", name="generic", arguments='{"count":42}')
    original = llm.ChatChunk(
        id="chunk",
        delta=llm.ChoiceDelta(
            content='<emotion value="calm"/>The count is 42.',
            tool_calls=[tool],
            extra={"reasoning": "not speakable"},
        ),
    )
    usage = llm.ChatChunk(id="usage")
    output = [
        item
        async for item in humanize_stream(
            chunks([original, usage]), FillerBudget(HumanizationSettings())
        )
    ]
    assert output[0].delta.content == "The count is 42."
    assert output[0].delta.tool_calls == [tool]
    assert original.delta.content.startswith("<emotion")
    assert output[1] is usage


async def test_unrecognized_chunk_type_is_rejected_without_payload():
    with pytest.raises(TypeError, match="Unsupported LLM chunk type"):
        await render([object()])


@pytest.mark.parametrize(
    "option",
    [
        {"emotion": "made-up"},
        {"emotion_intensity": 0.5},
        {"pitch": 1.1},
        {"markup": True},
        {"pauses": "ssml"},
        {"laughter": True},
        {"speed": 3},
        {"speed": float("nan")},
        {"volume": 0.1},
        {"default_style": "unknown"},
        {"filler_cooldown_turns": 0},
        {"max_leading_fillers_per_turn": 3},
    ],
)
def test_unsupported_features_and_invalid_values_fail_configuration(project, option):
    with pytest.raises(ConfigurationError):
        load_settings(project_root=project, environ={}, overrides={"humanization": option})


def test_controls_disabled_auto_and_neutral_fallback(project):
    baseline = load_settings(project_root=project, environ={})
    assert tts_controls(baseline) == {"emotion": "neutral", "speed": 1, "volume": 1}
    assert delivery_instructions(baseline.humanization) == ""
    humanized = load_settings(
        project_root=project,
        environ={},
        overrides={
            "humanization": {
                "enabled": True,
                "emotion": "auto",
                "pace": "measured",
            }
        },
    )
    assert tts_controls(humanized) == {"emotion": None, "speed": 0.95, "volume": 1}
    neutral = load_settings(
        project_root=project,
        environ={},
        overrides={
            "humanization": {
                "enabled": True,
                "emotion": "neutral",
                "default_style": "neutral",
                "speed": 1,
                "volume": 1,
                "disfluencies": "off",
            }
        },
    )
    assert tts_controls(neutral) == tts_controls(baseline)
    assert "Do not add optional" in delivery_instructions(neutral.humanization)


def test_guards_keep_bounded_state_without_queues():
    guard = SpeechMarkupGuard()
    guard.feed("<emotion " + "x" * 100000)
    assert guard.pending == "" and len(guard.escaped_end) <= 4
    assert guard.feed(">Still safe.") == "Still safe."


async def test_filler_accounting_is_isolated_between_agents():
    policy = HumanizationSettings(enabled=True)
    first, second = FillerBudget(policy), FillerBudget(policy)
    assert await render(["Hmm, First."], first) == "Hmm, First."
    assert await render(["Hmm, Again."], first) == "Again."
    assert await render(["Hmm, Independent."], second) == "Hmm, Independent."


async def test_tool_only_and_empty_output_cannot_bypass_filler_cooldown():
    budget = FillerBudget(HumanizationSettings(enabled=True, filler_cooldown_turns=2))
    assert await render(["Hmm, First."], budget) == "Hmm, First."
    for _ in range(5):
        async for _ in humanize_stream(chunks([llm.ChatChunk(id="tool-only")]), budget):
            pass
        assert await render([""], budget) == ""
    assert budget.generation == 1
    assert await render(["Um, Too soon."], budget) == "Too soon."


def test_explicit_controls_override_documented_pace_presets(project):
    settings = load_settings(
        project_root=project,
        environ={},
        overrides={
            "humanization": {
                "enabled": True,
                "emotion": "contemplative",
                "pace": "lively",
                "speed": 0.9,
                "volume": 0.95,
            }
        },
    )
    assert tts_controls(settings) == {"emotion": "contemplative", "speed": 0.9, "volume": 0.95}
