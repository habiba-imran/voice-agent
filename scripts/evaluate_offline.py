"""Run deterministic regression categories and write numeric evidence, never live requests."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = {
    "conversation": ("test_sdk_runs", "test_turn_behavior"),
    "audio_signals": ("test_audio_scenarios",),
    "delivery": ("test_expression", "test_delivery_evaluation", "test_cartesia_wire"),
    "performance": ("test_performance", "test_benchmark", "test_preemptive"),
    "failures": ("test_provider_failures", "test_reliability", "test_session_management"),
    "security": ("test_security",),
}


def child_environment(environ):
    env = {
        key: value
        for key, value in environ.items()
        if not key.startswith(("VOICEAGENT_", "LIVEKIT_"))
        and key
        not in {
            "GROQ_API_KEY",
            "DEEPGRAM_API_KEY",
            "CARTESIA_API_KEY",
            "PYTHONPATH",
            "PYTEST_ADDOPTS",
            "PYTEST_PLUGINS",
        }
    }
    env["UV_OFFLINE"] = "true"
    return env


def summarize(xml, categories, returncode):
    root = ET.fromstring(xml)
    reports = {}
    for category in categories:
        cases = [
            case
            for case in root.iter("testcase")
            if any(
                case.get("classname", "").split(".")[-1] == module
                for module in CATEGORIES[category]
            )
        ]
        failures = sum(case.find("failure") is not None for case in cases)
        errors = sum(case.find("error") is not None for case in cases)
        skipped = sum(case.find("skipped") is not None for case in cases)
        reports[category] = {
            "junit_case_reports": len(cases),
            "failures": failures,
            "errors": errors,
            "skipped": skipped,
            "status": "PASS_OFFLINE"
            if cases and not (failures or errors or skipped)
            else "FAIL_OR_INCOMPLETE",
        }
    return {
        "status": "PASS_OFFLINE"
        if returncode == 0 and all(item["status"] == "PASS_OFFLINE" for item in reports.values())
        else "FAIL_OR_INCOMPLETE",
        "pytest_exit_code": returncode,
        "categories": reports,
    }


def evaluate(categories):
    files = [
        f"tests/unit/{module}.py" for category in categories for module in CATEGORIES[category]
    ]
    with tempfile.TemporaryDirectory(prefix="voiceagent-offline-eval-") as temporary:
        xml = Path(temporary) / "tests.xml"
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", *files, f"--junitxml={xml}"],
                cwd=ROOT,
                env=child_environment(os.environ),
                capture_output=True,
                timeout=240,
                check=False,
            )
            # Do not persist stdout, exception payloads, transcripts, or the raw XML.
            report = summarize(xml.read_text(encoding="utf-8"), categories, result.returncode)
        except (subprocess.TimeoutExpired, OSError, ET.ParseError):
            report = {
                "status": "FAIL_OR_INCOMPLETE",
                "pytest_exit_code": None,
                "reason": "execution_timeout_or_missing_report",
                "categories": {},
            }
    report.update(
        {
            "schema_version": 1,
            "origin": "offline_scripted_evaluation",
            "sdk_version": version("livekit-agents"),
            "python_version": platform.python_version(),
            "prompt_sha256": hashlib.sha256((ROOT / "prompt.md").read_bytes()).hexdigest(),
            "signal_manifest_sha256": hashlib.sha256(
                (ROOT / "tests/fixtures/audio_scenarios.json").read_bytes()
            ).hexdigest(),
            "real_provider_requests": 0,
            "caller_heard_latency": None,
            "listening_scores": None,
            "live_acceptance": "BLOCKED",
            "coverage": "selected regression categories; use full pytest for release gates",
        }
    )
    # The same tested transform comparison, without synthesis or an LLM judge.
    sys.path.insert(0, str(ROOT / "tests/unit"))
    from audio_fixtures import catalog, frames
    from delivery_evaluation import evaluate_delivery

    report["delivery_ab"] = asyncio.run(evaluate_delivery())
    report["signal_checksums"] = {}
    for scenario in catalog()["scenarios"]:
        digest = hashlib.sha256()
        for frame in frames(scenario):
            digest.update(frame.data)
        report["signal_checksums"][scenario["id"]] = digest.hexdigest()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--category", action="append", choices=sorted(CATEGORIES))
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    categories = list(dict.fromkeys(args.category or CATEGORIES))
    if args.list:
        print(json.dumps({key: CATEGORIES[key] for key in categories}, indent=2))
        return
    report = evaluate(categories)
    text = json.dumps(report, indent=2, allow_nan=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
        print(f"{report['status']}: {len(report['categories'])} categories; report written.")
    else:
        print(text)
    raise SystemExit(0 if report["status"] == "PASS_OFFLINE" else 1)


if __name__ == "__main__":
    main()
