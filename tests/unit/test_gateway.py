import asyncio
import time
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import aiohttp
import jwt
import pytest
from aiohttp import web

from integrations.gateway.app import create_app
from integrations.gateway.auth import Unauthenticated, authenticate
from integrations.gateway.service import UnknownSession, VoiceGateway
from integrations.gateway.settings import GatewaySettings
from integrations.gateway.store import AdmissionDenied, QuotaStore

SECRET = "synthetic-assertion-secret-at-least-32-characters"


def settings_for(tmp_path):
    return GatewaySettings(
        tmp_path / "gateway.sqlite3",
        "wss://synthetic.livekit.cloud",
        "synthetic-api-key",
        "synthetic-api-secret-at-least-32-characters",
        SECRET,
        "https://example.invalid",
    )


def fake_client():
    return SimpleNamespace(
        room=SimpleNamespace(
            create_room=AsyncMock(), delete_room=AsyncMock(), remove_participant=AsyncMock()
        ),
        agent_dispatch=SimpleNamespace(create_dispatch=AsyncMock()),
        aclose=AsyncMock(),
    )


def assertion(**overrides):
    now = int(time.time())
    return "Bearer " + jwt.encode(
        {
            "iss": "voice-web",
            "aud": "voice-gateway",
            "sub": "synthetic-user",
            "network": "synthetic-network",
            "iat": now,
            "nbf": now,
            "exp": now + 60,
            **overrides,
        },
        SECRET,
        algorithm="HS256",
    )


def test_assertions_are_verified_and_identifiers_hashed():
    principal, network = authenticate(assertion(), SECRET)
    assert len(principal) == len(network) == 64
    assert "synthetic" not in principal + network


@pytest.mark.parametrize(
    "overrides",
    [
        {"aud": "wrong"},
        {"iss": "wrong"},
        {"exp": 1},
        {"exp": int(time.time()) + 600},
        {"sub": ""},
        {"network": {}},
    ],
)
def test_untrusted_assertion_cannot_choose_long_lived_or_invalid_identity(overrides):
    with pytest.raises(Unauthenticated):
        authenticate(assertion(**overrides), SECRET)


async def test_scoped_native_token_explicit_dispatch_and_owner_only_idempotent_end(tmp_path):
    settings = settings_for(tmp_path)
    store = QuotaStore(settings.database, settings.limits)
    client = fake_client()
    gateway = VoiceGateway(settings, store, client)
    result = await gateway.start("principal", "network")
    claims = jwt.decode(
        result["token"], settings.api_secret, algorithms=["HS256"], issuer=settings.api_key
    )
    video = claims["video"]
    assert video["roomJoin"] and video["canPublishSources"] == ["microphone"]
    assert not video["roomAdmin"] and not video["roomCreate"] and not video["agent"]
    assert not video["canPublishData"] and not video["canUpdateOwnMetadata"]
    assert "roomConfig" not in claims  # Replay never embeds worker dispatch.
    assert claims["exp"] - claims["nbf"] == 60
    dispatch = client.agent_dispatch.create_dispatch.call_args.args[0]
    assert dispatch.agent_name == "voiceagent" and dispatch.room == video["room"]
    with pytest.raises(UnknownSession):
        await gateway.end("other", result["sessionId"])
    assert await gateway.end("principal", result["sessionId"])
    assert await gateway.end("principal", result["sessionId"])
    client.room.delete_room.assert_awaited_once()
    assert client.room.remove_participant.call_args.args[0].revoke_token_ts >= int(time.time())


async def test_dispatch_failure_has_no_retry_and_keeps_conservative_quota(tmp_path):
    settings = settings_for(tmp_path)
    store = QuotaStore(settings.database, settings.limits)
    client = fake_client()
    client.agent_dispatch.create_dispatch.side_effect = TimeoutError("private provider payload")
    gateway = VoiceGateway(settings, store, client)
    with pytest.raises(TimeoutError):
        await gateway.start("principal", "network")
    client.agent_dispatch.create_dispatch.assert_awaited_once()
    with pytest.raises(AdmissionDenied):
        await gateway.start("principal", "network")
    await gateway.reap_once()
    client.room.delete_room.assert_awaited_once()
    client.room.remove_participant.assert_not_awaited()  # No participant token was released.


async def test_deadline_and_revocation_failure_hold_capacity_until_success(tmp_path):
    settings = settings_for(tmp_path)
    store = QuotaStore(settings.database, settings.limits)
    client = fake_client()
    now = [int(time.time())]
    gateway = VoiceGateway(settings, store, client, clock=lambda: now[0])
    result = await gateway.start("principal", "network")
    now[0] += 301
    client.room.remove_participant.side_effect = ConnectionError("private")
    await gateway.reap_once()
    assert store.get(result["sessionId"]).state == "closing"
    with pytest.raises(AdmissionDenied):
        await gateway.start("principal", "network")
    client.room.remove_participant.side_effect = None
    now[0] += 61
    await gateway.reap_once()
    assert store.get(result["sessionId"]).state == "closed"


@asynccontextmanager
async def local_server(settings, client, store=None):
    application = create_app(settings, client=client, store=store, reaper_interval=60)
    runner = web.AppRunner(application, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    try:
        port = runner.addresses[0][1]
        yield f"http://127.0.0.1:{port}"
    finally:
        await runner.cleanup()


@pytest.mark.parametrize(
    "failure", ["missing_auth", "wrong_origin", "injected_body", "too_large", "store_outage"]
)
async def test_http_fail_closed_and_never_echoes_secrets(tmp_path, failure):
    settings = settings_for(tmp_path)
    client = fake_client()
    store = QuotaStore(settings.database, settings.limits)
    headers = {"Origin": settings.web_origin, "Authorization": assertion()}
    body = {}
    if failure == "missing_auth":
        headers.pop("Authorization")
    if failure == "wrong_origin":
        headers["Origin"] = "https://attacker.invalid"
    if failure == "injected_body":
        body = {"room": "private", "agent_name": "attacker"}
    if failure == "too_large":
        body = {"private": "x" * 2048}
    async with local_server(settings, client, store=store) as url:
        if failure == "store_outage":
            # Opening a directory as SQLite must fail closed, not fall back to process memory.
            store.database = tmp_path
        async with aiohttp.ClientSession() as http:
            async with http.post(url + "/v1/sessions", headers=headers, json=body) as response:
                assert response.status in {400, 401, 413, 503}
                assert response.headers["Cache-Control"] == "no-store"
                assert "private" not in await response.text()
                assert settings.api_secret not in await response.text()
    client.agent_dispatch.create_dispatch.assert_not_awaited()
    client.aclose.assert_awaited_once()


async def test_http_start_end_cleanup_and_repeated_tokens_are_limited(tmp_path):
    settings = settings_for(tmp_path)
    client = fake_client()
    headers = {"Origin": settings.web_origin, "Authorization": assertion()}
    before = set(asyncio.all_tasks())
    async with local_server(settings, client) as url, aiohttp.ClientSession() as http:
        async with http.post(url + "/v1/sessions", headers=headers, json={}) as response:
            assert response.status == 201
            identifier = (await response.json())["sessionId"]
        async with http.post(url + "/v1/sessions", headers=headers, json={}) as response:
            assert response.status == 429
        async with http.post(
            url + f"/v1/sessions/{identifier}/end", headers=headers, json={}
        ) as response:
            assert response.status == 200 and (await response.json())["ended"]
    await asyncio.sleep(0)
    assert not [task for task in asyncio.all_tasks() - before if not task.done()]
