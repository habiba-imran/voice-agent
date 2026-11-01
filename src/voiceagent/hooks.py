"""One explicit async setup hook; no automatic imports or external I/O."""

from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SessionExtensions:
    # Validated as LiveKit FunctionTool/RawFunctionTool at the runtime boundary.
    tools: tuple[object, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)


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
    return SessionExtensions(tools=result.tools, metadata=dict(result.metadata))
