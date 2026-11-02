"""Supported SDK run/assertion API, with local scripted providers and no LLM judge."""

import asyncio

import pytest
from turn_harness import Harness, Reply, eventually

from voiceagent.settings import Settings


@pytest.mark.parametrize("humanization", [False, True])
async def test_native_run_results_keep_multiturn_corrections_and_one_reply(humanization):
    settings = Settings.model_validate({"humanization": {"enabled": humanization}})
    h = Harness(settings)
    before = asyncio.all_tasks()
    turns = (
        ("Remember the chosen day is Tuesday.", "The chosen day is Tuesday."),
        ("Correction: use Thursday instead.", "The chosen day is now Thursday."),
        ("Which day did I choose?", "You chose Thursday."),
    )
    try:
        await h.start()
        for question, answer in turns:
            h.model.pending.append(Reply(chunks=(answer,)))
            async with asyncio.timeout(3):
                result = await h.session.run(user_input=question, output_options=None)
            message = result.expect.next_event().is_message(role="assistant").event().item
            assert message.text_content == answer
            assert not message.interrupted
            result.expect.no_more_events()
        assert len(h.model.contexts) == len(turns)
        users = [
            item.text_content
            for item in h.model.contexts[-1].items
            if getattr(item, "role", None) == "user"
        ]
        assert users == [question for question, _ in turns]
        # A fake response is not evidence that Groq understands a correction. This verifies
        # the exact context supplied to it and public SDK output/event ordering.
    finally:
        await h.close()
    await asyncio.sleep(0)
    assert not [task for task in asyncio.all_tasks() - before if not task.done()]


@pytest.mark.parametrize("humanization", [False, True])
async def test_native_pending_run_interruption_cannot_emit_obsolete_tail(humanization):
    settings = Settings.model_validate(
        {
            "humanization": {"enabled": humanization},
            "listening": {"min_endpoint_delay": 0.02, "max_endpoint_delay": 0.1},
        }
    )
    h = Harness(settings)
    old = Reply(chunks=("Old opening.", "Obsolete unspoken tail."), hold=True)
    h.model.pending.extend((old, Reply(chunks=("Current answer.",))))
    try:
        await h.start()
        result = h.session.run(user_input="Old request", output_options=None)
        await eventually(lambda: h.sink.played)
        h.sink.transcript = "Old opening."
        await h.turn("Wait, use the correction.")
        await eventually(old.closed.is_set)
        old.release.set()
        await eventually(lambda: len(h.messages("assistant")) == 2)
        async with asyncio.timeout(3):
            await result
        message = result.expect.next_event().is_message(role="assistant").event().item
        assert message.interrupted and message.text_content.rstrip() == "Old opening."
        assert h.messages("assistant")[-1].text_content == "Current answer."
        assert "Obsolete unspoken tail." not in h.agent.markers
        assert len(h.model.contexts) == 2
    finally:
        await h.close()
