"""Optional direct-provider delivery policy and bounded, per-generation text guards.

No active SSML, emotion classifier, timers, tasks, audio buffers or extra requests.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterable

from livekit.agents import llm

from .settings import HumanizationSettings, Settings

STYLE_GUIDANCE = {
    "neutral": "Use a clear, measured professional tone.",
    "conversational": "Use relaxed, attentive conversational phrasing and varied openings.",
    "reassuring": "Be calm and supportive without promising outcomes you cannot verify.",
    "thoughtful": "Explain one thought at a time, using short clauses and natural punctuation.",
    "curious": "Show interest through relevant questions, at most one at a time.",
    "enthusiastic": "Use restrained enthusiasm when the content warrants it; avoid hype.",
}


def delivery_instructions(policy: HumanizationSettings) -> str:
    if not policy.enabled:
        return ""
    fillers = (
        f"A brief leading hmm, uh or um is optional, at most once in a reply and only when "
        f"thoughtful hesitation fits. Leave at least {policy.filler_cooldown_turns} intervening "
        "replies; never repeat the same hesitation on successive occasions. Do not put fillers "
        "inside explanations, identifiers, numbers or URLs. Prefer saying nothing extra."
        if policy.disfluencies == "contextual" and policy.max_leading_fillers_per_turn
        else "Do not add optional hmm, uh, um or other hesitation fillers."
    )
    return (
        "\n\nDelivery policy:\n" + STYLE_GUIDANCE[policy.default_style] + " "
        "Match phrasing to context: curious for exploration, thoughtful for complexity, "
        "sympathetic for difficulty, restrained excitement for good news. Stay factual. "
        "Use contractions, short clauses, commas and periods for rhythm; no forced pauses. "
        "Correct an actual mistake briefly; never fabricate a mistake to sound human. "
        + fillers
        + " Plain spoken text only: no delivery tags, stage directions or laughter."
    )


def tts_controls(settings: Settings) -> dict:
    """Static stream guidance. Auto omits emotion so Sonic can interpret the text."""
    policy, tts = settings.humanization, settings.tts
    if not policy.enabled:
        return {"emotion": tts.emotion, "speed": tts.speed, "volume": tts.volume}
    factor = {"baseline": 1.0, "measured": 0.95, "lively": 1.05}[policy.pace]
    return {
        "emotion": None if policy.emotion == "auto" else policy.emotion,
        "speed": policy.speed
        if policy.speed is not None
        else min(1.5, max(0.6, tts.speed * factor)),
        "volume": policy.volume if policy.volume is not None else tts.volume,
    }


class SpeechMarkupGuard:
    """Remove recognized speech controls, including split/escaped and malformed tags.

    Unknown technical angle expressions are preserved. This is not an HTML sanitizer.
    A recognized unclosed tag discards its ambiguous attributes through newline/EOF.
    State is bounded independently of chunk/response length.
    """

    TAGS = ("emotion", "speed", "volume", "break", "spell", "speak", "prosody", "phoneme")
    SOUNDS = ("[laughter]", "[laugh]", "[sigh]", "[sighing]", "[chuckle]")

    def __init__(self):
        self.pending = ""
        self.skipping = False
        self.escaped_end = ""
        self.last_emitted = ""
        self.separator = False

    def feed(self, text: str) -> str:
        output = []

        def emit(value):
            if not value:
                return
            if self.separator and self.last_emitted.isalnum() and value[0].isalnum():
                output.append(" ")
            self.separator = False
            output.append(value)
            self.last_emitted = value[-1]

        for char in text:
            if self.skipping:
                # No attribute buffering, even for an adversarially long tag.
                self.escaped_end = (self.escaped_end + char)[-4:]
                if char == ">" or self.escaped_end.lower() == "&gt;":
                    self.skipping = False
                    self.escaped_end = ""
                elif char in "\r\n":
                    self.skipping = False
                    emit(char)
                continue
            if not self.pending:
                if char in "<&[":
                    self.pending = char
                else:
                    emit(char)
                continue
            self.pending += char
            lower = self.pending.lower()
            if lower.startswith("["):
                if lower in self.SOUNDS:
                    self.pending = ""
                    self.separator = True
                elif not any(token.startswith(lower) for token in self.SOUNDS):
                    emit(self.pending)
                    self.pending = ""
                continue
            if lower.startswith("&") and len(lower) <= 4:
                if "&lt;".startswith(lower):
                    continue
                emit(self.pending)
                self.pending = ""
                continue
            prefix = 4 if lower.startswith("&lt;") else 1
            name = lower[prefix:]
            if name.startswith("/"):
                name = name[1:]
            exact = re.match(r"([a-z]+)(.*)", name, flags=re.DOTALL)
            if exact and exact[1] in self.TAGS and exact[2]:
                if exact[2][0] in " \t\r\n/>&":
                    # Delimiter confirms a control, not e.g. <breakpoint>.
                    ended = char == ">" or lower.endswith("&gt;")
                    self.pending = ""
                    self.separator = True
                    self.skipping = not ended
                    self.escaped_end = "&" if char == "&" else ""
                    continue
            if not any(tag.startswith(name) for tag in self.TAGS):
                emit(self.pending)
                self.pending = ""
        return "".join(output)

    def finish(self) -> str:
        pending, self.pending = self.pending, ""
        self.skipping = False
        # Never flush a half-delivery directive into synthesis. A lone comparator/entity
        # opener remains ordinary text; incomplete recognized names are discarded.
        if pending in ("<", "&", "&l", "&lt", "&lt;"):
            return pending
        return ""


class FillerBudget:
    """Per-session, conservative accounting of generated leading hesitations."""

    def __init__(self, policy: HumanizationSettings):
        self.policy = policy
        self.generation = 0
        self.last_generation = None
        self.last_filler = None

    def begin(self):
        return LeadingHesitation(self)

    def advance(self) -> int:
        # Tool-only requests and empty/canceled prefixes do not consume a reply slot.
        self.generation += 1
        return self.generation

    def allow(self, filler: str, generation: int) -> bool:
        permitted = (
            self.policy.disfluencies == "contextual"
            and self.policy.max_leading_fillers_per_turn == 1
            and (
                self.last_generation is None
                or generation - self.last_generation > self.policy.filler_cooldown_turns
            )
            and filler != self.last_filler
        )
        if permitted:
            self.last_generation, self.last_filler = generation, filler
        return permitted


class LeadingHesitation:
    WORDS = ("hmm", "uh", "um", "umm")
    PREFIX = re.compile(r"^\s*(hmm|uh|umm?)(?:\s+|[,!?…]+\s*|\.{2,}\s*|\.\s+)", re.I)
    MAX_PENDING = 64

    def __init__(self, budget: FillerBudget):
        self.budget = budget
        self.pending = ""
        self.candidate = None
        self.started = False

    def feed(self, text: str) -> str:
        if self.started:
            return text
        output = []
        for index, char in enumerate(text):
            self.pending += char
            if self.candidate and not self.pending.strip(" \t\r\n.,!?…"):
                self.pending = ""
                continue
            match = self.PREFIX.match(self.pending)
            if match:
                if self.candidate is None:
                    self.candidate = "um" if match[1].lower().startswith("um") else match[1].lower()
                self.pending = self.pending[match.end() :]
                continue
            word = self.pending.lstrip().lower()
            # Delay only an ambiguous leading hesitation, never an ordinary sentence.
            possible = any(
                token.startswith(word)
                or (word.startswith(token) and not word[len(token) :].strip(".,!?…"))
                for token in self.WORDS
            )
            if possible and len(self.pending) < self.MAX_PENDING:
                continue
            if not word and len(self.pending) < self.MAX_PENDING:
                continue
            self.started = True
            generation = self.budget.advance()
            if self.candidate and self.budget.allow(self.candidate, generation):
                output.append(self.candidate.capitalize() + ", ")
            output.append(self.pending + text[index + 1 :])
            self.pending = ""
            break
        return "".join(output)

    def finish(self) -> str:
        if self.started:
            return ""
        word = self.pending.strip().lower().strip(".,!?…")
        # Filler-only output makes no TTS request. Ambiguous incomplete ordinary text
        # is preserved instead of inventing content or a synthetic replacement answer.
        result = "" if not word or word in self.WORDS else self.pending
        if result:
            self.budget.advance()
        self.pending = ""
        return result


async def humanize_stream(stream: AsyncIterable, budget: FillerBudget):
    markup, leading = SpeechMarkupGuard(), budget.begin()
    async for chunk in stream:
        if not isinstance(chunk, (str, llm.ChatChunk)):
            raise TypeError("Unsupported LLM chunk type")
        text = (
            chunk
            if isinstance(chunk, str)
            else (chunk.delta.content if isinstance(chunk, llm.ChatChunk) and chunk.delta else None)
        )
        if text is None:
            yield chunk
            continue
        clean = leading.feed(markup.feed(text))
        if isinstance(chunk, str):
            if clean:
                yield clean
        else:
            # Preserve usage/tool IDs/arguments and provider metadata without mutation.
            delta = chunk.delta.model_copy(update={"content": clean or None})
            if clean or delta.tool_calls or chunk.usage:
                yield chunk.model_copy(update={"delta": delta})
    # Reached only on normal completion. Cancellation drops pending fragments.
    tail = leading.feed(markup.finish()) + leading.finish()
    if tail:
        yield tail
