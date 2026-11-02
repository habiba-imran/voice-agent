"""Real installed plugin and pool, fake WebSocket/PCM. No Cartesia requests."""

import asyncio
import base64
import json
from types import SimpleNamespace

import aiohttp
import pytest
from livekit.agents import APIConnectOptions
from livekit.plugins import cartesia
from turn_harness import eventually


class MemoryWebSocket:
    def __init__(self, *, respond=True):
        self.respond = respond
        self.packets = []
        self.incoming = asyncio.Queue()
        self.closed = False

    async def send_str(self, message):
        packet = json.loads(message)
        self.packets.append(packet)
        if not packet["continue"] and self.respond:
            context = packet["context_id"]
            for data in (
                {"context_id": context, "data": base64.b64encode(bytes(1920)).decode()},
                {"context_id": context, "done": True},
            ):
                self.incoming.put_nowait(
                    SimpleNamespace(type=aiohttp.WSMsgType.TEXT, data=json.dumps(data))
                )

    async def receive(self, *, timeout):  # noqa: ASYNC109 - matches aiohttp WebSocket API
        return await asyncio.wait_for(self.incoming.get(), timeout=timeout)

    async def close(self):
        self.closed = True


@pytest.fixture
def sockets(monkeypatch):
    created = []

    async def connect(_client, timeout):  # noqa: ASYNC109 - matches SDK pool callback API
        socket = MemoryWebSocket()
        created.append(socket)
        return socket

    monkeypatch.setattr(cartesia.TTS, "_connect_ws", connect)
    return created


async def synthesize(client, text, *, stream=None):
    async with stream or client.stream(conn_options=APIConnectOptions(max_retry=0)) as output:
        output.push_text(text)
        output.end_input()
        async with asyncio.timeout(5):
            return [audio async for audio in output]


async def test_real_plugin_snapshots_controls_forwards_markup_and_reuses_pool(sockets):
    client = cartesia.TTS(
        api_key="synthetic",
        voice="00000000-0000-4000-8000-000000000001",
        emotion="calm",
        speed=1,
        volume=1,
    )
    try:
        first = client.stream(conn_options=APIConnectOptions(max_retry=0))
        client.update_options(emotion="excited", speed=1.1)
        audio = await synthesize(client, 'Hello <break time="300ms"/>world.', stream=first)
        assert audio and len(sockets) == 1
        first_packets = list(sockets[0].packets)
        assert all(
            p["generation_config"] == {"emotion": "calm", "speed": 1, "volume": 1}
            for p in first_packets
        )
        # Forwarding is verified; the fake does not interpret tags or prove audible pauses.
        assert '<break time="300ms"/>' in "".join(p["transcript"] for p in first_packets)
        await synthesize(client, "Next complete sentence.")
        assert len(sockets) == 1
        later = sockets[0].packets[len(first_packets) :]
        assert later and all(p["generation_config"]["emotion"] == "excited" for p in later)
        assert all(p["generation_config"]["speed"] == 1.1 for p in later)
        assert first_packets[0]["context_id"] != later[0]["context_id"]
    finally:
        await client.aclose()
    assert sockets[0].closed


async def test_real_plugin_auto_emotion_omits_emotion_field(sockets):
    client = cartesia.TTS(api_key="synthetic", emotion=None, speed=1, volume=1)
    try:
        await synthesize(client, "A natural question?")
        assert all(p["generation_config"] == {"speed": 1, "volume": 1} for p in sockets[0].packets)
    finally:
        await client.aclose()


async def test_native_pool_prewarm_is_reused_by_first_and_later_synthesis(sockets):
    client = cartesia.TTS(api_key="synthetic", emotion=None)
    try:
        client.prewarm()
        await eventually(lambda: sockets)
        await synthesize(client, "First complete sentence.")
        await synthesize(client, "Second complete sentence.")
        assert len(sockets) == 1
    finally:
        await client.aclose()
    assert sockets[0].closed


async def test_real_plugin_cancellation_closes_socket_and_background_tasks(sockets):
    before = asyncio.all_tasks()
    client = cartesia.TTS(api_key="synthetic", emotion="neutral")

    async def consume():
        async with client.stream(conn_options=APIConnectOptions(max_retry=0)) as stream:
            stream.push_text("Speech in progress.")
            stream.flush()
            await eventually(lambda: sockets)
            sockets[0].respond = False
            async for _ in stream:
                pass

    task = asyncio.create_task(consume())
    try:
        await eventually(lambda: sockets and sockets[0].packets)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await client.aclose()
    await asyncio.sleep(0)
    assert sockets[0].closed
    assert not [task for task in asyncio.all_tasks() - before if not task.done()]
