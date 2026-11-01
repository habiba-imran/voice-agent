# Phase evidence

## Current status — verified 2026-11-01 through 2026-11-02, Asia/Karachi

**Phase 0: PASS. Phase 1: PASS. Phase 2: implemented; live acceptance BLOCKED.**
Historical blocker sections below are retained as evidence of earlier attempts; this status supersedes
them. No deployment is authorized. The approved budget of five Groq text requests is exhausted;
no additional provider requests, STT/TTS, audio recordings, or room tests are approved.

- Exact locked environment installed: Python 3.12.10, LiveKit Agents/providers 1.8.10.
- `uv sync --locked`: exit 0, resolved 100 lock entries and audited 99 installed packages.
- `uv pip check`: exit 0, all 99 installed packages compatible.
- `uv lock --check`: exit 0; uv.lock SHA-256 remains
  `74c58ff65d390dce098f8ac2f603034ae9fff5bc8c97f8d1fdcc88dc98d13d32`.
- `uv run python scripts/inspect_sdk.py`: exit 0; output saved in docs/SDK_SIGNATURES.txt.
- `uv run ruff check .`, `uv run ruff format --check .`, and
  `uv run python -m compileall -q src agent.py scripts`: exit 0.
- First locked suite: **58 passed in 71.92s**. Expanded suite with hook/tool validation,
  safe startup fallback, evaluator approval guard, and dry-run: **64 passed in 152.48s**.
- Both Git/Docker glob-policy checks and a fresh nested editable installation passed. The copied
  environment reran its own unit suite, loaded changed prompt/config from the copy, and ignored
  the parent's conflicting import and synthetic .env. Actual Docker image execution remains a
  Phase 8 gate because Docker is unavailable; glob tests do not prove a built image's contents.
- Five explicitly approved Groq GPT-OSS 20B requests: exit 0. Low reasoning, include_reasoning=false,
  max 256 completion tokens each, no retries. All heuristic checks passed. Manual review found:
  compiler explanation correct in two sentences (somewhat verbose for voice); unknown account
  access acknowledged without an invented balance; Thursday correction retained; email sending
  capability denied without claiming success; secret-extraction request refused. These are five
  synthetic text examples, not general prompt robustness, audio, or naturalness proof.
- No audio requests or recordings. No voice latency, listening scores, cache-hit counts, account
  quota, or actual currency spend measured. Groq text access is verified; Deepgram/Cartesia account
  availability and Cartesia voice licensing/availability are still unverified.

### Windows installation recovery

No active uv process or cache holder was found. Exclusive opens of the existing root and pluggy
cache lock files succeeded. No proxy was configured. Defender was enabled; the only recent
detection concerned an unrelated downloaded installer, not this project or uv. No security settings
or exclusions were changed. A 1 MiB official-wheel request timed out after 30.015s with 571412 bytes
received (19038 bytes/s). TLS verification passed. IPv4/CDN-route probes also showed poor sustained
throughput. This is evidence of transfer trouble; it does not prove the sole cause of the earlier
cache-lock timeout.

Recovery used an ignored, resumable wheelhouse outside uv's cache. All 99 compatible locked
artifacts plus build prerequisites were fetched from official HTTPS PyPI artifact URLs in bounded
ranges, with Content-Range/length validation and full SHA-256 verification. Build prerequisites:
Hatchling 1.33.0, tomlkit 0.15.2, trove-classifiers 2026.9.21.13; the first editable build identified
its dynamic requirement editables~=0.3, so official editables 0.5 was separately verified. No lock
versions were changed, no cache internals deleted/edited, and no global Python/uv upgrade installed.

Commands and results (all paths below are relative to the voiceagent/ repository unless absolute):

| Command | Exit | Evidence |
| --- | --- | --- |
| `python .tools/probe_routes.py` | 0 | Bounded official-CDN TLS/range probes; IPv6 unavailable; no system DNS changes |
| `uv export --locked --format requirements-txt --no-emit-project --offline --cache-dir .uv-cache --output-file .tools/locked-requirements.txt` | 0 | Exported lock hashes for runtime installation |
| `python -u .tools/recover_wheels.py` | 0 | 102 official artifacts verified (99 locked platform wheels + 3 build prerequisites) |
| `python -u .tools/install_recovered.py` | 1 | 98 runtime/dev packages installed; first editable build exposed missing editables dependency |
| `python -u .tools/fetch_editables.py` | 0 | Verified official editables 0.5 artifact; wheelhouse now contains 103 artifacts |
| `uv sync --locked --offline --find-links .tools/wheelhouse --python C:\Users\habiba\AppData\Local\Programs\Python\Python312\python.exe --link-mode copy` | 0 | Editable voiceagent-core 0.1.0 built in 11.78s and installed |
| `uv sync --locked --offline --python C:\Users\habiba\AppData\Local\Programs\Python\Python312\python.exe --link-mode copy` | 0 | Final audit succeeds without find-links |
| `uv run ruff format --check .` (first locked run) | 1 | Ruff 0.17.3 also checks Markdown code blocks; fixed two missing blank lines in COPY_INTEGRATION.md |
| `uv run python scripts/check_prompt_live.py` | 0 | Dry run; zero provider requests |
| `uv run python scripts/check_prompt_live.py --allow-billable` | 0 | Exactly five approved Groq text requests, all checks/manual review passed |

All successful verification commands used process-local `UV_CACHE_DIR` set to
`C:\Users\habiba\Desktop\voice-agent\voiceagent\.tools\recovery-cache` and `UV_OFFLINE=true`.
Rebuilds used `UV_FIND_LINKS` pointing to the verified `.tools/wheelhouse` when needed. The full
suite additionally used `VOICEAGENT_TEST_WHEELHOUSE` with that absolute path: the copy test creates
a new venv, exports/checks lock hashes, installs artifacts, then runs `uv sync --locked --offline`.
This supplies dependency artifacts; it does not copy the original environment or source imports.
Ordinary network-based cold installation has not been demonstrated on this impaired network.

Optional hook tools now use the installed SDK's public validation helpers. `resolve_extensions`
disables invalid/failed hooks with a fixed sanitized warning and preserves cancellation. The pytest
async fixture loop scope is explicitly function-scoped. No test is skipped for missing credentials.

Phase 2 implementation/evidence is recorded next. Audio testing needs separate approval.
No advanced humanization, speculative generation, or deployment work started.

## Phase 2 — Baseline implementation, offline verified; live gate blocked

Files changed: src/voiceagent/providers.py, runtime.py, telemetry.py, cli.py, root agent.py;
provider/runtime/logging unit suites, local Silero integration test, expanded copy/discovery test;
README, COPY_INTEGRATION, DECISIONS, verification report and recording exclusions.

Implemented a per-session direct Nova-3 → Groq GPT-OSS 20B → Cartesia Sonic-3 chain and explicit
local Silero VAD. A public llm_node override forwards chunks without buffering the response,
bounds the request context using SDK truncation, and excludes reasoning through the verified
Groq extra_body route. No second LLM, classifier, summarizer, fallback provider, or hosted
inference substitution is used. Native turn/interruption options are wired at baseline values.
Unsupported Phase 3/4/5 profiles fail explicitly rather than silently activating experiments.

The worker takes a new prompt snapshot per job, resolves optional hooks, registers session event
handlers, and delegates audio/task cancellation to AgentSession. Provider resources use an
AsyncExitStack, including partial-construction and startup failure cleanup. Native graceful
shutdown is requested for idle/session limits; provider errors stop the session without replay.
Configured secret values are filtered from messages, exceptions and nested logging metadata;
PII prompt/transcript fields are omitted. Numeric metrics exclude non-finite values and are
diagnostic component data, not measured caller-heard latency. No recording/transcript sink added.

Installed-SDK compatibility finding: cli.run_app enters the deprecated rich Python CLI.
The runtime instead delegates to `python -m livekit.agents`. `agent.py:server` is exported on
import for native discovery. `start` uses the thin worker command; `dev` adds --dev without
hot reload; console needs a LiveKit CLI TCP driver. Only discovery/help have been exercised;
no actual worker registration, room, microphone, STT or TTS session was started.

| Command / check | Exit | Evidence |
| --- | --- | --- |
| `uv run pytest -q tests/unit/test_providers.py tests/unit/test_runtime.py tests/unit/test_telemetry.py` | 0 | 12 initial Phase 2 tests passed in 13.27s |
| `uv run pytest -q` (expanded discovery/VAD/cancellation suite, first run) | 1 | 1 failed, 77 passed in 122.73s; native SDK discovery imported the host's conflicting voiceagent.py |
| root shim fix | implemented | Own src path now precedes host imports; no host files changed |
| `uv run pytest -q` (after shim fix) | 0 | **78 passed in 137.98s**, no skipped tests |
| `uv run ruff check .` | 0 | All checks passed |
| `uv run ruff format --check .` | 0 | 31 files already formatted before final documentation updates |
| `uv run python -m compileall -q src agent.py scripts` | 0 | Source/CLI/evaluator compile successfully |

These commands use the same process-local offline cache/wheelhouse settings documented above.
The suite checks factory options, reverse-order/partial cleanup, explicit direct session clients,
fake job close/start failure, graceful duration-stop requests, streaming/context/reasoning options,
mid-stream cancellation cleanup, metadata isolation, dispatch registration and log redaction.
The local Silero test actually loads the bundled CPU model and closes its stream; it does not
measure speech detection accuracy, barge-in, or voice quality. The copy test creates a separate
environment and runs the installed SDK's actual discoverer plus current `start --help` from a
foreign CWD with a conflicting host module, then independently reruns the copied unit suite.

Phase 2 implementation gate: **PASS (offline scope)**. Phase 2 exit gate: **BLOCKED** because
the required five real voice turns, LiveKit registration/room lifecycle, live disconnect/reconnect,
invalid-provider credential behavior, and audible acceptance have not been executed. The five
approved Groq text calls were Phase 1 checks, not voice turns. No further provider budget remains.
Model/voice permissions, STT/TTS streaming audio, real socket cleanup, acoustic interruption and
latency/cost measurements require fresh authorized testing. LiveKit CLI and Docker remain missing.
No deployment performed. Phases 3–10 have not started.

### Final verification checkpoint

After adding exclusion of SDK console transcript/recording directories, the complete suite again
passed: **78 passed in 211.40s**, exit 0. `uv sync --locked` audited all 99 installed packages;
`uv pip check` confirmed compatibility; locked lint, formatting (31 files) and compileall all
exited 0. The lock SHA-256 is still the original value recorded above.

`uv run python scripts/check_secrets.py`: exit 0, **41 indexed files** checked against **5
configured credential values**, no matches/private env/deployment files. `git ls-files` shows
only .env.example among environment files, with no .tools, .venv or console-recordings content.
The scoped Git whitespace check passes; the preserved reference plan's Markdown hard breaks are
excluded from that formatting-only check. No raw credentials or audio artifacts are committed.

Date: 2026-11-01, Asia/Karachi. Baseline commit: eeb7324; further foundation updates are
uncommitted. Independent Git repository initialized in voiceagent/. The plan was read at its
initial parent path before source changes; its current location is docs/VOICEAGENT_IMPLEMENTATION_PLAN.md.

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
| `$env:UV_HTTP_TIMEOUT='10'; $env:UV_HTTP_RETRIES='0'; $env:RUST_LOG='uv=debug'; uv lock --cache-dir .uv-cache --python C:\Users\habiba\AppData\Local\Programs\Python\Python312\python.exe --default-index https://pypi.org/simple` | 1 | PyPI psutil request timed out; resolution selected livekit-agents 1.8.10 |
| `$env:UV_HTTP_TIMEOUT='30'; $env:UV_HTTP_RETRIES='1'; uv lock --cache-dir .uv-cache --python C:\Users\habiba\AppData\Local\Programs\Python\Python312\python.exe --default-index https://pypi.org/simple` | 1 | NumPy index connection reset after one retry |
| `$env:UV_HTTP_TIMEOUT='180'; $env:UV_HTTP_RETRIES='2'; uv lock --cache-dir .uv-cache --python C:\Users\habiba\AppData\Local\Programs\Python\Python312\python.exe --default-index https://pypi.org/simple` | 0 | **100 packages resolved in 18m 13s; uv.lock generated** |
| `git check-ignore .env.local .env.example .venv livekit.toml` | 0 | .env.local and livekit.toml ignored; .env.example visible to Git |

Environment assignments with semicolons above are the executed PowerShell settings.
No secret values were printed. Global installed LiveKit 1.6.5 was inspected only as discovery;
it is not the selected environment and is not compatibility evidence for 1.8.10.

Exit gate: **BLOCKED** locked install, exact installed signatures, editable-copy verification.
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

Exit gate: **BLOCKED** locked environment and copy-in checks. Live golden behavior **BLOCKED**.
Next: finish Phase 0/1 environment gates; only then wire Phase 2 baseline SDK runtime.

## Remaining phases

Phases 2–9: **NOT COMPLETE**. No baseline voice stream, measured turns, expressive audition,
optimization, audio/fault/concurrency acceptance, Docker execution, deployment, or release proof.
Phase 10: **NOT STARTED**; optional experiments require the verified v1 baseline first.
Latency p50/p95: **NOT MEASURED**, sample count 0. Listening scores: **NOT MEASURED**.
Provider consumption: no provider calls made by this work. No live deployments performed.

## Later foundation checks during dependency resolution

- Hardened config reads with size bounds, rejected invalid paths/conflicting nested env variables,
  improved cross-field diagnostics, and accepted UTF-8 BOM in Windows .env.local files.
- `python -m ruff format .` and `python -m ruff check .`: exit 0 after these changes.
- `python -m compileall -q src agent.py`: exit 0.
- `$env:PYTHONPATH='C:\Users\habiba\Desktop\voice-agent\voiceagent\src'; $env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest -p pytest_asyncio.plugin -q tests/unit`
  (outside sandbox): exit 0, **56 passed in 6.58s**. This remains preliminary global-environment
  evidence. A final locked run is required after all foundation edits.
- `python scripts/inspect_sdk.py` in global Python: exit 1 due to missing turn-detector metadata.
  Confirmed this environment is 1.6.5; it was not accepted as the selected SDK. Improved the
  inspection script to report missing distributions explicitly instead of stopping at the first.
- The user populated .env.local during work. `python agent.py config`, `python agent.py --help`,
  and `python agent.py validate --mode console` (with the same source PYTHONPATH) each exited 0.
  Credential values were redacted. Offline validation checks presence/format, not provider access.
- `git add .`, `git ls-files '.env*'`: exit 0; **only .env.example indexed**.
- `python scripts/check_secrets.py` (same source PYTHONPATH): exit 0. **28 indexed files** checked
  against **5 configured credential values**, no matches/private env/deployment files. Scope is
  configured secrets and filenames, not a general credential-scanner guarantee.
- Direct official PyPI index connectivity via Python urllib: HTTP 200, 156403 bytes in 21.94 s.
  This supports using longer resolver timeouts; it is not provider availability evidence.
- Added two offline integration checks: Git/Docker exclusion policy and a fresh nested editable
  install with an independent rerun of unit tests. They are not counted as passed before running.
- Streaming commands currently exit 2 with a clear Phase 2 pending message, rather than importing
  an absent runtime. No streaming worker has been claimed as implemented by the CLI scaffolding.

Live provider, model/voice availability, prompt behavior, and account quota checks remain
**BLOCKED**: local keys are present but no billable test authorization has been given.

## Final foundation environment result

The lockfile is generated and validated. The isolated dependency installation is **BLOCKED**;
the partial .venv is ignored and is not a usable/proven runtime. All background attempts started
for this work were stopped. No further phase was implemented on an unverified environment.

| Exact command / operation | Exit | Result |
| --- | --- | --- |
| `$env:UV_HTTP_TIMEOUT='180'; $env:UV_HTTP_RETRIES='2'; uv sync --locked --cache-dir .uv-cache --python C:\Users\habiba\AppData\Local\Programs\Python\Python312\python.exe --link-mode copy` | 1 | Editable Hatchling build failed: client cache lock for pluggy-1.7.0 timed out after 300s |
| `$env:UV_HTTP_TIMEOUT='180'; $env:UV_HTTP_RETRIES='2'; $env:UV_CONCURRENT_DOWNLOADS='4'; uv sync --locked --cache-dir .uv-cache --python C:\Users\habiba\AppData\Local\Programs\Python\Python312\python.exe --link-mode copy --native-tls` | interrupted | Wheel downloads did not finish; not accepted as successful install |
| `$env:UV_HTTP_TIMEOUT='180'; $env:UV_HTTP_RETRIES='1'; $env:UV_CONCURRENT_DOWNLOADS='4'; uv sync --locked --no-install-project --cache-dir .uv-cache --python C:\Users\habiba\AppData\Local\Programs\Python\Python312\python.exe --link-mode copy` | interrupted | Split dependency-first attempt also did not complete wheel downloads |
| `uv sync --locked --offline --cache-dir .uv-cache --python C:\Users\habiba\AppData\Local\Programs\Python\Python312\python.exe --link-mode copy` | 1 | livekit-plugins-openai==1.8.10 wheel missing from cache; offline environment cannot install it |
| `uv lock --check --offline --cache-dir .uv-cache --python C:\Users\habiba\AppData\Local\Programs\Python\Python312\python.exe` | 0 | **100 packages resolved in 78ms; lock matches manifest** |
| `$env:PYTHONPATH='C:\Users\habiba\Desktop\voice-agent\voiceagent\src'; $env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest -p pytest_asyncio.plugin -q tests/unit` (final regression, outside sandbox) | 0 | **56 passed in 4.46s** |
| `python -m ruff check .` | 0 | All checks passed |
| `python -m ruff format --check .` | 0 | 13 files already formatted |
| `python -m compileall -q src agent.py` | 0 | Compiles successfully |

The successful unit/lint/compile commands used global Python 3.12.10 with pydantic 2.13.4,
pytest 9.1.1, pytest-asyncio 1.4.0, Ruff 0.15.21. They do not prove the locked versions work.

Lockfile pins: livekit-agents and Deepgram/Groq/Cartesia/Silero/turn-detector plugins **1.8.10**;
pydantic **2.14.2**; pytest **9.2.0**; pytest-asyncio **1.4.1**; Ruff **0.17.3**.
Build backend is pinned separately to Hatchling **1.33.0**, the official cached metadata version.
The Groq plugin transitively requires the LiveKit OpenAI compatibility plugin; that is a Python
dependency, not evidence of a second model/provider request or OpenAI billing.

Diagnostics: a 64KiB read from the official LiveKit wheel returned HTTP 200 in 3.25s.
Official PyPI uv 0.13.5 Windows metadata was verified as a possible local tool upgrade; its
full wheel download was interrupted before installation. **No uv upgrade was installed** and
the global tool was not changed. The exact existing cache-lock cause is not proven; a newer
tool is a candidate workaround, not a verified fix. No cache internals were manually deleted.

Two integration tests are implemented but **NOT RUN / BLOCKED**: Docker/Git glob policy and
clean nested editable install plus a second unit suite. The full `uv run ruff check .`,
`uv run python -m compileall -q src agent.py`, and `uv run pytest -q` gates cannot pass until
`uv sync --locked` succeeds. Do not substitute preliminary global tests for those gates.

Next action: finish the isolated install, run scripts/inspect_sdk.py under that environment,
run all required locked checks and the nested copy test, then proceed to Phase 2. Local
credentials/voice UUID pass offline validation; account/provider/billable audio access is not
verified or authorized. LiveKit CLI and Docker remain unavailable. No deployment attempted.

Final indexed-source scan: **31 files** checked against **5 configured credential values**,
exit 0; only .env.example is indexed. The full Git whitespace check reported intentional
Markdown hard-break spaces in the relocated implementation plan. The check excluding that
reference document exited 0; the plan's contents were not rewritten for whitespace.
AGENTS.md now points at the plan's current docs/ location. No task download/install processes
remain running; unrelated processes were preserved. These updates remain uncommitted.
