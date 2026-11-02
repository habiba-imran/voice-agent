"""Optional conversation controls; SDK speech handles own streaming and interruption."""

from __future__ import annotations

import asyncio
import re

from livekit.agents import RunContext

END_CANCELLED = "Ending cancelled; continue listening."

# Whole-utterance grammar: every clause must be an ending or a short courtesy.
# No substring matching, quoted text, questions, negations or trailing topic requests.
_END = (
    r"(?:goodbye|bye(?: bye)?|(?:that's|that is) (?:all(?: for now)?|it)|"
    r"(?:i'm|i am) done|no more questions|"
    r"i (?:don't|do not) want to know anything (?:more|else)|"
    r"(?:you can |please )?(?:end|stop|finish|close) "
    r"(?:(?:the|this|our) )?(?:call|session|conversation)|"
    r"(?:i )?(?:have|need) to go(?: now)?)"
)
_COURTESY = r"(?:thanks|thank you|okay|ok|alright|please)"
_SEPARATOR = r"[\s,.!;]+"
_ENDING_INTENT = re.compile(
    rf"(?:{_COURTESY}{_SEPARATOR})*{_END}"
    rf"(?:{_SEPARATOR}(?:{_END}|{_COURTESY}))*[,.!;\s]*",
    re.IGNORECASE,
)


def explicit_ending_intent(text: str) -> bool:
    """Conservative whole-utterance guard, not a general intent classifier."""
    normalized = " ".join(text.replace("’", "'").split())
    return bool(_ENDING_INTENT.fullmatch(normalized))


class SessionControl:
    def __init__(self, session, settings, *, lifecycle=None, ending_policy=None):
        self.session, self.settings, self.lifecycle = session, settings, lifecycle
        self.ending_policy = ending_policy or explicit_ending_intent
        self.greeted = False
        self.user_started = False
        self.user_activity = 0
        self._ending_result = None
        self._speech = None
        self._closed = False
        self._listening = all(callable(getattr(session, name, None)) for name in ("on", "off"))
        if self._listening:
            session.on("user_state_changed", self._user_state)

    def note_user_activity(self):
        self.user_started = True
        self.user_activity += 1

    def _user_state(self, event):
        if event.new_state == "speaking":
            self.note_user_activity()

    def unavailable(self):
        return self._closed or (
            self.lifecycle is not None
            and (self.lifecycle.stopping or self.lifecycle.closed.is_set())
        )

    async def greet(self):
        if self.greeted:
            return None
        self.greeted = True  # Latch before generation, including failures; no reconnect replay.
        greeting = self.settings.opening
        if self.user_started or self.unavailable() or greeting.mode == "user_first":
            return None
        if greeting.mode == "custom":
            return self.session.say(greeting.text, allow_interruptions=True)
        return self.session.generate_reply(
            instructions=greeting.instructions, tool_choice="none", allow_interruptions=True
        )

    async def request_end(self, *, context: RunContext | None = None, speak: bool = True):
        """Run inline to preserve SDK tool context; duplicate callers share the result."""
        if self.unavailable():
            return False
        if self._ending_result is not None:
            return await asyncio.shield(self._ending_result)
        result_future = asyncio.get_running_loop().create_future()
        self._ending_result = result_future
        try:
            result = await self._finish(context, speak)
            if not result_future.done():
                result_future.set_result(result)
            if not result:
                self._ending_result = None
            return result
        except BaseException:
            if not result_future.done():
                result_future.set_result(False)
            self._ending_result = None
            raise
        finally:
            self._speech = None

    async def _finish(self, context, speak):
        handle = None
        activity = self.user_activity
        try:
            async with asyncio.timeout(self.settings.ending.timeout_seconds):
                if context is not None:
                    # Never wait for the tool's own complete SpeechHandle (a circular wait).
                    await context.wait_for_playout()
                if self.unavailable() or self.user_activity != activity:
                    return False
                ending = self.settings.ending
                if speak and ending.farewell_mode != "none":
                    if ending.farewell_mode == "custom":
                        handle = self.session.say(ending.farewell, allow_interruptions=True)
                    else:
                        handle = self.session.generate_reply(
                            instructions=ending.instructions,
                            tool_choice="none",
                            allow_interruptions=True,
                        )
                    self._speech = handle
                    await handle.wait_for_playout()
                    if handle.interrupted or self.user_activity != activity:
                        return False  # User reclaimed the turn; do not hang up underneath them.
        except asyncio.CancelledError:
            if handle is not None and not handle.done():
                handle.interrupt(force=True)
            raise
        except Exception:
            if handle is not None and not handle.done():
                handle.interrupt(force=True)
            # Requested end still completes after a bounded playback/start failure.
        if self.unavailable() or self.user_activity != activity:
            return False
        if self.lifecycle is not None:
            self.lifecycle.stop("user_initiated", drain=False)
        else:
            self.session.shutdown(drain=False)
        return True

    async def aclose(self):
        self._closed = True
        if self._listening:
            self.session.off("user_state_changed", self._user_state)
            self._listening = False
        if self._speech is not None and not self._speech.done():
            self._speech.interrupt(force=True)
        if self._ending_result is not None and not self._ending_result.done():
            self._ending_result.set_result(False)

    def matches_ending(self, text):
        try:
            return self.ending_policy(text) is True
        except Exception:
            return False

    async def end_from_tool(self, context, confirmed, latest_input):
        allowed = self.matches_ending(latest_input)
        if not confirmed or not allowed:
            return "Not ended. Ask whether the user wants to end this conversation."
        ended = await self.request_end(context=context)
        return "Session ended." if ended else END_CANCELLED
