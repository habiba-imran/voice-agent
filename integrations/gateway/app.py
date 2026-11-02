"""Stateful central gateway behind HTTPS; not a serverless/local-memory token endpoint."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import sys
import time

import aiohttp
from aiohttp import web
from livekit import api

from .auth import Unauthenticated, authenticate
from .service import UnknownSession, VoiceGateway
from .settings import from_environment
from .store import AdmissionDenied, QuotaStore

logger = logging.getLogger(__name__)


@web.middleware
async def safe_responses(request, handler):
    try:
        response = await handler(request)
    except Unauthenticated:
        response = web.json_response({"error": "unauthorized"}, status=401)
    except AdmissionDenied:
        response = web.json_response(
            {"error": "limit_reached"}, status=429, headers={"Retry-After": "60"}
        )
    except UnknownSession:
        response = web.json_response({"error": "not_found"}, status=404)
    except web.HTTPException as error:
        response = web.json_response({"error": "invalid_request"}, status=error.status)
    except Exception:
        logger.error("gateway_request_unavailable")
        response = web.json_response({"error": "unavailable"}, status=503)
    response.headers.update(
        {"Cache-Control": "no-store", "Pragma": "no-cache", "X-Content-Type-Options": "nosniff"}
    )
    return response


def create_app(settings, *, client=None, store=None, reaper_interval=5):
    # This must be on durable local storage shared by every worker on ONE gateway host.
    store = store or QuotaStore(settings.database, settings.limits)
    application = web.Application(middlewares=[safe_responses], client_max_size=1024)
    service_key = web.AppKey("voice_gateway", VoiceGateway)

    async def lifecycle(app):
        connection = client or api.LiveKitAPI(
            settings.livekit_url,
            settings.api_key,
            settings.api_secret,
            timeout=aiohttp.ClientTimeout(total=5),
            failover=False,
        )
        service = VoiceGateway(settings, store, connection)
        app[service_key] = service

        async def reaper():
            while True:
                try:
                    await service.reap_once()
                except Exception:
                    # Store/API outage never creates an admission fallback or clears leases.
                    logger.error("gateway_reaper_unavailable")
                await asyncio.sleep(reaper_interval)

        task = asyncio.create_task(reaper(), name="voice_gateway.deadlines")
        try:
            yield
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            await connection.aclose()

    application.cleanup_ctx.append(lifecycle)

    async def identity(request):
        if request.headers.get("Origin") != settings.web_origin:
            raise Unauthenticated
        if request.content_type != "application/json":
            raise web.HTTPBadRequest()
        try:
            body = await request.json()
        except (ValueError, UnicodeError):
            raise web.HTTPBadRequest() from None
        if body != {}:
            raise web.HTTPBadRequest()
        return authenticate(request.headers.get("Authorization", ""), settings.assertion_secret)

    async def start(request):
        principal, network = await identity(request)
        data = await request.app[service_key].start(principal, network)
        return web.json_response(data, status=201)

    async def end(request):
        principal, network = await identity(request)
        await asyncio.to_thread(store.control_rate, principal, network, int(time.time()))
        ended = await request.app[service_key].end(principal, request.match_info["identifier"])
        return web.json_response({"ended": ended}, status=200 if ended else 202)

    application.router.add_post("/v1/sessions", start)
    application.router.add_post(r"/v1/sessions/{identifier:[a-f0-9]{32}}/end", end)
    return application


def main():
    try:
        settings = from_environment(os.environ)
        application = create_app(settings)
    except Exception:
        print(
            "Gateway configuration/storage invalid; see integrations/gateway/.env.example",
            file=sys.stderr,
        )
        raise SystemExit(2) from None
    web.run_app(application, host="127.0.0.1", port=8080, access_log=None, print=None)


if __name__ == "__main__":
    main()
