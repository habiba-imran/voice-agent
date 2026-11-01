# Phase evidence

Date: 2026-11-01, Asia/Karachi. No commit created. Independent Git repository initialized in
voiceagent/. The parent implementation plan is preserved unchanged.

## Phase 0 — Research and environment (in progress)

Changed: pyproject.toml, ignore files, .python-version, AGENTS.md, README.md,
docs/DECISIONS.md, scripts/inspect_sdk.py, package/CLI scaffolding.

Official docs checked: all four providers, LiveKit sessions/turn handling/expressive mode,
and deployment/secrets (links and specific decisions in DECISIONS.md).

Commands / observed results:

| Exact command or operation | Exit | Actual evidence |
| --- | --- | --- |
| `git status --short` (parent workspace) | 1 | Not a Git repository; only implementation plan existed |
| `python --version` | 0 | Python 3.12.10 |
| `uv --version` | 0 | uv 0.10.6 |
| `lk --version`, `docker --version` | unavailable | Executables missing/on PATH |
| Python urllib GET https://pypi.org/pypi/livekit-agents/json | 0 after escalation | 1.8.10; requires Python >=3.10,<3.15 |
| `git init` (voiceagent/) | 0 | Independent repository created |
| `uv lock` | 1 | Sandbox denied interpreter cache persistence |
| `uv lock --python C:\Users\habiba\AppData\Local\Programs\Python\Python312\python.exe --index-url https://pypi.org/simple --verbose` | interrupted | Slow resolution; no lock claimed |
| `uv lock --cache-dir .uv-cache --python C:\Users\habiba\AppData\Local\Programs\Python\Python312\python.exe --default-index https://pypi.org/simple --native-tls` | interrupted | Resolution continued slowly |
| `uv lock --no-cache --python C:\Users\habiba\AppData\Local\Programs\Python\Python312\python.exe --default-index https://pypi.org/simple` | interrupted | No lock claimed |
| `uv lock --offline --cache-dir .uv-cache --python C:\Users\habiba\AppData\Local\Programs\Python\Python312\python.exe -vv` | 1 | Insufficient cached package metadata |
| `UV_HTTP_TIMEOUT=10 UV_HTTP_RETRIES=0 RUST_LOG=uv=debug uv lock --cache-dir .uv-cache --python ... --default-index https://pypi.org/simple` | 1 | PyPI psutil request timed out; resolution selected livekit-agents 1.8.10 |
| `UV_HTTP_TIMEOUT=30 UV_HTTP_RETRIES=1 uv lock --cache-dir .uv-cache --python ... --default-index https://pypi.org/simple` | pending | Ongoing resolution with downloaded metadata retained |
| `git check-ignore .env.local .env.example .venv livekit.toml` | 0 | .env.local and livekit.toml ignored; .env.example visible to Git |

The two command rows with `...` use the same explicit Python312/python.exe path as preceding
rows. Environment assignments above are shorthand for PowerShell `$env:NAME = 'value'`.
No secret values were printed. Global installed LiveKit 1.6.5 was inspected only as discovery;
it is not the selected environment and is not compatibility evidence for 1.8.10.

Exit gate: **PENDING** locked install, exact installed signatures, editable-copy verification.
External account capabilities: **BLOCKED** (credentials/voice selection/credit authorization).

## Phase 1 — Settings, prompt, extension boundary (offline implementation)

Changed: settings.py, prompts.py, hooks.py, cli.py, config.example.yaml, prompt.md,
.env.example and ignored empty .env.local, tests/unit, synthetic dialogue fixtures.

Implemented: typed settings; source precedence; no YAML credentials; redacted effective config;
Nova/Flux invariants; bounded UTF-8 prompt snapshots per session; generic speech policy;
explicit async setup hook with bounded metadata, timeout and cancellation propagation.
No core business tools or hidden hook discovery. Markup/laughter/preemptive TTS are rejected.

Verification to date (preliminary global Python environment only):

| Command | Exit | Evidence |
| --- | --- | --- |
| `python -m compileall -q src agent.py` | 0 | Sources compile |
| `python -m ruff check .` (first run) | 1 | Four lint findings; fixed |
| `python -m ruff check .` (after fix) | 0 | All checks passed |
| `python -m ruff format --check .` | 1 | Four files needed formatting |
| `python -m ruff format .` | 0 | Four reformatted, six unchanged |
| `PYTHONPATH=<project>/src PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -p pytest_asyncio.plugin -vv -s tests/unit/test_settings.py` (sandbox) | 1 | 32 fixture errors: sandbox cannot create pytest temporary directories |
| `PYTHONPATH=<project>/src PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -p pytest_asyncio.plugin -q` (outside sandbox) | 0 | **52 passed in 2.57s** |

PYTHONPATH above was the explicit absolute path C:/Users/habiba/Desktop/voice-agent/voiceagent/src.
Two earlier quiet sandbox pytest runs were interrupted after the same temp-directory issue;
neither is counted as passed. No microphone/provider calls were made.

Prompt tests verify the policy contract and immutable snapshots. They do **not** establish that
Groq obeys the speech policy. Synthetic dialogue golden cases are provided for later execution;
actual LLM-generated concise/uncertainty/context/tool-truth checks remain **BLOCKED**.

Exit gate: **PENDING** locked environment and copy-in checks. Live golden behavior **BLOCKED**.
Next: finish Phase 0/1 environment gates; only then wire Phase 2 baseline SDK runtime.

## Remaining phases

Phases 2–9: **NOT COMPLETE**. No baseline voice stream, measured turns, expressive audition,
optimization, audio/fault/concurrency acceptance, Docker execution, deployment, or release proof.
Phase 10: **NOT STARTED**; optional experiments require the verified v1 baseline first.
Latency p50/p95: **NOT MEASURED**, sample count 0. Listening scores: **NOT MEASURED**.
Provider consumption: no provider calls made by this work. No live deployments performed.
