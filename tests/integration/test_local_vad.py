"""Local model verification; no microphone, provider, recording, or room connection."""

import pytest


@pytest.mark.integration
async def test_bundled_silero_model_and_stream_close():
    from livekit.agents.vad import VAD
    from livekit.plugins import silero

    model = silero.VAD.load(force_cpu=True)
    assert isinstance(model, VAD)
    stream = model.stream()
    stream.end_input()
    await stream.aclose()
