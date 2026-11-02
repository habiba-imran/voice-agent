"""Bounded deterministic signal fixtures in memory. Tones are explicitly not human speech."""

import json
import math
import random
import struct
from pathlib import Path

from livekit import rtc

MANIFEST = Path(__file__).resolve().parents[1] / "fixtures" / "audio_scenarios.json"


def catalog():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if data["origin"] != "synthetic_signal_not_speech":
        raise ValueError("Fixture provenance must be explicit")
    return data


def frames(scenario):
    """Yield mono signed 16-bit little-endian frames; no file, device or provider access."""
    rng = random.Random(scenario["seed"])
    elapsed = 0
    total = sum(segment["duration_ms"] for segment in scenario["segments"])
    if not 0 < total <= 20000:
        raise ValueError("Signal fixtures must fit 20 seconds")
    for segment in scenario["segments"]:
        kind, duration = segment["kind"], segment["duration_ms"]
        if kind not in {"silence", "tone", "noise", "mixed", "overlap"} or duration % 20:
            raise ValueError("Invalid fixture segment")
        for _ in range(duration // 20):
            samples = []
            for index in range(320):
                position = elapsed + index
                tone = 2800 * math.sin(2 * math.pi * 220 * position / 16000)
                other = 1800 * math.sin(2 * math.pi * 330 * position / 16000)
                noise = rng.randint(-450, 450)
                value = {
                    "silence": 0,
                    "tone": tone,
                    "noise": noise,
                    "mixed": tone + noise,
                    "overlap": tone + other,
                }[kind]
                samples.append(int(value))
            elapsed += 320
            yield rtc.AudioFrame(struct.pack("<320h", *samples), 16000, 1, 320)
