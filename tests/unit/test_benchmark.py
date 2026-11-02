"""The repeatable benchmark must remain offline, isolated, and honest about its origin."""

import importlib.util
import json
import socket
from pathlib import Path

import pytest


def benchmark_module():
    spec = importlib.util.spec_from_file_location(
        "offline_benchmark", Path(__file__).resolve().parents[2] / "scripts" / "benchmark.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_benchmark_blocks_external_connections_before_dns_or_connect():
    benchmark = benchmark_module()
    with benchmark.offline_network():
        with pytest.raises(RuntimeError, match="External networking"):
            socket.getaddrinfo("example.invalid", 443)
        with socket.socket() as sock:
            with pytest.raises(RuntimeError, match="External networking"):
                sock.connect(("192.0.2.1", 443))


async def test_concurrent_benchmark_reports_real_local_observations_and_cleanup():
    benchmark = benchmark_module()
    with benchmark.offline_network():
        report = await benchmark.run_suite(turns=1, concurrency=2, delay=0.005, profiles=("vad",))
    assert report["origin"] == "synthetic_native_session"
    assert report["provider_latency_claim"] is False
    assert report["caller_heard_latency"] is None
    assert report["leaked_task_count"] == 0
    assert len(report["groups"]) == 4
    assert len({group["session_id"] for group in report["groups"]}) == 4
    for group in report["groups"]:
        assert group["llm_request_count"] == 4  # normal, interrupted, replacement, fault
        assert group["resource_checks"]["active_llm"] == 0
        assert group["resource_checks"]["active_tts"] == 0
        assert group["resource_checks"]["vad_streams_closed"]
        assert group["counts"]["provider_errors"] == 1
        metric = group["metrics"]["eot_hook_to_sink_accept_s/completed"]
        assert metric["sample_count"] == 2
        assert metric["p95"] >= metric["p50"] >= 0.005
        assert "positive_cached_tokens" in group["unobserved"]
        assert "Synthetic request" not in json.dumps(group)
