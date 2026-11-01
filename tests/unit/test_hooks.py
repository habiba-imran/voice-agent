from __future__ import annotations

import asyncio

import pytest

from voiceagent.hooks import HookError, SessionExtensions, prepare_extensions, resolve_extensions


async def test_no_hook():
    result = await prepare_extensions()
    assert result == SessionExtensions()
    assert result.metadata is not (await prepare_extensions()).metadata


async def test_explicit_hook():
    async def hook():
        return SessionExtensions(metadata={"topic": "synthetic"})

    assert (await prepare_extensions(hook)).metadata == {"topic": "synthetic"}


async def test_timeout_cancels_hook():
    canceled = asyncio.Event()

    async def hook():
        try:
            await asyncio.Event().wait()
        finally:
            canceled.set()

    with pytest.raises(HookError, match="timed out"):
        await prepare_extensions(hook, deadline_seconds=0.01)
    assert canceled.is_set()


async def test_cancellation_propagates():
    started = asyncio.Event()

    async def hook():
        started.set()
        await asyncio.Event().wait()

    task = asyncio.create_task(prepare_extensions(hook))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.parametrize(
    "returned",
    [
        None,
        {},
        SessionExtensions(metadata={"x": 2}),
        SessionExtensions(tools=[]),
        SessionExtensions(tools=(object(),)),
        SessionExtensions(metadata={"x": "a" * 2050}),
    ],
)
async def test_malformed_result(returned):
    async def hook():
        return returned

    with pytest.raises(HookError):
        await prepare_extensions(hook)


async def test_malformed_hook():
    with pytest.raises(HookError, match="async function"):
        await prepare_extensions(lambda: None)


async def test_hook_exception_is_sanitized():
    async def hook():
        raise RuntimeError("synthetic-secret-payload")

    with pytest.raises(HookError) as error:
        await prepare_extensions(hook)
    assert "synthetic-secret" not in str(error.value)


async def test_malformed_optional_hook_does_not_block_startup(caplog):
    async def hook():
        raise RuntimeError("synthetic-secret-payload")

    assert await resolve_extensions(hook) == SessionExtensions()
    assert "Optional session hook disabled" in caplog.text
    assert "synthetic-secret" not in caplog.text


async def test_registered_livekit_tool():
    from livekit.agents.llm import function_tool

    @function_tool
    async def synthetic_tool() -> str:
        """Return a synthetic test value without external I/O."""
        return "synthetic"

    async def hook():
        return SessionExtensions(tools=(synthetic_tool,))

    result = await resolve_extensions(hook)
    assert result.tools == (synthetic_tool,)
