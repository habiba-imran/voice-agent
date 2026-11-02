"""Offline developer benchmark using real AgentSession and scripted local providers.

This tool depends on the shipped tests/unit harness, never loads .env.local, and
blocks external Python networking. It is not a provider or acoustic benchmark.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import platform
import socket
import sys
import time
from contextlib import ExitStack, contextmanager
from importlib.metadata import version
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "unit"))
from livekit.agents import stt, vad  # noqa: E402
from turn_harness import Harness, Reply, eventually  # noqa: E402

from voiceagent.expression import FillerBudget, humanize_stream  # noqa: E402
from voiceagent.performance import PerformanceObserver, distribution  # noqa: E402
from voiceagent.settings import HumanizationSettings, Settings  # noqa: E402


@contextmanager
def offline_network():
    with ExitStack() as stack:
        for owner, name in (
            (socket, "getaddrinfo"),
            (socket.socket, "connect"),
            (socket.socket, "connect_ex"),
        ):
            original = getattr(owner, name)

            def guarded(*args, _original=original, _name=name, **kwargs):
                host = args[0] if _name == "getaddrinfo" else args[1][0]
                if host not in ("127.0.0.1", "::1", "localhost"):
                    raise RuntimeError("External networking is forbidden in synthetic benchmarks")
                return _original(*args, **kwargs)

            stack.enter_context(patch.object(owner, name, guarded))
        yield


class ScriptedEOT:
    def predict(self, pcm):
        return 1.0


async def measure_text_processing(iterations=200):
    """Controlled text-only comparison, separate from native-session/provider timing."""
    text = ("Hmm, ", "A complete sentence. ", "Keep 42.5 and Type<T>. ") * 32

    async def source():
        for chunk in text:
            yield chunk

    results = []
    for enabled in (False, True):
        budget = FillerBudget(HumanizationSettings(enabled=enabled))
        first, total = [], []
        for iteration in range(iterations + 8):
            stream = humanize_stream(source(), budget) if enabled else source()
            started = time.perf_counter()
            first_at = None
            async for _ in stream:
                if first_at is None:
                    first_at = time.perf_counter()
            finished = time.perf_counter()
            if iteration >= 8:
                first.append(first_at - started)
                total.append(finished - started)
        results.append(
            {
                "humanization": enabled,
                "origin": "synthetic_text_processing_only",
                "chunks_per_iteration": len(text),
                "first_output_s": distribution(first),
                "total_processing_s": distribution(total),
                "provider_requests": 0,
            }
        )
    return results


async def input_turn(h, text, profile, delay):
    await h.speech_start()
    if profile == "semantic":
        h.vad.send(vad.VADEventType.INFERENCE_DONE, silence=0.3)
    await h.speech_end()
    await asyncio.sleep(delay)
    await h.transcript(text)
    if profile == "stt":
        h.agent.transcripts.send_nowait(stt.SpeechEvent(type=stt.SpeechEventType.END_OF_SPEECH))


async def run_case(*, profile, humanization, turns, delay, replica):
    settings = Settings.model_validate(
        {
            "stt": {"model": "flux-general-en" if profile == "stt" else "nova-3"},
            "listening": {
                "turn_detection": profile,
                "min_endpoint_delay": 0.02,
                "max_endpoint_delay": 0.1,
            },
            "humanization": {"enabled": humanization},
            "interruption": {"false_interruption_timeout": 0.1},
        }
    )
    h = Harness(settings)
    h.agent.audio_delay = delay
    observer = PerformanceObserver(settings, origin="synthetic_native_session")
    observer.attach(h.session)
    h.agent.performance = observer
    try:
        await h.start()
        observer.wrap_output()
        for index in range(turns):
            text = (
                ("Hmm, A short answer.",)
                if index % 2 == 0
                else (
                    "A longer answer starts here.",
                    "Then another complete sentence.",
                    "The technical value remains 42.5.",
                )
            )
            h.model.pending.append(Reply(chunks=text, first_delay=delay, chunk_delay=delay))
            count = len(h.messages("assistant"))
            await input_turn(h, f"Synthetic request {index}", profile, delay)
            await eventually(lambda count=count: len(h.messages("assistant")) == count + 1)
        # Genuine interruption after first synthetic PCM, then latest-input recovery.
        old = Reply(
            chunks=("Old output.", "Never output this stale tail."), hold=True, first_delay=delay
        )
        h.model.pending.extend((old, Reply(chunks=("Updated output.",), first_delay=delay)))
        count = len(h.messages("assistant"))
        await input_turn(h, "Initial request to replace", profile, delay)
        await eventually(old.started.is_set)
        await eventually(lambda: h.model.active == 1 and h.session.agent_state == "speaking")
        await input_turn(h, "Replacement request", profile, delay)
        await eventually(old.closed.is_set)
        old.release.set()
        await eventually(lambda: len(h.messages("assistant")) == count + 2)
        assert "Never output this stale tail." not in h.agent.markers
        # Public provider error event and a failed node; native shutdown owns cancellation.
        fault = Reply(
            chunks=("Partial fault response.",),
            fail=True,
            hold=True,
            fault_status=429 if replica % 2 == 0 else None,
            fault_timeout=replica % 2 == 1,
        )
        h.model.pending.append(fault)
        await input_turn(h, "Fault injection request", profile, delay)
        await eventually(fault.started.is_set)
        fault.release.set()
        await eventually(fault.failed.is_set)
    finally:
        await h.close()
        await asyncio.sleep(0)
    report = observer.report()
    report.update(
        replica=replica,
        scripted_normal_turns=turns,
        llm_request_count=len(h.model.contexts),
        configured_stage_delay_s=delay,
        faults_injected=["synthetic_429" if replica % 2 == 0 else "synthetic_timeout"],
        resource_checks={
            "active_llm": h.model.active,
            "active_tts": h.agent.tts_active,
            "vad_streams_closed": all(s._task.done() for s in h.vad.streams),
            "real_provider_sockets": "not_exercised",
        },
    )
    assert h.model.active == h.agent.tts_active == 0
    assert not observer.active
    observer.detach()
    return report


async def run_suite(*, turns=3, concurrency=2, delay=0.005, profiles=("vad", "semantic", "stt")):
    from livekit.agents.inference.eot import transports

    before = asyncio.all_tasks()
    start = time.perf_counter()
    # Test CPU verdicts are scripted; the real mini binary has a separate smoke test.
    with patch.object(transports, "_EOT", ScriptedEOT):
        groups = []
        for profile in profiles:
            for humanization in (False, True):
                groups.extend(
                    await asyncio.gather(
                        *(
                            run_case(
                                profile=profile,
                                humanization=humanization,
                                turns=turns,
                                delay=delay,
                                replica=replica,
                            )
                            for replica in range(concurrency)
                        )
                    )
                )
    await asyncio.sleep(0)
    leaks = [
        task
        for task in asyncio.all_tasks() - before
        if not task.done() and task is not asyncio.current_task()
    ]
    assert not leaks, "Synthetic benchmark left background tasks"
    return {
        "schema_version": 1,
        "origin": "synthetic_native_session",
        "provider_latency_claim": False,
        "caller_heard_latency": None,
        "sdk_version": version("livekit-agents"),
        "python": platform.python_version(),
        "wall_duration_s": time.perf_counter() - start,
        "concurrent_replicas": concurrency,
        "semantic_prediction": "scripted probability, not speech inference",
        "leaked_task_count": len(leaks),
        "text_processing": await measure_text_processing(),
        "groups": groups,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--turns", type=int, default=3)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--delay", type=float, default=0.005)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 1 <= args.turns <= 30 or not 1 <= args.concurrency <= 8 or not 0 <= args.delay <= 0.05:
        parser.error("turns: 1..30; concurrency: 1..8; delay: 0..0.05 seconds")
    previous_logging = logging.root.manager.disable
    try:
        logging.disable(logging.CRITICAL)
        with offline_network():
            result = asyncio.run(
                run_suite(turns=args.turns, concurrency=args.concurrency, delay=args.delay)
            )
    finally:
        logging.disable(previous_logging)
    text = json.dumps(result, indent=2, allow_nan=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
        print(f"Synthetic benchmark complete: {len(result['groups'])} groups; report written.")
    else:
        print(text)


if __name__ == "__main__":
    main()
