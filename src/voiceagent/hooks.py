"""One explicit async setup hook; no automatic imports or external I/O."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SessionExtensions:
    # Validated as LiveKit FunctionTool/RawFunctionTool at the runtime boundary.
    tools: tuple[object, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)
    ending_policy: Callable[[str], bool] | None = None


SessionHook = Callable[[], Awaitable[SessionExtensions]]


class HookError(ValueError):
    """Safe error without hook payload or exception details."""


async def prepare_extensions(
    hook: SessionHook | None = None, *, deadline_seconds: float = 2, max_metadata_bytes: int = 2048
) -> SessionExtensions:
    if hook is None:
        return SessionExtensions()
    if not callable(hook) or not inspect.iscoroutinefunction(hook):
        raise HookError("Session hook must be an async function")
    try:
        async with asyncio.timeout(deadline_seconds):
            result = await hook()
    except asyncio.CancelledError:
        raise
    except TimeoutError:
        raise HookError("Session hook timed out") from None
    except Exception:
        raise HookError("Session hook failed") from None
    if not isinstance(result, SessionExtensions) or not isinstance(result.tools, tuple):
        raise HookError("Session hook must return SessionExtensions with a tools tuple")
    if not isinstance(result.metadata, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in result.metadata.items()
    ):
        raise HookError("Session metadata must contain string keys and values")
    if len(json.dumps(result.metadata, ensure_ascii=False).encode("utf-8")) > max_metadata_bytes:
        raise HookError("Session metadata exceeds limits.max_metadata_bytes")
    if result.tools:
        from livekit.agents.llm import is_function_tool, is_raw_function_tool

        if not all(is_function_tool(tool) or is_raw_function_tool(tool) for tool in result.tools):
            raise HookError("Session tools must be decorated LiveKit function tools")
    if result.ending_policy is not None and (
        not callable(result.ending_policy)
        or inspect.iscoroutinefunction(result.ending_policy)
        or inspect.iscoroutinefunction(result.ending_policy.__call__)
    ):
        raise HookError("Ending policy must be a synchronous callable")
    return SessionExtensions(
        tools=result.tools, metadata=dict(result.metadata), ending_policy=result.ending_policy
    )


async def resolve_extensions(
    hook: SessionHook | None = None, *, deadline_seconds: float = 2, max_metadata_bytes: int = 2048
) -> SessionExtensions:
    """Disable malformed optional extensions while allowing the session to start."""
    try:
        return await prepare_extensions(
            hook, deadline_seconds=deadline_seconds, max_metadata_bytes=max_metadata_bytes
        )
    except HookError:
        # Do not log hook exception text, metadata, arguments, or tool payloads.
        logger.warning("Optional session hook disabled", extra={"event": "hook_disabled"})
        return SessionExtensions()
