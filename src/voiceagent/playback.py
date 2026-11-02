"""Optional room-member playback readiness; never a timer pretending audio is ready."""

from __future__ import annotations

import asyncio

from livekit import rtc

PLAYBACK_READY_ATTRIBUTE = "voiceagent.playback_ready"


class ClientPlaybackReady:
    """A linked participant acknowledges successful browser audio-track playback.

    The host must permit only updates to that participant's own metadata/attributes.
    Other room members and all other attribute values are ignored. Reconnects retain
    the acknowledgement; the SessionControl still latches the greeting exactly once.
    The caller supplies the existing bounded startup deadline.
    """

    def __init__(self, room):
        self.room = room
        self.identity = None
        self.ready = asyncio.Event()
        room.on("participant_attributes_changed", self._changed)

    def _changed(self, _attributes, participant):
        if (
            self.identity is not None
            and participant.identity == self.identity
            and participant.attributes.get(PLAYBACK_READY_ATTRIBUTE) == "true"
        ):
            self.ready.set()

    async def wait(self, participant, closed):
        self.identity = participant.identity
        self._changed({}, participant)  # Covers readiness acknowledged before binding.
        ready = asyncio.create_task(self.ready.wait())
        stopped = asyncio.create_task(closed.wait())
        try:
            await asyncio.wait((ready, stopped), return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in (ready, stopped):
                task.cancel()
            await asyncio.gather(ready, stopped, return_exceptions=True)

    def close(self):
        self.room.off("participant_attributes_changed", self._changed)


async def prime_playback(session):
    """Give a newly subscribed browser track real silent media before its play() ack.

    Otherwise some browsers wait for media to resolve play(), while the greeting
    waits for play() -- a startup deadlock. This uses supplied PCM in memory, not
    TTS/LLM, a recording, a file or an extra provider request.
    """

    async def silence():
        for _ in range(3):
            yield rtc.AudioFrame.create(sample_rate=24000, num_channels=1, samples_per_channel=2400)

    handle = session.say("", audio=silence(), allow_interruptions=False, add_to_chat_ctx=False)
    await handle.wait_for_playout()
