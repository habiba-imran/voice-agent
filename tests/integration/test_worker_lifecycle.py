"""Real native HTTP/pool lifecycle with fake registration/job state, never a Cloud connection."""

from __future__ import annotations

import asyncio
import runpy
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from livekit.agents import AgentServer, JobExecutorType

from voiceagent.healthcheck import healthy
from voiceagent.settings import PROJECT_ROOT

pytestmark = pytest.mark.integration


async def test_bundled_model_preparation_without_provider_clients(capsys):
    module = runpy.run_path(str(PROJECT_ROOT / "scripts/prepare_models.py"))
    await asyncio.wait_for(asyncio.to_thread(module["prepare"]), timeout=30)
    assert "no provider clients created" in capsys.readouterr().out


@pytest.mark.parametrize("unregistered", [False, True])
async def test_native_worker_health_drain_and_idempotent_cleanup(monkeypatch, unregistered):
    # Restore env on exit: the installed worker writes its connection settings into os.environ.
    for key in ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"):
        monkeypatch.setenv(key, "synthetic")
    before = set(asyncio.all_tasks())
    started = asyncio.Event()
    server = AgentServer(
        ws_url="wss://example.invalid",
        api_key="synthetic-key",
        api_secret="synthetic-secret",
        host="127.0.0.1",
        port=0,
        num_idle_processes=0,
        job_executor_type=JobExecutorType.THREAD,
        load_fnc=lambda _: 0.0,
    )
    server.rtc_session(AsyncMock(), agent_name="voiceagent")
    server.on("worker_started", lambda: started.set())
    # No websocket, JWT exchange, provider calls or real registration. Only lifecycle is native.
    monkeypatch.setattr(server, "_connection_task", AsyncMock(side_effect=asyncio.Event().wait))
    running = asyncio.create_task(server.run(devmode=False, unregistered=unregistered))
    drain_task = None
    original_pool = None
    try:
        await asyncio.wait_for(started.wait(), timeout=15)
        port = server.worker_info.http_port
        assert port > 0
        assert await asyncio.to_thread(healthy, port) is unregistered
        # Locked-SDK white-box state injection exercises real HTTP health policy.
        server._id = "synthetic-registered-worker"
        assert await asyncio.to_thread(healthy, port)
        server._disconnected_at = time.monotonic() - 31
        assert await asyncio.to_thread(healthy, port) is unregistered
        server._disconnected_at = time.monotonic()
        assert await asyncio.to_thread(healthy, port)
        server._connection_failed = True
        assert not await asyncio.to_thread(healthy, port)
        server._connection_failed = False
        server._disconnected_at = None

        # A controlled job join tests the real SDK drain waiting policy, not real job execution.
        joining, finish = asyncio.Event(), asyncio.Event()
        process = SimpleNamespace(running_job=object())

        async def join():
            joining.set()
            await finish.wait()
            process.running_job = None

        process.join = join
        original_pool = server._proc_pool
        server._proc_pool = SimpleNamespace(processes=[process])
        drain_task = asyncio.create_task(server.drain(timeout=5))
        await asyncio.wait_for(joining.wait(), timeout=5)
        assert server.draining and not drain_task.done()
        # Health is still liveness/connection health while draining, not admission readiness.
        assert await asyncio.to_thread(healthy, port)
        finish.set()
        await asyncio.wait_for(drain_task, timeout=5)
        await server.drain(timeout=1)  # SDK idempotence.
    finally:
        if drain_task is not None and not drain_task.done():
            drain_task.cancel()
            await asyncio.gather(drain_task, return_exceptions=True)
        if original_pool is not None:
            server._proc_pool = original_pool
        await asyncio.wait_for(server.aclose(), timeout=10)
        await asyncio.wait_for(running, timeout=10)
    await server.aclose()
    assert server._http_session.closed
    assert server._load_task.done()
    assert server._conn_task is None or server._conn_task.done()
    await asyncio.sleep(0)
    assert not [task for task in asyncio.all_tasks() - before if not task.done()]
    assert not await asyncio.to_thread(healthy, port)
