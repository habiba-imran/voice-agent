"""Controlled text A/B, not generated language or a listening evaluation."""

import re

from voiceagent.expression import FillerBudget, delivery_instructions, humanize_stream, tts_controls
from voiceagent.settings import Settings

PREFIX = re.compile(r"^(?:hmm|umm|um|uh)[,.\s]+", re.IGNORECASE)


async def evaluate_delivery():
    body = "The value is 42.5, and the identifier is AB_92-x. Visit https://example.test/a?b=1."
    results = []
    for enabled in (False, True):
        settings = Settings.model_validate({"humanization": {"enabled": enabled}})
        budget = FillerBudget(settings.humanization)
        positions = []
        for index in range(12):
            text = ("Hmm, ", "Uh, ", "Um, ")[index % 3] + body

            async def source(text=text):
                for char in text:
                    yield char

            output = humanize_stream(source(), budget) if enabled else source()
            rendered = "".join([chunk async for chunk in output])
            assert PREFIX.sub("", rendered) == body
            if PREFIX.match(rendered):
                positions.append(index)
        if enabled:
            assert all(
                second - first >= 4 for first, second in zip(positions, positions[1:], strict=False)
            )
        results.append(
            {
                "humanization": enabled,
                "origin": "scripted_text_transform_only",
                "generations": 12,
                "filler_prefixes": len(positions),
                "filler_generation_indices": positions,
                "substantive_text_preserved": True,
                "punctuation_preserved": True,
                "tts_controls": tts_controls(settings),
                "stable_delivery_policy": bool(delivery_instructions(settings.humanization)),
                "provider_requests": 0,
                "token_usage": None,
                "listening_score": None,
            }
        )
    return results
