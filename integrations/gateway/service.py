"""Control plane only. No worker/provider code and no browser-configurable dispatch targets."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import timedelta

from livekit import api

logger = logging.getLogger(__name__)


class UnknownSession(Exception):
    pass


class VoiceGateway:
    def __init__(self, settings, store, client, *, clock=time.time):
        self.settings, self.store, self.client, self.clock = settings, store, client, clock

    async def start(self, principal, network):
        reservation = await asyncio.to_thread(
            self.store.reserve, principal, network, int(self.clock())
        )
        try:
            async with asyncio.timeout(10):
                await self.client.room.create_room(
                    api.CreateRoomRequest(
                        name=reservation.room,
                        max_participants=2,
                        empty_timeout=30,
                        departure_timeout=20,
                    )
                )
                await self.client.agent_dispatch.create_dispatch(
                    api.CreateAgentDispatchRequest(
                        room=reservation.room, agent_name=self.settings.agent_name
                    )
                )
            # Never embed dispatch in the browser token: replay must not start another worker.
            token = (
                api.AccessToken(self.settings.api_key, self.settings.api_secret)
                .with_identity(reservation.identity)
                .with_ttl(timedelta(seconds=self.settings.limits.token_seconds))
                .with_grants(
                    api.VideoGrants(
                        room_join=True,
                        room=reservation.room,
                        can_publish=True,
                        can_publish_sources=["microphone"],
                        can_subscribe=True,
                        can_publish_data=False,
                        can_update_own_metadata=False,
                        room_create=False,
                        room_list=False,
                        room_admin=False,
                        room_record=False,
                        agent=False,
                        can_manage_agent_session=False,
                        can_subscribe_metrics=False,
                    )
                )
                .to_jwt()
            )
            await asyncio.to_thread(self.store.activate, reservation.id)
            return {
                "sessionId": reservation.id,
                "serverUrl": self.settings.livekit_url.replace("https://", "wss://", 1),
                "token": token,
                "expiresAt": int(self.clock()) + self.settings.limits.token_seconds,
                "deadline": reservation.deadline,
            }
        except BaseException:
            # Unknown network outcomes never trigger a second create/dispatch attempt.
            await asyncio.to_thread(self.store.closing, reservation.id, int(self.clock()))
            raise

    async def end(self, principal, identifier):
        reservation = await asyncio.to_thread(self.store.get, identifier)
        if reservation is None or reservation.principal != principal:
            raise UnknownSession
        if reservation.state == "closed":
            return True
        await asyncio.to_thread(self.store.closing, identifier, int(self.clock()))
        return await self.cleanup(identifier)

    async def cleanup(self, identifier):
        now = int(self.clock())
        reservation = await asyncio.to_thread(self.store.claim_cleanup, identifier, now)
        if reservation is None:
            return False
        try:
            async with asyncio.timeout(10):
                if reservation.issued:
                    # Cloud-only strict cutoff avoids the default one-minute replay window.
                    await self.client.room.remove_participant(
                        api.RoomParticipantIdentity(
                            room=reservation.room,
                            identity=reservation.identity,
                            revoke_token_ts=now + 10,
                        )
                    )
                try:
                    await self.client.room.delete_room(api.DeleteRoomRequest(room=reservation.room))
                except api.TwirpError as error:
                    if error.code != "not_found":
                        raise
            await asyncio.to_thread(self.store.cleaned, identifier)
            return True
        except asyncio.CancelledError:
            raise
        except Exception:
            # Persisted max six attempts, one minute apart. Exhaustion holds capacity closed.
            logger.warning("gateway_cleanup_pending", extra={"attempt": reservation.attempts})
            await asyncio.to_thread(self.store.cleanup_failed, identifier, now)
            return False

    async def reap_once(self):
        for identifier in await asyncio.to_thread(self.store.due, int(self.clock())):
            await self.cleanup(identifier)
