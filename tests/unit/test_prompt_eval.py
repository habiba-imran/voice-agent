from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from types import SimpleNamespace

import pytest

from voiceagent.settings import PROJECT_ROOT, Credentials


@pytest.fixture
def evaluator():
    spec = importlib.util.spec_from_file_location(
        "prompt_evaluator", PROJECT_ROOT / "scripts/check_prompt_live.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def test_eval_requires_approval_before_creating_provider(evaluator, settings):
    def forbidden(**kwargs):
        pytest.fail("Provider construction must not occur without approval")

    with pytest.raises(PermissionError, match="approval"):
        await evaluator.run_checks(settings, [{}], model_factory=forbidden)


async def test_eval_uses_bounded_direct_stream_and_cleans_up(evaluator, settings):
    observed = {}

    class Stream:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            observed["stream_closed"] = True

        async def __aiter__(self):
            yield SimpleNamespace(delta=SimpleNamespace(content=None, reasoning="hidden thoughts"))
            yield SimpleNamespace(delta=SimpleNamespace(content="A compiler translates code."))

    class Model:
        def chat(self, **kwargs):
            observed["chat"] = kwargs
            return Stream()

        async def aclose(self):
            observed["closed"] = True

    def factory(**kwargs):
        observed["factory"] = kwargs
        return Model()

    configured = settings.model_copy(update={"credentials": Credentials(groq_api_key="synthetic")})
    results = await evaluator.run_checks(
        configured,
        [{"id": "brief", "input": "What is a compiler?"}],
        allow_billable=True,
        model_factory=factory,
    )
    assert results[0]["response"] == "A compiler translates code."
    assert all(results[0]["checks"].values())
    assert observed["closed"] and observed["stream_closed"]
    assert observed["factory"]["max_completion_tokens"] <= 256
    assert observed["factory"]["max_retries"] == 0
    assert observed["chat"]["conn_options"].max_retry == 0
    assert observed["chat"]["extra_kwargs"] == {"extra_body": {"include_reasoning": False}}


def test_eval_dry_run_sends_no_requests(tmp_path):
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts/check_prompt_live.py")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["provider_requests_sent"] == 0
    assert data["planned_requests"] == 5
