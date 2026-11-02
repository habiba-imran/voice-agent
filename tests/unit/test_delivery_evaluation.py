import pytest
from delivery_evaluation import evaluate_delivery

from voiceagent.expression import STYLE_GUIDANCE, delivery_instructions
from voiceagent.settings import HumanizationSettings


async def test_identical_text_ab_preserves_facts_pauses_and_filler_cooldown():
    baseline, humanized = await evaluate_delivery()
    assert baseline["filler_prefixes"] == 12
    assert humanized["filler_prefixes"] == 3
    assert baseline["tts_controls"]["emotion"] == "neutral"
    assert humanized["tts_controls"]["emotion"] is None
    assert baseline["listening_score"] is humanized["listening_score"] is None
    assert baseline["provider_requests"] == humanized["provider_requests"] == 0


@pytest.mark.parametrize("style", sorted(STYLE_GUIDANCE))
def test_each_supported_style_has_stable_contextual_policy_without_active_markup(style):
    policy = HumanizationSettings(enabled=True, default_style=style)
    instructions = delivery_instructions(policy)
    assert STYLE_GUIDANCE[style] in instructions
    assert instructions == delivery_instructions(policy)
    assert "Plain spoken text only" in instructions
    assert "never fabricate" in instructions
    assert "<emotion" not in instructions
