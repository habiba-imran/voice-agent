"""One session's stop policy; LiveKit still owns interruption and stream cancellation."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from uuid import uuid4

from livekit.agents import APIConnectionError, APITimeoutError

logger = logging.getLogger(__name__)
REASONS = {
    "session_ended",
    "participant_disconnected",
    "room_disconnected",
    "user_initiated",
    "error",
    "session_limit",
    "idle_limit",
    "job_shutdown",
    "provider_error",
    "startup_timeout",
    "session_failure",
    "cancelled",
    "shutdown_timeout",
    "input_limit",
    "request_limit",
}


def failure_details(error):
    """Only fixed classifications, never exception text, headers or response bodies."""
    inner = getattr(error, "error", error)
    status = getattr(inner, "status_code", None)
    status = status if type(status) is int and 100 <= status <= 599 else None
    category = (
        "timeout"
        if isinstance(inner, (TimeoutError, APITimeoutError))
        else "authentication"
        if status in (401, 403)
        else "rate_limit"
        if status == 429
        else "server"
        if status is not None and status >= 500
        else "request"
        if status is not None and status >= 400
        else "network"
        if isinstance(inner, (APIConnectionError, ConnectionError, OSError))
        else "provider"
    )
    kind = getattr(error, "type", None)
    return {
        "component": kind if kind in {"stt_error", "llm_error", "tts_error"} else "unknown",
        "category": category,
        "status_code": status,
        "recoverable": bool(getattr(error, "recoverable", False)),
    }


class SessionLifecycle:
    def __init__(self, session, settings):
        self.session = session
        self.settings = settings.runtime
        self.id = uuid4().hex
        self.started_at = time.perf_counter()
        self.closed = asyncio.Event()
        self.finished = asyncio.Event()
        self.reason = "session_ended"
        self.stopping = False
        self.watchdog = None

    def on_close(self, event):
        if not self.stopping and not self.closed.is_set():
            value = getattr(event.reason, "value", event.reason)
            self.reason = value if isinstance(value, str) and value in REASONS else "session_ended"
        self.closed.set()

    def stop(self, reason, *, drain=True):
        if self.finished.is_set() or self.closed.is_set():
            return
        if self.stopping:
            if not drain:
                # A second shutdown() cannot change an SDK drain already in progress.
                self._interrupt()
            return
        self.stopping = True
        self.reason = reason if reason in REASONS else "session_failure"
        self.session.shutdown(drain=drain)
        self.watchdog = asyncio.create_task(
            self._watch_close(drain), name="voiceagent.stop_watchdog"
        )

    def _interrupt(self):
        try:
            future = self.session.interrupt(force=True)
        except RuntimeError:
            return  # Session has not started, or already closed.
        # The SDK owns this future and the underlying cancellation tasks.
        if isinstance(future, asyncio.Future):
            future.add_done_callback(self._consume_interrupt)

    def on_error(self, event):
        details = failure_details(event.error)
        logger.error("provider_error", extra={"session_id": self.id, **details})
        if not details["recoverable"]:
            self.stop("provider_error", drain=False)

    @staticmethod
    def _consume_interrupt(future):
        if not future.cancelled():
            future.exception()

    async def _watch_close(self, drain):
        try:
            if drain:
                try:
                    async with asyncio.timeout(self.settings.drain_timeout_seconds):
                        await self.closed.wait()
                    return
                except TimeoutError:
                    logger.info("session_drain_expired", extra={"session_id": self.id})
                    self._interrupt()
            async with asyncio.timeout(self.settings.shutdown_timeout_seconds):
                await self.closed.wait()
        except TimeoutError:
            self.reason = "shutdown_timeout"
            self.closed.set()  # Release entrypoint so bounded cleanup and job shutdown run.

    async def close(self):
        self.stopping = True  # Cleanup-generated close events must preserve the stop cause.
        if self.watchdog is not None:
            self.watchdog.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.watchdog
        try:
            async with asyncio.timeout(self.settings.shutdown_timeout_seconds):
                await self.session.aclose()
        except TimeoutError:
            self.reason = "shutdown_timeout"
            logger.error("session_cleanup_timeout", extra={"session_id": self.id})
        except Exception:
            self.reason = "session_failure"
            logger.error("session_cleanup_failed", extra={"session_id": self.id})

    def complete(self):
        self.finished.set()
        logger.info(
            "session_finished",
            extra={
                "session_id": self.id,
                "reason": self.reason,
                "elapsed_seconds": time.perf_counter() - self.started_at,
            },
        )
