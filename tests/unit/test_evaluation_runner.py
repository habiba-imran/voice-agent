import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


def runner():
    spec = importlib.util.spec_from_file_location(
        "offline_evaluation", Path(__file__).resolve().parents[2] / "scripts/evaluate_offline.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("child", ["", "<failure/>", "<error/>", "<skipped/>"])
def test_reports_never_promote_failure_skips_or_missing_tests_to_pass(child):
    module = runner()
    xml = (
        '<testsuites><testsuite><testcase classname="tests.unit.test_sdk_runs">'
        f"{child}</testcase></testsuite></testsuites>"
    )
    report = module.summarize(xml, ["conversation"], 0)
    assert report["status"] == ("PASS_OFFLINE" if not child else "FAIL_OR_INCOMPLETE")
    assert module.summarize(xml, ["audio_signals"], 0)["status"] == "FAIL_OR_INCOMPLETE"
    assert module.summarize(xml, ["conversation"], 1)["status"] == "FAIL_OR_INCOMPLETE"


def test_child_environment_strips_provider_and_host_overrides():
    env = runner().child_environment(
        {
            "GROQ_API_KEY": "synthetic",
            "LIVEKIT_URL": "synthetic",
            "VOICEAGENT_CONFIG_PATH": "untrusted",
            "PYTEST_ADDOPTS": "-k no_tests",
            "PYTHONPATH": "untrusted",
            "UV_OFFLINE": "false",
            "PATH": "tools",
        }
    )
    assert env == {"UV_OFFLINE": "true", "PATH": "tools"}


def test_list_command_is_offline_and_category_files_exist():
    module = runner()
    for names in module.CATEGORIES.values():
        assert all((module.ROOT / "tests/unit" / f"{name}.py").is_file() for name in names)
    result = subprocess.run(
        [sys.executable, str(module.ROOT / "scripts/evaluate_offline.py"), "--list"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0
    assert set(json.loads(result.stdout)) == set(module.CATEGORIES)


def test_prepared_cloud_scenario_structure_is_local_only():
    import re

    import yaml

    source = runner().ROOT / "evals/livekit_scenarios.yaml"
    data = yaml.safe_load(source.read_text(encoding="utf-8"))
    assert re.fullmatch(r"SCNG_[A-Za-z0-9]{12}", data["id"])
    assert len(data["scenarios"]) == 5
    assert len({scenario["id"] for scenario in data["scenarios"]}) == 5
    for scenario in data["scenarios"]:
        assert re.fullmatch(r"SCN_[A-Za-z0-9]{12}", scenario["id"])
        assert scenario["instructions"] and scenario["agent_expectations"]
        assert set(scenario) == {"id", "label", "instructions", "agent_expectations", "tags"}
    # Shape checks cannot certify the remote CLI schema or a simulation verdict.
