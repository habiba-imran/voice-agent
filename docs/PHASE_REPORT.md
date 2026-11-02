# Phase evidence

## Current status — verified 2026-11-01 through 2026-11-02, Asia/Karachi

**Phase 0: PASS. Phase 1: PASS. Phase 2: implemented; live acceptance BLOCKED.**
**Phase 3: offline implementation/verification PASS; overall acceptance BLOCKED.**
**Phase 4: offline implementation/verification PASS; live acceptance BLOCKED.**
**Phase 5: offline implementation/verification PASS; live performance acceptance BLOCKED.**
**Phase 6: offline implementation/verification PASS; live reliability/security acceptance BLOCKED.**
**Phase 7: offline implementation/verification PASS; real-audio/hosted acceptance BLOCKED.**
**Phase 8: offline artifacts/tests PASS; Docker/CLI/live deployment acceptance BLOCKED.**
Historical blocker sections below are retained as evidence of earlier attempts; this status supersedes
them. No deployment is authorized. The approved budget of five Groq text requests is exhausted;
no additional provider requests, STT/TTS, audio recordings, or room tests are approved.

Phase 5 offline work is authorized separately on 2026-11-02. Its implementation and verification
record appears at the end of this report; no synthetic measurement closes the live gates above.

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
The Phase 3 continuation below is explicitly authorized for offline work despite Phase 2's live
blocker. No advanced humanization, speculative generation, or deployment work started.

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

## Phase 3 — Native turn-taking and interruption recovery, 2026-11-02

Scope: user explicitly authorized offline implementation while Phase 2's live gate remains
blocked. **Offline implementation complete; overall Phase 3 NOT COMPLETE.** The five Groq
requests from the previous phase remain exhausted. No further Groq, Deepgram, Cartesia, LiveKit
Cloud inference, live room, microphone, recording or deployment action was performed here.

Changed files:

- `src/voiceagent/turns.py` (new): centralized public TurnHandlingOptions, local Silero factory,
  local audio-detector selection/prewarm; no custom interruption engine.
- `settings.py`, `config.example.yaml`: typed VAD/endpointing/Flux/adaptive/recovery controls,
  cross-profile validation, explicit Cloud opt-in, adaptive credential checks.
- `providers.py`, `runtime.py`, `telemetry.py`: separate direct STTv2 path, native options and
  detector prewarm, numeric interruption metrics and payload-free false-recovery logging.
- `scripts/inspect_sdk.py`, `docs/SDK_SIGNATURES.txt`: refreshed actual installed public APIs.
- `tests/unit/turn_harness.py`, `test_turn_behavior.py`, `test_turn_settings.py` (new), provider
  and telemetry tests, `tests/integration/test_local_turn_detector.py` (new), and conftest.
- `docs/TUNING.md` (new), README, COPY_INTEGRATION, DECISIONS, PHASE_REPORT, VERIFICATION_REPORT.
  Dependencies, `uv.lock`, prompt and existing secrets were not changed.

### Installed API and behavior evidence

Public APIs used: `AgentSession(turn_handling=...)`, `TurnHandlingOptions`, `EndpointingOptions`
(`fixed`/`dynamic`, `alpha`, delay bounds), `InterruptionOptions` (VAD/adaptive, duration/word
gates, boundary controls, discard, recovery timeout/resume), direct `deepgram.STTv2`,
`silero.VAD.load`, `inference.TurnDetector(version="v1-mini")`, and local `init_eot()` prewarm.
Native session speech handles/interrupt, output pause/resume/clear, streaming cancellation and
history trimming remain SDK responsibilities. No competing classifier, cancellation loop,
custom speech repair, extra LLM request, advanced emotion or filler system was introduced.

The deprecated text detector was initially considered but replaced after actual SDK inspection;
no deprecated plugin is imported by the implementation. The local audio detector is explicitly
pinned to mini rather than environment-driven Cloud auto-selection. Its real installed binary
loads and predicts on synthetic silence without external networking. This establishes no
human-speech accuracy. Semantic profile validation enforces Silero's SDK-required minimum
0.25-second silence. Defaults remain Nova/VAD, fixed 0.5/3-second bounds, 0.5-second interruption
minimum and 2-second false recovery. Dynamic Nova endpointing and Flux are selectable.

Flux uses direct STTv2 and `turn_detection="stt"`; Nova's semantic detector is absent. Fixed SDK
endpoint waits are set to zero for Flux because omitting them retains the SDK's 0.5-second
default after provider EOT. A native behavior test verifies VAD/final transcript alone does not
commit a Flux turn, but provider END_OF_SPEECH does. Provider timeout/threshold defaults are
not inferred from stale docstrings; current official differences are documented in DECISIONS.

Adaptive mode requires explicit `allow_cloud_inference=true` plus LiveKit keys. Its real Cloud
service was not called. Controlled verdicts traverse the real SDK overlap/STT gate; an injected
unrecoverable adaptive error exercises its native VAD fallback. VAD alone cannot reliably
classify short acknowledgments. Recovery also needs a pause-capable audio sink. Production
preserves native AEC warmup (normally the first three seconds of agent speech); synthetic tests
disable it through the public constructor because their PCM cannot echo. First-turn acoustic
barge-in is therefore explicitly unverified.

### Exact verification commands and results

Repository: `C:\Users\habiba\Desktop\voice-agent\voiceagent`. All successful locked commands
used the process-local settings below, never edits to global settings or `.env.local`:

```powershell
$env:UV_CACHE_DIR="$PWD\.tools\recovery-cache"
$env:UV_OFFLINE='true'
$env:VOICEAGENT_TEST_WHEELHOUSE="$PWD\.tools\wheelhouse"
```

Tests ran outside the Windows sandbox because pytest temporary-directory creation inside it
failed. External DNS/socket connections are denied by an autouse test fixture; IPv4/IPv6
loopback is allowed because Windows asyncio creates its wakeup socket pair there. The copied
suite inherits that fixture and strips all real provider/LiveKit credentials from subprocesses.

| Exact command | Exit | Evidence |
| --- | --- | --- |
| `uv sync --locked` | 0 | 100 lock entries resolved; 99 installed packages audited |
| `uv pip check` | 0 | All 99 installed packages compatible |
| `uv run ruff format .` | 0 | New/edited sources formatted; final pass left 37 files unchanged |
| `uv run ruff check .` | 0 | All checks passed after fixing test helper lint findings |
| `uv run ruff format --check .` | 0 | 37 files already formatted |
| `uv run python -m compileall -q src agent.py scripts tests` | 0 | All source, scripts and tests compile |
| `uv run python scripts/inspect_sdk.py` | 0 | Actual 1.8.10 signatures refreshed, including current detector/interrupt/audio APIs |
| `uv run pytest -q tests/unit/test_turn_behavior.py tests/unit/test_turn_settings.py tests/unit/test_providers.py tests/integration/test_local_turn_detector.py -x --durations=5` | 0 | Intermediate 38 passed in 49.57s |
| `uv run pytest -q tests/unit/test_turn_behavior.py -k semantic tests/unit/test_turn_settings.py tests/unit/test_telemetry.py -x` | 0 | After semantic harness fix: 4 passed, 38 deselected in 13.13s; this was a targeted filter |
| `uv run pytest -q --durations=5` | 0 | **121 passed, 0 failed, no skips in 234.71s** |
| Clean-copy test within full suite | 0 | New venv/hash-locked editable install, actual SDK discovery/start help, foreign CWD/host collision, independent copied unit suite; 175.38s |
| Git/Docker exclusion-policy test within full suite | 0 | Private env/deployment/audio/transcript/cache exclusions preserved; .env.example remains Git eligible |
| `Get-FileHash -Algorithm SHA256 uv.lock` | 0 | Original hash unchanged: `74c58ff65d390dce098f8ac2f603034ae9fff5bc8c97f8d1fdcc88dc98d13d32` |
| `git diff --check -- . ':(exclude)docs/VOICEAGENT_IMPLEMENTATION_PLAN.md'` | 0 | No whitespace errors outside unchanged reference plan |

SDK capture used `$sdkOutput = & uv run python scripts/inspect_sdk.py; $sdkExit = $LASTEXITCODE`
and wrote SDK_SIGNATURES.txt with UTF-8 only after checking exit 0. The full suite's result is
the parent test count; the copied unit rerun is additional independent evidence, not added to
121 as though it were another set of test cases. Test durations are execution wall times, not
voice latency measurements. Final source secret-scan evidence is recorded below.

Development failures were observed and corrected, not counted as passes:

- First targeted collection failed (exit 1): relative helper import without a package. Fixed
  test module discovery. Next sandbox attempt failed creating pytest temp directories (exit 1);
  reran with authorized filesystem access.
- First native run: 1 failed/1 teardown error in 11.79s (exit 1). Assertions incorrectly assumed
  provider chunk boundaries survive native text transforms and counted pytest's own finalizer
  as a leaked task. Corrected the harness, without weakening checks for SDK/provider tasks.
  A subsequent chunk-count assertion still failed (1 failed in 24.70s, exit 1); replaced it
  with an assertion that every actual generated PCM marker is delivered in order.
- Next run: 1 failed/3 passed in 21.97s (exit 1). Synthetic interruptions were suppressed by
  the SDK's real initial AEC warmup. Disabled that feature only in the no-echo harness.
- An overly broad socket block prevented Windows asyncio's loopback setup (1 error in 10.20s,
  exit 1). Permitted loopback while retaining external-network denial. A subsequent 9-test
  behavior run passed (exit 0; reported 2915.25s wall time, not a performance result).
- Initial Ruff check found three test helper issues (loop-variable capture and two async
  helper rules), exit 1. Bound the loop variable; bounded predicate observation is documented
  with one test-only ASYNC110 suppression; final lint passes.
- Expanded run: 1 failed/16 passed in 53.04s (exit 1). Scripted semantic silence was 100 ms,
  below the SDK's 200 ms prediction trigger. Corrected the event to 300 ms and added the
  corresponding production Silero minimum-silence invariant. Targeted and full suites pass.
- Read-only sandbox CIM process inspection was denied (exit 1); authorized inspection of
  process IDs/CPU times succeeded (exit 0). No process was terminated or environment printed.

### Behavior coverage and remaining gates

| Requested behavior | Offline evidence | Real acceptance |
| --- | --- | --- |
| Normal complete turn, ordered replies | Actual session commits once and streams PCM markers | BLOCKED: real five-turn baseline |
| Hesitation/short silence and continuation | Pending endpoint decision cancels; transcript combines into one turn | BLOCKED: one-second pause, filler, breath and short yes audio |
| Long pause / incomplete turn | Negative scripted mini prediction selects max delay; continued speech or bound produces one reply; dynamic delay learns within bounds | BLOCKED: premature-EOT and EOU distributions |
| Interruption before first token / during LLM stream | Native speech interruption closes old stream; unspoken tail absent from history/playout | BLOCKED: provider/transport cancellation |
| Interruption during TTS | Native clear stops obsolete synthetic output; supplied played prefix retained as interrupted history | BLOCKED: early/late real chunks and playback clock |
| Noise / abandoned speech | Pause then resume same handle/generation without an extra LLM call | BLOCKED: real cough/noise/very short speech |
| Backchannels | Controlled adaptive yeah/hmm/right verdicts gate STT without another reply; word gate behavior verified | BLOCKED: acoustic intent and boundary accuracy |
| Adaptive service failure | Native error path falls back to VAD and accepts a new genuine turn | BLOCKED: actual authentication/quota/network behavior |
| Rapid consecutive interruptions | Three ordered requests, prior handles interrupted, only current generation active | BLOCKED: real overlaps/reconnect |
| Failure/cancellation and active shutdown | Provider failure actually raised; native cleanup/cancellation closes streams | BLOCKED: real sockets and provider resources |
| No duplicates/stale generation/shared state | Ten scripted turns, bounded context, no stale tail, per-session harness and context isolation | BLOCKED: ten real coherent/brief conversational turns |
| No background task/resource leaks | Each native harness checks task delta and active provider/TTS counters; adaptive streams closed | BLOCKED: real transport soak/lifecycle |
| Configuration and portability | Validation, direct factory, local binary, clean-copy and exclusion checks | PASS for offline scope |

All requested offline Phase 3 work is implemented and verified. To close live gates, obtain
fresh provider/LiveKit test approval,
then first execute Phase 2's five voice turns/room lifecycle, followed by the Phase 3 acoustic
matrix and the real ten-turn coherence script. Quantify early cutoffs, false stops/backchannels,
EOU and audio-to-stop with sample counts; do not infer them from scripted probabilities or PCM.
Recording requires separate consent. Nova vs mini vs Flux A/B and adaptive service access remain
BLOCKED. Keep the default profile unchanged until those comparisons justify a change.

Final source checks: `git add .` exited 0, then `uv run python scripts/check_secrets.py`
exited 0: **47 indexed files** checked against **5 configured credential values**, no matches
or private env/deployment identities indexed. `git ls-files '.env*' '.venv/*' '.tools/*'
'console-recordings/*'` exited 0 and listed only `.env.example`. This scanner checks configured
values/filenames, not arbitrary unknown credentials. `git diff --cached --check -- .
':(exclude)docs/VOICEAGENT_IMPLEMENTATION_PLAN.md'` exited 0. After documentation changes,
`uv sync --locked`, `uv run ruff check .`, `uv run ruff format --check .`, and
`uv run python -m compileall -q src agent.py scripts tests` each exited 0 again (37 formatted
files). No dependency or source-code changes occurred after the passing full suite.

No EOU p50/p95, audio-to-stop, speech clipping rate, listening score or live latency improvement
was measured. Phase 2's live exit gate remains BLOCKED. Phase 3's offline gate passes, but its
required acoustic/semantic/coherence exit gates remain BLOCKED. Phase 4 has not started.

## Phase 4 — Optional direct-provider speech humanization, 2026-11-02

The user authorized offline Phase 4 implementation despite still-blocked Phase 2/3 live gates.
No new Groq, Deepgram, Cartesia, adaptive Cloud or real room request was made. No microphone,
recording, deployment, secrets edit, model audition or dependency upgrade occurred. Humanization
remains off by default. The offline gate passes; the overall Phase 4 acceptance gate remains
BLOCKED on real listening and earlier live acceptance.

Files changed: `src/voiceagent/expression.py` (new), settings.py, providers.py, runtime.py,
config.example.yaml, prompt.md, scripts/inspect_sdk.py, docs/SDK_SIGNATURES.txt; new unit
test_expression.py and test_cartesia_wire.py; provider/native turn regression tests; README,
DECISIONS, TUNING, VERIFICATION_REPORT; new docs/HUMANIZATION.md and evals/humanization_ab.md.
Earlier Phase 3 staged changes were preserved. The plan, existing secrets and uv.lock are unchanged.

### Implementation and capability decisions

- Validated optional style, auto/static emotion, speed/volume overrides, bounded application
  pace presets, leading-filler cap/cooldown and disfluency settings. Active markup, timed
  pauses, laughter, numeric pitch and emotion intensity are unavailable/rejected, not guessed.
- Direct Cartesia constructor controls remain the provider path. Auto omits the emotion field;
  the existing Groq wording and Sonic emotional subtext supply context. Static emotions use
  the verified generation_config route. No extra classifier, LLM call or round trip is added.
  Native TTS options are snapshots per stream; no shared mid-stream mutation or per-turn
  client recreation is introduced. Expressive Inference mode remains false.
- Stable delivery instructions follow the editable prompt and precede untrusted session
  metadata. Language guidance permits restrained curiosity, excitement, thoughtfulness and
  empathy without forced fillers, fake mistakes or claims of internal deliberation.
- A small prefix limiter never invents a filler. It removes repeated/over-budget leading
  hmm/uh/um/umm, normalizes permitted prefixes to comma/space and treats um/umm as one family.
  Empty/tool-only output does not advance the cooldown. This is generated-text accounting,
  not caller-heard frequency proof. Meaningful well/actually/you-know and body content are
  preserved; broader filler constraints remain prompt guidance.
- Bounded recognition strips known speech-control tags and stage tokens before both speech
  and displayed history, including split/escaped/nested controls. Plain technical text,
  factual numbers, URLs, identifiers and unknown type expressions stay intact. Removed controls
  preserve adjacent word boundaries. Incomplete recognized tags discard ambiguous attributes
  through newline/EOF; arbitrary malformed XML is not promised a lossless repair.
- Streaming remains incremental with no full-response buffer, additional queue/task/timer,
  sleep or audio middleware. Input tool/usage metadata survives unchanged; cancellation
  discards pending fragments. Native LiveKit barge-in, recovery and history machinery stays
  responsible for conversation state. CPU/first-audio overhead has not been benchmarked.
- Plain-text/neutral fallback is available by disabling the feature or selecting neutral
  settings. Unsupported configuration fails before requests. No automatic provider replay,
  retry or switch follows a partial speech failure.

Official controls/markup/direct-plugin/Inference-expressive docs were rechecked (DECISIONS links).
Public API inspection added TTS.update_options, TTS.stream, TTS.aclose and Agent.default.tts_node.
Actual installed plugin tests replace only WebSocket connection creation with an in-memory peer,
retaining real serializers, tokenizer, PCM emitter and ConnectionPool. These tests verify
snapshot semantics, guidance/omission fields, raw tag forwarding, distinct contexts, pool reuse,
cancellation and closure. They do not verify real networking or how Cartesia interprets tags.
SDK source allows a looser speed ceiling than current docs; the existing 1.5 cap is retained.

### Verification commands and observed results

All locked commands ran in the repository with the same process-local settings as Phase 3:

```powershell
$env:UV_CACHE_DIR="$PWD\.tools\recovery-cache"
$env:UV_OFFLINE='true'
$env:VOICEAGENT_TEST_WHEELHOUSE="$PWD\.tools\wheelhouse"
```

Tests used authorized Windows temp-directory access; the existing autouse fixture denies external
DNS/socket connections and the clean-copy child strips real provider credentials. Test timings
are wall-clock test execution, not voice measurements.

| Exact command | Exit | Actual result |
| --- | --- | --- |
| `uv run pytest -q tests/unit/test_expression.py tests/unit/test_providers.py -x` | 0 | Initial humanization suite: 54 passed in 22.17s |
| `uv run pytest -q tests/unit/test_cartesia_wire.py tests/unit/test_turn_behavior.py -x --durations=5` (first) | 1 | 1 failed, 2 passed in 15.59s; fake streaming input had not been flushed before waiting for a packet |
| Same command after fake-input flush | 1 | 1 failed, 26 passed in 77.05s; expected interrupted text omitted an allowed trailing space |
| `uv run pytest -q --durations=5` (first complete run) | 0 | 182 passed in 270.08s, no failures/skips; clean-copy test 200.64s |
| Final-review word-boundary correction | implemented | Stripping a control between adjacent words now preserves separation; added split-point regressions |
| `uv run pytest -q tests/unit/test_expression.py -x` (after correction) | 0 | 56 passed in 5.94s |
| `uv run pytest -q --durations=5` (after correction) | 0 | **186 passed, 0 failed, no skips in 254.88s**; clean-copy test 186.31s |
| `uv run ruff check .` | 0 | Initial import order finding fixed; fake WebSocket timeout parameters retain API-compatible names with scoped test-only ASYNC109 notes |
| `uv run ruff format --check .` | 0 | 42 files formatted after source/test/docs additions |
| `uv run python -m compileall -q src agent.py scripts tests` | 0 | Source/scripts/tests compile; repeated successfully after word-boundary correction |
| `uv sync --locked`, `uv pip check` | 0 each | 100 lock entries, 99 installed packages, all compatible |
| `uv run python scripts/inspect_sdk.py` | 0 | Public signatures captured without contacting providers |
| `Get-FileHash -Algorithm SHA256 uv.lock` | 0 | Unchanged original `74c58ff65d390dce098f8ac2f603034ae9fff5bc8c97f8d1fdcc88dc98d13d32` |

The SDK capture checked LASTEXITCODE before writing SDK_SIGNATURES.txt as UTF-8. First Ruff
checks also reported one import-order issue and then two timeout-parameter rules in test API
substitutes; each exited 1 before correction. Final lint passes. No failed attempt is counted
as a passed gate. The first complete 182-test run exposed no failures; the subsequent boundary
change was a source-review finding, so the full suite was rerun and passed all 186 tests.

The complete suite includes clean-copy hash-locked editable installation and an independent
copied unit rerun, Git/Docker exclusion-policy checks, local CPU model checks and all new
humanization regressions. The copied test count is not added again to 186. Native session
tests run humanization both off and on for normal streaming, genuine barge-in and false recovery;
mid-tag interruption also verifies no stale speech or history and no background task leak.
Table-driven split tests cover plain technical/factual content, controls, malformed input,
filler spacing/repetition/isolation, cancellation, tool/usage metadata and neutral fallback.

Final `uv sync --locked`, `uv pip check`, `uv run ruff check .`, `uv run ruff format --check .`
and `uv run python -m compileall -q src agent.py scripts tests` all exited 0 (42 formatted
files, 99 compatible installed packages). `git add .` and `uv run python scripts/check_secrets.py`
exited 0: **52 indexed files** checked against **5 configured credential values**, no matches
or private env/deployment identities. `git ls-files '.env*' '.venv/*' '.tools/*'
'console-recordings/*'` exited 0, listing only `.env.example`. The scanner covers configured
values/filenames, not unknown arbitrary secrets. `git diff --cached --check -- .
':(exclude)docs/VOICEAGENT_IMPLEMENTATION_PLAN.md'` exited 0. Existing secrets remain untouched.

The revised prompt's raw UTF-8 SHA-256 is
`4361295de1fe95ed37997f26238b26893471783f1322232e7ce28c48cac2a4d2`.
The previous five approved Groq examples used the earlier prompt; they are not verification of
this revision or its added delivery instructions. No additional provider budget is authorized.

### Remaining live acceptance

Prepared `evals/humanization_ab.md`: authorized 3–5 voice audition, identical-text voice/control
comparisons plus a twelve-turn interactive content matrix, at least 30 comparable warm turns
and five separately reported cold trials per measured configuration. Human listeners must score
naturalness/prosody/emotion/pause/filler/intelligibility/interruption behavior and note facts,
repetition and acoustic artifacts. No score is prefilled. Audio persistence needs separate consent.

Real voice availability, license/account access, contextual audible emotion, pitch/intonation,
intelligibility, pause quality, caching/usage/cost and actual interruption responsiveness remain
BLOCKED. No latency percentiles, acoustic scores or quality improvement were measured. Known
limits: no pitch/intensity API, no active markup/nonverbals, no dynamic per-chunk controls, narrow
leading-filler enforcement and no general malformed-XML sanitizer. Do not choose new defaults
or mark Phase 2/3/4 live acceptance complete from these offline tests. **Phase 4 offline
implementation is complete and verified; overall Phase 4 acceptance is BLOCKED.** Phase 5 has
not started. No provider-backed audio was produced or persisted and no deployment was attempted.

## Historical foundation entries (superseded by current status above)

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

## Phase 5 — offline performance work, 2026-11-02

Authorization: the user explicitly requested Phase 5 offline work while Phase 2–4 live acceptance
remains blocked. All real provider/network room usage, recording and deployment remain forbidden.
The previous five-request Groq authorization is exhausted. No credentials were changed or printed.

### Changes and evidence

- New `src/voiceagent/performance.py`: bounded per-session observations, public turn/speech hooks,
  numeric SDK metrics/usage, monotonic sink-acceptance/completion estimates, timeout/cancellation/
  failure counts, shortened correlation IDs, per-outcome p50/p95 and explicit unknowns.
- `runtime.py`, `turns.py`, `providers.py`, `settings.py`, `config.example.yaml`: stable/dynamic
  instruction sections, missing-prewarm initialization off the event loop, optional metric window,
  native opt-in preemptive LLM. Humanization and preemptive LLM stay off by default; TTS speculation
  stays constrained to false. No production endpoint threshold changed or new dependency added.
- New `scripts/benchmark.py`, `tests/unit/test_benchmark.py`, `test_performance.py`,
  `test_preemptive.py`; extended `turn_harness.py`, `test_runtime.py`, `test_cartesia_wire.py`,
  `test_providers.py`. Actual SDK sessions exercise streaming, ten-turn bounded prompts, native
  speculative adoption/stale cancellation, output backpressure correlation, pool prewarm/reuse,
  injected failures and cleanup without remote calls.
- `scripts/inspect_sdk.py`, `docs/SDK_SIGNATURES.txt`: additional installed Instructions,
  MetricsReport, speech-handle callbacks and current hook/metric signatures.
- New `docs/PERFORMANCE.md`; updated README, DECISIONS, TUNING, HUMANIZATION and VERIFICATION_REPORT. These define
  every timing boundary, synthetic scope, unchanged defaults, rejected premature optimizations
  and future identical-audio comparison protocol.

Native LLM chunks still forward incrementally, including through optional bounded humanization;
there is no extra LLM classifier, TTS client, custom connection pool, per-chunk request, whole-reply
buffer or fine-fragment flush policy. Existing malformed-markup and cancellation regressions are
retained. Cartesia's real pool is tested against an in-memory WebSocket. Nova's persistent stream
lifecycle is inspected in installed source; successful remote connection reuse remains unverified.

The static prompt is not edited in this phase. Native Instructions.dynamic separates mutable
session metadata internally; the installed Groq/OpenAI serializer merges it after stable text in
the wire system message. Ten actual session request contexts and their serialized messages verify
the same prefix, bounded history and no duplicate instruction. Character counts are not called
token counts. Cache hits, actual tokens, savings, low-versus-default reasoning, real coherence,
voice quality and caller-heard latency remain unmeasured. Zero cached tokens from SDK can mean
unreported; actual retry attempts have no public event and remain null in reports.

### Commands and corrections

Run from `C:\Users\habiba\Desktop\voice-agent\voiceagent`. All uv checks use process-local
`$env:UV_CACHE_DIR="$PWD\.tools\recovery-cache"; $env:UV_OFFLINE='true'`.
The full suite also sets `$env:VOICEAGENT_TEST_WHEELHOUSE="$PWD\.tools\wheelhouse"`.
Tests run outside the restrictive Windows sandbox, whose temp-directory failure was established
earlier. External Python networking is blocked by the test fixture/benchmark; loopback is allowed
only for local asyncio plumbing. No global Python, cache, TLS or antivirus settings are altered.

| Command | Exit / result |
| --- | --- |
| `uv run ruff format .` | 0; format changes applied as implementation evolved |
| `uv run ruff check .` (first observer pass) | 1; three import ordering findings, corrected |
| `uv run pytest -q tests/unit/test_performance.py tests/unit/test_runtime.py tests/unit/test_providers.py -x` | 0; 20 passed in 19.16s |
| `uv run ruff check .` (first benchmark pass) | 1; unused import, two import order findings, loop variable binding; corrected without changing runtime behavior |
| `uv run python scripts/benchmark.py --turns 2 --concurrency 2 --output evals/results/phase5_synthetic.json` | 0; first 12-group benchmark completed in 12.823s; provisional report later replaced |
| `uv run ruff check --fix scripts/benchmark.py scripts/inspect_sdk.py tests/unit/turn_harness.py tests/unit/test_preemptive.py tests/unit/test_benchmark.py` | 0; two remaining import findings fixed |
| `uv run pytest -q tests/unit/test_preemptive.py tests/unit/test_benchmark.py tests/unit/test_performance.py -x` | 0; 13 passed in 24.09s |
| `uv run pytest -q tests/unit/test_runtime.py tests/unit/test_cartesia_wire.py tests/unit/test_preemptive.py tests/unit/test_benchmark.py tests/unit/test_performance.py -x` | 0; 26 passed in 24.06s |
| `uv run pytest -q tests/unit/test_performance.py tests/unit/test_turn_settings.py -x` | 1; 1 failed, 7 passed in 15.11s; new test incorrectly assumed every ChatItem had role, encountered AgentConfigUpdate |
| `uv run ruff check --fix tests/unit/test_performance.py` | 0; import ordering corrected; native test now filters message roles and also verifies actual provider serialization |
| `uv run pytest -q tests/unit/test_performance.py tests/unit/test_preemptive.py tests/unit/test_benchmark.py -x` | 0; 15 passed in 26.24s after serializer/backpressure checks |
| `uv sync --locked` | 0; 100 entries resolved, 99 packages audited |
| `uv pip check` | 0; 99 installed packages compatible |
| `uv lock --check` | 0; 100 entries resolved |
| `uv run python scripts/inspect_sdk.py` (captured to docs/SDK_SIGNATURES.txt) | 0; refreshed installed APIs verified; explicit inspect_exit=0 on final capture |
| `uv run ruff check .` (final code/docs checks) | 0; all checks passed |
| `uv run ruff format --check .` | 0; 48 Python/Markdown files formatted |
| `uv run python -m compileall -q src agent.py scripts tests` | 0; explicit compile_exit=0 |
| `Get-FileHash uv.lock -Algorithm SHA256` | 0; unchanged 74c58ff65d390dce098f8ac2f603034ae9fff5bc8c97f8d1fdcc88dc98d13d32 |
| `uv run python scripts/benchmark.py --turns 10 --concurrency 2 --output evals/results/phase5_synthetic.json` | 0; final instrumented run, 12 groups in 14.413s; details below |
| `uv run pytest -q --durations=5` | 0; **203 passed in 294.63s**, no failures or skips; clean-copy integration 207.46s, including a new isolated editable install and its independent copied unit-suite rerun |
| `git add README.md config.example.yaml docs/DECISIONS.md docs/PHASE_REPORT.md docs/SDK_SIGNATURES.txt docs/TUNING.md docs/PERFORMANCE.md scripts/inspect_sdk.py scripts/benchmark.py src/voiceagent/performance.py src/voiceagent/providers.py src/voiceagent/runtime.py src/voiceagent/settings.py src/voiceagent/turns.py tests/unit/test_benchmark.py tests/unit/test_performance.py tests/unit/test_preemptive.py tests/unit/test_cartesia_wire.py tests/unit/test_providers.py tests/unit/test_runtime.py tests/unit/turn_harness.py` | 0; stage only reviewable implementation/docs, preserving earlier staged Phase 3/4 changes; no commit/publish |
| `uv run python scripts/check_secrets.py` | 0; 58 indexed files against five configured credential values; no private env/deployment files indexed; only .env.example tracked |
| `git diff --check` | 0; SDK_SIGNATURES.txt CRLF→LF normalization warning only |

After evidence documentation was finalized, lint, formatting, compilation, indexed-secret scan
and both worktree/index whitespace checks were rerun (all exit 0). No code changed after the
203-test suite. The clean-copy unit timeout remains 180 seconds; no verification limit was relaxed.

### Measured local results — synthetic only

Final benchmark: Python 3.12.10, Agents 1.8.10, this Windows machine, two replicas at once.
Controlled STT/LLM/TTS stage delay: 0.005 s; test endpoints 0.02/0.1 s; no real speech, provider
transport or acoustic inference. Other offline verification was active: scheduling/background
load was not controlled. Twelve sessions produced 156 fake LLM requests, 132 completed responses,
12 interrupted responses and 12 failed responses (six 429, six timeout). All local model/TTS
generators and VAD streams closed, with zero surviving asyncio tasks. No remote socket leak or
long-duration process-memory claim can be made from this.

`eot_hook_to_sink_accept_s/completed`, converted to milliseconds below. Each row is a separate
profile/condition/replica distribution with **11 samples**; no averaging of group percentiles.

| Profile | Humanization | Replica | p50 ms | p95 ms |
| --- | --- | --- | --- | --- |
| VAD | off | 0 | 9.429 | 11.385 |
| VAD | off | 1 | 9.052 | 10.769 |
| VAD | on | 0 | 9.140 | 11.535 |
| VAD | on | 1 | 8.763 | 11.163 |
| mini routing, scripted verdict | off | 0 | 8.554 | 75.809 |
| mini routing, scripted verdict | off | 1 | 8.981 | 75.553 |
| mini routing, scripted verdict | on | 0 | 7.767 | 8.657 |
| mini routing, scripted verdict | on | 1 | 7.432 | 8.673 |
| Flux event routing | off | 0 | 8.050 | 10.101 |
| Flux event routing | off | 1 | 8.019 | 10.312 |
| Flux event routing | on | 0 | 11.895 | 18.748 |
| Flux event routing | on | 1 | 11.954 | 20.753 |

These start AFTER detected turn completion and end at an in-memory server sink. They exclude
actual speech endpoint detection, remote STT/LLM/TTS and WebRTC/device playback. Outliers are
retained; these numbers do not rank provider/profile performance or show humanization is faster.

Text-only on/off comparison: 200 measured iterations per condition after eight warmups,
96 chunks each, no I/O or provider requests. Actual monotonic measurements:

| Condition | First text p50 / p95 ms | Whole transform p50 / p95 ms |
| --- | --- | --- |
| Pass-through, humanization off | 0.0010 / 0.0012 | 0.0301 / 0.0304 |
| Bounded guard, humanization on | 0.0335 / 0.0668 | 0.7992 / 1.4200 |

This measures added processing cost rather than asserting zero overhead. The guard stays
incremental and cancellation-safe, with no additional model requests. No historical application
latency baseline exists, so no before/after network improvement or audible naturalness gain is
claimed. The local JSON report is ignored by Git/Docker. Numeric results above remain reviewable
without publishing evaluation artifacts.

### Remaining acceptance and completion

Final full-suite, clean-copy, Git/Docker policy and indexed-secret checks pass. Phase 5's requested
offline implementation/verification is PASS. Phases 0–1 retain PASS; Phases 2–4 remain offline
PASS / live BLOCKED. Phase 5 overall live acceptance remains BLOCKED:
five real voice turns first, identical-input profile/listening comparisons, five cold and at least
20 warm trials per configuration, and at least 30 comparable warm turns per speculation condition.
Need explicit provider-credit approval, confirmed authorized voice/language and microphone/input
permission; recording and deployment require separate authorization. Current request authorizes
neither. PERFORMANCE.md defines the real E2E p50/p95 and barge-in targets and their measurement.

Rejected now: custom pooling, extra provider warmup calls, hidden classifiers/summarization,
tiny TTS flushes, reduced production pause thresholds, assumed cache hits, automatic retries/
provider switches, preemptive TTS and unmeasured noise processing. No work beyond Phase 5 began.

## Phase 6 — Reliability, security and session management, 2026-11-02

Scope: the user expressly authorized Phase 6 offline implementation and verification despite
Phases 2–5 live gates remaining BLOCKED. No real STT/LLM/TTS, live room, paid access, microphone,
recording or deployment is authorized or executed. The five old Groq text requests remain the
only approved provider calls and their budget is exhausted. Earlier staged changes are preserved.

### Implementation

Files added: `src/voiceagent/lifecycle.py`; `tests/unit/test_provider_failures.py`,
`test_reliability.py`, `test_security.py`, `test_session_management.py`;
`docs/RELIABILITY_SECURITY.md`.
Files updated: runtime.py, providers.py, settings.py, telemetry.py, config.example.yaml,
test_providers.py, scripts/inspect_sdk.py, SDK_SIGNATURES.txt, README, COPY_INTEGRATION,
DECISIONS, PERFORMANCE, PHASE_REPORT and VERIFICATION_REPORT. No prompt, credential, dependency,
provider/model, endpoint-threshold or humanization/preemptive default is changed by this phase.

- One per-session lifecycle helper latches stop causes, handles terminal provider/room errors,
  bounds startup/drain/shutdown, escalates an expired graceful drain with public force interruption,
  and joins its own watchdog. Repeated job callbacks await the same completed cleanup. Native
  SDK streaming, interruption, speech/history handling, recovery and client prewarming remain.
- Startup uses one monotonic deadline across prompt/hook/model setup and session.start/connect;
  default 30 seconds. Graceful drain allowance is 5 seconds; session close and each provider close
  have separate 10-second budgets. A failing close cannot prevent remaining reverse-order client
  close attempts; fixed cleanup errors propagate after cleanup. Cancellation is preserved.
- Explicit RoomOptions closes on SDK-approved linked-participant disconnect reasons without room
  deletion. A terminal RTC room-disconnected callback stops the job's session and is detached on
  exit. Transient reconnect events do not stop/re-greet/reconstruct providers.
- Terminal STT/LLM/TTS, auth, rate-limit, server/network/timeout failures degrade by ending the
  unavailable session. No extra apology generation, new provider or replay after partial speech.
  Recoverable notifications do not cause an application response/retry.
- `limits.max_retries` now only accepts zero. The installed SDK's first retry is 0.1 s and no
  sufficient public jitter/Retry-After control is available here. Reject unsafe opt-ins rather
  than promising quota-aware recovery. Groq HTTP retries and SDK retries remain zero; no custom
  backoff loop is added. Nonzero configurations require migration to zero.
- Default input cap 8192 UTF-8 bytes, 100 LLM-node starts per agent/session and explicit native
  max_tool_steps=3 supplement token/time/history bounds. Caps stop before a new model invocation;
  starts include speculative/tool-continuation work and are not asserted billed request counts.
- Logging merges bounded configured-secret filters across overlapping session setup, suppresses
  raw SDK/provider messages, exception payloads/source stacks and sensitive fields, and bounds
  recursive metadata handling. Safe application diagnostics retain category/status/reason.
  Effective config redacts known values in noncredential fields, and unknown field names do not
  echo untrusted input. No arbitrary object repr, transcript/audio sink or extra classifier.
- Remote room URLs require wss; ws is loopback-only; embedded credentials/query/fragment are
  rejected without echoing input. Known configured credentials accidentally placed in prompt or
  hook metadata fail before provider construction. Trusted host hook/tool authorization remains
  a host responsibility, with no automatic plugin/shell/business tool registration.

Actual installed 1.8.10 APIs inspected before use: AgentSession.shutdown/interrupt/aclose,
APIConnectOptions and RoomOptions. Installed source also verifies native partial-stream behavior
and record=False resolving audio/transcript/trace/log recording flags to false. Official session,
events/error, fallback and PII pages were rechecked; DECISIONS and RELIABILITY_SECURITY link them.
The latter documents threat surfaces, limited host-issued tokens, flood controls, consent/voice
licensing, supervisor grace and cooperative-cancellation limits. It distinguishes local tests
from real network/socket/RSS/acoustic acceptance.

### Exact commands, failures and results

Working directory: `C:\Users\habiba\Desktop\voice-agent\voiceagent`. All uv commands use:

```powershell
$env:UV_CACHE_DIR="$PWD\.tools\recovery-cache"
$env:UV_OFFLINE='true'
$env:VOICEAGENT_TEST_WHEELHOUSE="$PWD\.tools\wheelhouse"
```

The wheelhouse variable is needed for the clean-copy test; individual unit commands also remain
offline. Tests use authorized Windows temp-directory access with the existing autouse external
DNS/socket block; only loopback is permitted for asyncio. No global Python/cache/TLS/antivirus
settings, secret files or locked versions are modified. Explicit LASTEXITCODE values are captured
for final dependency/SDK/static checks. SDK output is saved in docs/SDK_SIGNATURES.txt.

| Exact command | Exit | Result |
| --- | --- | --- |
| `uv run ruff format .` | 0 | Sources/tests formatted during implementation |
| `uv run ruff check .` (initial) | 1 | One overlong URL-validation message; split safely; final lint passes |
| `uv run pytest -q tests/unit/test_runtime.py tests/unit/test_providers.py tests/unit/test_telemetry.py tests/unit/test_settings.py -x` | 0 | 53 passed in 26.53s |
| `uv run pytest -q tests/unit/test_reliability.py -x` | 0 | 12 passed in 24.20s, including native three-session failures and forced drain |
| `uv run ruff check --fix tests/unit/test_provider_failures.py tests/unit/test_security.py` | 1 initially | Three imports fixed, four long test lines subsequently formatted; final lint passes |
| `uv run pytest -q tests/unit/test_provider_failures.py tests/unit/test_security.py -x` | 0 | 51 passed in 25.85s |
| `uv run ruff check --fix tests/unit/test_session_management.py` | 1 initially | Two imports fixed, two long lines subsequently formatted; final lint passes |
| `uv run pytest -q tests/unit/test_session_management.py tests/unit/test_providers.py tests/unit/test_security.py -x` | 1 | 1 failed in 14.99s: cleanup-generated close event overwrote participant-disconnect reason |
| `uv run pytest -q tests/unit/test_session_management.py tests/unit/test_providers.py tests/unit/test_security.py tests/unit/test_reliability.py -x` (first) | 1 | 1 failed, 2 passed in 15.10s: startup-timeout reason still overwritten by cleanup |
| Same command after stop-reason latch/cleanup fix | 0 | 48 passed in 29.96s |
| `uv run pytest -q tests/unit/test_session_management.py tests/unit/test_provider_failures.py tests/unit/test_runtime.py tests/unit/test_settings.py -x` | 0 | 94 passed in 21.74s after terminal-room callback addition |
| `uv sync --locked` | 0 | Resolved 100 entries; audited 99 packages |
| `uv pip check` | 0 | All 99 installed packages compatible |
| `uv lock --check` | 0 | Manifest/lock consistent, 100 entries |
| `uv run python scripts/inspect_sdk.py` (captured to docs/SDK_SIGNATURES.txt) | 0 | Actual Agents/plugins 1.8.10 signatures, including new lifecycle/options APIs |
| `uv run ruff check .` | 0 | All checks passed |
| `uv run ruff format --check .` | 0 | 54 files already formatted after reliability documentation |
| `uv run python -m compileall -q src agent.py scripts tests` | 0 | Source/shim/scripts/tests compile |
| `Get-FileHash uv.lock -Algorithm SHA256` | 0 | Unchanged 74c58ff65d390dce098f8ac2f603034ae9fff5bc8c97f8d1fdcc88dc98d13d32 |

Final Phase 6 gates:

| Exact command / check | Exit | Result |
| --- | --- | --- |
| `uv run pytest -q --durations=5` | 0 | **283 passed in 342.86s**, zero failures/skips; 80 additional cases beyond Phase 5 |
| Clean-copy installation test within full suite | 0 | 232.88s; new environment/editable locked install, foreign-CWD/import isolation, SDK discovery/help and independent copied unit rerun |
| Git/Docker exclusion-policy test within full suite | 0 | Private env/deployment/cache/recording exclusions retained; this does not prove Docker image layers |
| `uv run python scripts/check_secrets.py` | 0 | **64 indexed files** against **5 configured credential values**, no match/private env/deployment identities |
| `git ls-files '.env*' '.venv/*' '.tools/*' 'console-recordings/*'` | 0 | Only .env.example listed |
| `git diff --cached --check` | 0 | No whitespace errors; SDK output normalization warning only when staged |

The index scan staged the exact Phase 6 candidate source/documents with the following command;
earlier staged changes were preserved, without committing, publishing or exposing secrets:

```powershell
git add config.example.yaml src/voiceagent/lifecycle.py src/voiceagent/providers.py src/voiceagent/runtime.py src/voiceagent/settings.py src/voiceagent/telemetry.py tests/unit/test_providers.py tests/unit/test_provider_failures.py tests/unit/test_reliability.py tests/unit/test_security.py tests/unit/test_session_management.py scripts/inspect_sdk.py docs/SDK_SIGNATURES.txt docs/RELIABILITY_SECURITY.md docs/PHASE_REPORT.md docs/DECISIONS.md docs/COPY_INTEGRATION.md docs/PERFORMANCE.md README.md
```

The copied unit count is not added a second time to 283. The existing 180-second child unit-suite
timeout was retained. Compilation/lint/format/indexed-secret/whitespace checks are repeated after
final report edits; no code changed after the complete passing suite.

The test failures identified a real reason-code race: a closing session may emit another
close event. Both first close reason and an explicit timeout/cancellation cause must remain
latched while cleanup proceeds. The fix is in production lifecycle code; assertions were retained.
Fast tests use explicitly copied shorter time budgets rather than lowering production defaults
or relaxing full-suite/copy timeouts. No failed test run counts as passing verification.

### Offline evidence and limitations

Native stream matrix: STT, LLM, TTS × 401/403/429/503/timeout/network × before/after partial output
= 36 cases. Each uses real installed SDK stream loops with fake provider _run, one attempt, one
terminal error, no replay and no surviving tasks. Three simultaneous native sessions are tested
with separate facts for STT/LLM/TTS faults, both humanization conditions and pre-/post-output.
The event matrix verifies policy and cancellation, not real provider transport behavior.

Entrypoint tests cover start/connect failure/timeouts, idle/duration, participant/room close,
job callbacks, startup/active cancellation, request/input caps and stale stop causes. Cleanup
tests inject client-close timeout/error/cancellation and retain reverse close attempts. Security
tests exercise configured secret omission, unknown payload/SDK logs, cyclic metadata, concurrent
redaction, URL validation, retry rejection, accidental prompt/metadata keys and untrusted-injection
boundaries. A real model was not asked to refuse an injection in this phase.

No new latency p50/p95, listening, WER, currency or provider-token values were measured. Existing
Phase 5 synthetic metrics remain synthetic. Local tasks/streams are test evidence; they do not
certify arbitrary long-running process memory, remote socket cleanup, real reconnection, provider
quota/Retry-After or user-heard partial speech. Blocking/noncooperative hooks and native threads
need host supervision; a Python timeout cannot safely kill them.

Exit gates possible offline: **6.1 predictable degradation PASS**, **6.2 minimum deterministic
security checks PASS**, **6.3 local lifecycle/isolation PASS**. The complete locked regression,
dependency/SDK/static, clean-copy and configured-secret gates pass. **Phase 6 offline scope is
complete; overall real-world acceptance remains BLOCKED.** Actual injection refusal, invalid
account/expired-key translation, provider network recovery, real socket/RSS soak, quota/cost,
three live sessions and caller-heard partial-output behavior need fresh explicit provider/room
approval. Voice/language permissions must be confirmed; recording and deployment require separate
approval. Docker image inspection remains blocked by unavailable Docker and the later image phase.
Phases 2–5 live acceptance remain BLOCKED. No later phase or deployment has begun.

## Phase 7 — Testing, simulations and quality evaluation, 2026-11-02

Scope: authorized offline implementation only. Phases 2–6 live acceptance remain BLOCKED. No
provider call, paid judge, Cloud simulation, live room, microphone, recording or deployment is
authorized or performed. Previous five Groq text calls remain exhausted. Existing staged work is
preserved. No production runtime, prompt, secret file, provider/model, threshold, locked dependency
or experiment default is changed by this phase.

### Implementation and API evidence

New files: `scripts/evaluate_offline.py`; `tests/fixtures/audio_scenarios.json`;
`tests/unit/audio_fixtures.py`, `delivery_evaluation.py`, `test_sdk_runs.py`,
`test_audio_scenarios.py`, `test_delivery_evaluation.py`, `test_evaluation_runner.py`;
`evals/scenarios.md`, `livekit_scenarios.yaml`, `first_live_audio.md`; `docs/EVALUATION.md`.
Updated SDK inspection/signature capture, clean-copy test, README, DECISIONS, PHASE_REPORT,
VERIFICATION_REPORT, humanization protocol cross-reference and evaluation-artifact README.

- Native AgentSession.run/RunResult assertions verify three-turn context/correction ordering,
  one assistant response per turn, interrupted events and obsolete-tail suppression with
  humanization on/off. No LLM judge or hidden response is used; output_options=None disables
  structured-output re-prompting. Fake replies are predetermined, so model accuracy is unverified.
- Six stable, seeded 16 kHz mono/20 ms in-memory PCM recipes cover silence, hesitation timing,
  background noise, incidental noise, overlap and rapid cadence. Tones/noise are not speech.
  Fixture hashes/framing/bounds are checked; actual bundled Silero processes silence/noise and
  emits finite predictions. No acoustic classification or recognition score is inferred.
- Twelve identical text streams per A/B condition verify substantive text, decimals/identifiers/
  URLs and punctuation preservation, leading-filler cooldown and control selection. All supported
  speaking-style policies are checked. Existing fake-wire emotion/prewarm and split-markup tests
  remain. No synthetic listening, prosody, emotion or naturalness winner is selected.
- A fixed-category runner reuses existing turn, failure, metrics, concurrency and cleanup suites.
  Child credentials/settings/pytest overrides are stripped. Temporary JUnit is summarized into
  numeric category counts/status and removed with stdout; real-audio/listening fields stay null.
  Missing/error/failure/skipped reports cannot pass. SDK/Python, prompt/manifest/PCM hashes and
  synthetic A/B provenance are included. It is a selected evaluation, not a replacement full suite.
- Five generic hosted scenario templates have local shape/unique-ID checks only. The clean-copy
  test now copies that specific non-secret template, never local results. The scenario matrix
  maps every plan case to existing/new offline evidence and remaining live work.
- evals/first_live_audio.md gives explicit approval/budget/voice/input/retention prerequisites,
  offline validation, local worker/room readiness, five first voice turns, terminal cleanup,
  evidence rules, stop limits and subsequent warm/cold/A-B/soak gates. It does not start a worker.

Current official unit-testing, Agent Simulations, scenario-format and CLI debugger pages were
checked (links in EVALUATION.md/DECISIONS). The pinned SDK exposes assertions in voice.run_result;
there is no Python agents.testing package here. AgentSession.run, RunAssert.next_event,
no_more_events and ChatMessageAssert.event are captured in SDK_SIGNATURES.txt and actually tested.

LiveKit Cloud simulation users/judges and media are genuine services. CLI >=2.19.0 is required;
`Get-Command lk -ErrorAction SilentlyContinue` returned no executable. The current worker also
sets session_host=False, which disables remote driving. CLI/debugger/hosted integration therefore
remains BLOCKED on tooling, approval and a reviewed explicit SessionHost opt-in path. YAML is not
CLI-schema certification. Recording/observation defaults were not changed to bypass that boundary.

### Commands and observed results

Directory: `C:\Users\habiba\Desktop\voice-agent\voiceagent`. All uv commands use process-local
`$env:UV_CACHE_DIR="$PWD\.tools\recovery-cache"; $env:UV_OFFLINE='true'`.
Full pytest also uses `$env:VOICEAGENT_TEST_WHEELHOUSE="$PWD\.tools\wheelhouse"`.
Tests use authorized Windows temp-directory access, scripted/fake providers and external Python
DNS/socket denial (loopback allowed for asyncio). No global interpreter/cache/security setting is
changed. Output capture checks explicit LASTEXITCODE; SDK capture is UTF-8 in SDK_SIGNATURES.txt.

| Exact command | Exit | Result |
| --- | --- | --- |
| `uv run pytest -q tests/unit/test_sdk_runs.py tests/unit/test_audio_scenarios.py -x` | 0 | 12 passed in 22.82s |
| `uv run pytest -q tests/unit/test_audio_scenarios.py tests/unit/test_delivery_evaluation.py -x` | 0 | 16 passed in 12.41s, including actual local Silero inference |
| `uv run pytest -q tests/unit/test_evaluation_runner.py tests/unit/test_delivery_evaluation.py tests/unit/test_audio_scenarios.py -x` | 0 | 22 passed in 13.03s |
| `uv run pytest -q tests/unit/test_evaluation_runner.py -x` | 0 | 7 passed in 0.70s, including prepared YAML shape and report guards |
| `uv run ruff format .` | 0 | New source/tests formatted |
| `uv run ruff check .` during development | 1 before correction | Explicit strict=False was needed for unequal-length adjacent-pair zip; import ordering and one long XML test line corrected |
| `uv run ruff check --fix tests/unit/test_delivery_evaluation.py scripts/inspect_sdk.py` | 0 | Two import findings fixed |
| `uv run ruff check --fix tests/unit/test_evaluation_runner.py` | 0 | Import ordering fixed after splitting XML line |
| `uv run ruff check --fix scripts/evaluate_offline.py` | 0 | One import-order finding after PCM-checksum metadata addition fixed |
| `uv run python scripts/evaluate_offline.py --output evals/results/phase7_offline.json` | 0 | Both initial and final execution PASS_OFFLINE; final 196 selected JUnit case reports across six categories, no failure/error/skip |
| `uv run python scripts/benchmark.py --turns 10 --concurrency 3 --delay 0.005 --output evals/results/phase7_synthetic.json` | 0 | 18 synthetic groups, 234 fake generations, zero surviving asyncio tasks; measured local results below |
| `uv sync --locked` | 0 | 100 lock entries resolved, 99 installed packages audited |
| `uv pip check` | 0 | All 99 packages compatible |
| `uv lock --check` | 0 | Manifest/lock consistent |
| `uv run python scripts/inspect_sdk.py` (captured in SDK_SIGNATURES.txt) | 0 | Actual 1.8.10 testing APIs captured |
| `uv run ruff check .` | 0 | All checks passed |
| `uv run ruff format --check .` | 0 | 64 files formatted after documentation additions |
| `uv run python -m compileall -q src agent.py scripts tests` | 0 | Source/shim/scripts/tests compile |
| `Get-FileHash uv.lock -Algorithm SHA256` | 0 | Unchanged 74c58ff65d390dce098f8ac2f603034ae9fff5bc8c97f8d1fdcc88dc98d13d32 |

No failing pytest case was observed in the targeted runs above. Negative parser tests deliberately
inject failed/skipped XML and assert FAIL_OR_INCOMPLETE; these are passing guard tests, not hidden
failed evaluations. Intermediate lint findings were corrected before final verification.

### Selected evaluation and synthetic benchmark results

Final evaluator: conversation 28, audio_signals 9, delivery 67, performance 15, failures 61,
security 16 JUnit case reports: **196 PASS_OFFLINE**, zero failures/errors/skips. These overlap
the complete suite and are not added again to its test count. Six PCM hashes and prompt/manifest
hashes are recorded in the ignored report. No raw audio/transcript/exception artifact is retained.

Controlled twelve-generation A/B: baseline retains 12 supplied leading prefixes; enabled guard
retains three at indices 0,4,8. Substantive text and punctuation remain identical. Baseline
Cartesia emotion is neutral; enabled auto omits it. Provider requests are zero; real tokens,
listening scores and caller-heard latency remain null. These counts describe deliberately
repetitive input, not Groq's actual filler frequency or a naturalness improvement.

Benchmark: Python 3.12.10, Agents 1.8.10, Windows; three concurrent replicas per condition;
0.005 s scripted stage delays, test-only 0.02/0.1 s endpoints and scripted mini probability.
18 groups completed in **15.545s**, with 234 fake LLM generations: 198 completed responses,
18 interrupted and 18 failed. All active fake LLM/TTS generators and VAD streams close; zero
surviving tasks. It measures no real provider/socket, CPU speech-inference latency or capacity.

Server EOT-hook-to-in-memory-sink acceptance, completed responses only; each row has **11 samples**.
Values below are milliseconds and retain outliers. Percentiles are not averaged across groups.

| Profile | Humanization | Replica | p50 ms | p95 ms |
| --- | --- | --- | --- | --- |
| VAD | off | 0 | 16.444 | 32.264 |
| VAD | off | 1 | 16.751 | 31.817 |
| VAD | off | 2 | 15.995 | 32.169 |
| VAD | on | 0 | 15.717 | 114.647 |
| VAD | on | 1 | 16.084 | 115.028 |
| VAD | on | 2 | 15.521 | 114.456 |
| mini routing, scripted | off | 0 | 15.803 | 19.596 |
| mini routing, scripted | off | 1 | 15.333 | 19.007 |
| mini routing, scripted | off | 2 | 15.450 | 18.993 |
| mini routing, scripted | on | 0 | 15.256 | 17.636 |
| mini routing, scripted | on | 1 | 14.860 | 17.450 |
| mini routing, scripted | on | 2 | 15.036 | 18.055 |
| Flux event routing | off | 0 | 14.119 | 15.812 |
| Flux event routing | off | 1 | 13.939 | 15.742 |
| Flux event routing | off | 2 | 13.998 | 15.856 |
| Flux event routing | on | 0 | 11.285 | 13.157 |
| Flux event routing | on | 1 | 11.538 | 13.225 |
| Flux event routing | on | 2 | 11.671 | 13.374 |

Separate text-only CPU benchmark, 200 samples after eight warmups per condition, 96 chunks each:
pass-through first-output p50/p95 0.0011/0.0022 ms, total 0.0285/0.0410 ms; enabled guard
first-output 0.0393/0.0769 ms, total 0.8496/1.3930 ms. These are actual local monotonic values,
not zero-overhead claims. Background verification/scheduling load was not controlled. Replica
count differs from Phase 5 and no runtime optimization was made: there is no comparable network
before/after improvement, profile ranking or audible-quality claim. All real latency targets remain
unmeasured; PERFORMANCE.md defines the boundaries.

### Completion and remaining gates

Final Phase 7 gates:

| Exact command / check | Exit | Result |
| --- | --- | --- |
| `uv run pytest -q --durations=5` | 0 | **310 passed in 332.93s**, zero failures/skips; 27 additional cases beyond Phase 6 |
| Clean-copy editable installation within full suite | 0 | 214.97s; fresh isolated locked environment, foreign-CWD/import isolation, changed prompt/config, SDK discovery/help, copied prepared YAML and independent copied unit suite |
| Git/Docker exclusion-policy test within full suite | 0 | Private env/deployment/cache/recording/evaluation artifacts excluded; no Docker image execution claimed |
| `uv run python scripts/check_secrets.py` | 0 | **76 indexed files** against **5 configured credential values**, no match/private env/deployment identities; scope is known values/filenames only |
| `git ls-files '.env*' '.venv/*' '.tools/*' 'console-recordings/*'` | 0 | Only .env.example listed |
| `git diff --cached --check` | 0 | No whitespace errors; SDK capture normalizes CRLF on staging |

Index scan staging command (exit 0), preserving earlier staged work and making no commit/publish:

```powershell
git add scripts/evaluate_offline.py scripts/inspect_sdk.py tests/fixtures/audio_scenarios.json tests/unit/audio_fixtures.py tests/unit/delivery_evaluation.py tests/unit/test_sdk_runs.py tests/unit/test_audio_scenarios.py tests/unit/test_delivery_evaluation.py tests/unit/test_evaluation_runner.py tests/integration/test_copy_contract.py docs/SDK_SIGNATURES.txt docs/EVALUATION.md docs/DECISIONS.md docs/PHASE_REPORT.md evals/scenarios.md evals/livekit_scenarios.yaml evals/first_live_audio.md evals/humanization_ab.md evals/results/README.md README.md
```

Final documentation edits are followed by lint/format/compile, indexed-secret and worktree/index
whitespace reruns. No code changed after the passing complete suite; copied unit timeout remains
180 seconds. Neither the copied unit count nor the selected evaluator's 196 cases is added again
to the 310-test parent count.

Exit gates possible offline: **7.1 static/unit/regression PASS**; **7.2 supported local SDK
run/assertion checks PASS, CLI debugger BLOCKED**; **7.3 signal/control/scenario preparation PASS,
real acoustic/listening/hosted simulations BLOCKED**; **7.4 honest offline evidence report PASS**.
**Phase 7 offline implementation is complete and verified; overall live acceptance is BLOCKED.**
All real-audio/hosted/LLM-judge gates and Phases 2–6 live acceptance remain BLOCKED. Use
evals/first_live_audio.md for the first authorized test; it requires a fresh capped provider/room
budget, designated test project, confirmed voice/language, approved microphone/input and separate
recording/retention permission. No Phase 8 deployment work was begun during Phase 7.

## Phase 8 — Docker and LiveKit Cloud deployment preparation

Date: 2026-11-02, Asia/Karachi. Existing uncommitted/staged Phase 3–7 work is preserved. No commit,
push, provider request, recording, authentication or deployment was performed. No dependencies or
secrets were changed. Phases 2–7 live acceptance remains BLOCKED.

### Implementation and documentation

- Added Dockerfile with immutable Python 3.12.16 slim Bookworm / uv 0.10.6 manifest pins,
  unchanged locked runtime dependencies, separate build/runtime stages, non-root UID/GID 10001,
  CA/native libraries, exec-form production start, SIGTERM and native SDK health probe.
- Retained editable source at `/app` so external prompt/settings paths resolve from the copied
  folder. The final stage excludes uv, tests, docs, caches and development tools. Dockerignore is
  deny-default with explicit source/build inputs; no root-directory COPY or secret ARG/ENV.
- Added network-disabled build initialization for bundled Silero/local mini models. Windows CPU
  initialization is tested; Linux initialization still requires an actual build. No all-plugin
  model downloader, remote model service or additional provider is introduced.
- Added Compose preparation: read-only rootfs, init, bounded tmpfs/log rotation, dropped
  capabilities, no-new-privileges, raw runtime env-file values, no published ports and no
  automatic restart loop. Raw format requires Compose >=2.30 and a literal unquoted UTF-8 env
  file; the existing private dotenv file was not changed.
- Added inert `deploy/livekit.toml.example`; actual project binding stays ignored and excluded.
  SELF_HOST.md and DEPLOY_LIVEKIT.md cover local startup, configuration, build/layer checks,
  production start, health, supervision, target review, Cloud secrets, updates/logs and rollback.
  `lk agent create` is explicitly an immediate deployment, requiring separate approval.
- Matched native process initialization timeout to the existing startup budget. Increased native
  per-job shutdown allowance from SDK default 10s to existing drain + 5*close + 5s: 60s by default,
  covering the existing 55s cooperative cleanup bound. Native worker drain stays 3600s; Compose
  grants 62m. No custom signal/drain/admission engine, provider or humanization changes were added.
- Added 38 deterministic tests: Docker/pin/context/Compose/template contracts; environment and
  health failure validation; configured SDK budgets; actual local native HTTP/pool lifecycle,
  drain waiting and repeated cleanup with synthetic registration/job state; bundled-model init.
  Extended the fresh-copy test to carry only inert deployment metadata and run the added unit
  contracts independently. SDK signature capture now includes AgentServer.run/drain/aclose.

### Documentation and compatibility checked

Reviewed official [Cloud quickstart](https://docs.livekit.io/deploy/agents/quickstart/),
[builds](https://docs.livekit.io/deploy/agents/builds/),
[secrets](https://docs.livekit.io/deploy/agents/secrets/),
[updates/rollback](https://docs.livekit.io/deploy/agents/managing-deployments/),
[server options](https://docs.livekit.io/agents/server/options/),
[uv Docker guide](https://docs.astral.sh/uv/guides/integration/docker/), Docker's official Python
Dockerfile and Compose raw env-file reference. Installed Agents/plugins remain 1.8.10. Cloud
injects LIVEKIT connection credentials; provider-only secret files must not overwrite them.
Managed rollback requires a paid plan; reviewed prior-source rebuild/redeploy is documented for
other plans. CLI help/actual commands remain unverified because the executable is missing.

Public image manifest probes fetched only anonymous registry metadata, not images or provider
services. SHA-256 of the returned bytes matched Docker-Content-Digest and linux/amd64 entries
exist for both pins. Digests/URLs are in docs/CONTAINER_PINS.json. Python image patch 3.12.16
differs from host 3.12.10; no local interpreter upgrade was performed. Debian security packages
remain build-time repository resolutions; no whole-image reproducibility or CVE result is claimed.

### Initial verification and limitations

All commands use the `voiceagent/` repository, not its parent. Environment:

```powershell
$env:UV_CACHE_DIR = "$PWD\.tools\recovery-cache"
$env:UV_OFFLINE = 'true'
$env:VOICEAGENT_TEST_WHEELHOUSE = "$PWD\.tools\wheelhouse"
```

Windows pytest runs use the previously established sandbox exception for temporary directories;
the autouse socket/DNS guard forbids non-loopback test connections. The copy installs offline
from hash-verified locked wheels. No new external inference/provider request is authorized.

| Exact command / check | Exit | Observed evidence |
| --- | --- | --- |
| `.venv\Scripts\python.exe .tools/inspect_image_pins.py` (first, sandboxed) | 1 | DNS error 11001 contacting public registry; no metadata verification claimed from this attempt |
| Same public-manifest probe, approved outside sandbox | 0 | Both immutable digests matched manifest bytes and included amd64; no image pull/build |
| `Get-Command docker,lk -ErrorAction SilentlyContinue` availability lookup | 1 on initial standalone lookup | Neither executable found; later combined diagnostic exits 0 because subsequent Test-Path commands complete |
| `Test-Path 'C:\Program Files\Docker\Docker\resources\bin\docker.exe'` and `Test-Path 'C:\Program Files\LiveKit\lk.exe'` | 0 | Both return False |
| `uv run ruff check .` (initial new-test run) | 1 | One E501 at test_deployment.py:86; formatting split the long call and the later check passed |
| `uv run ruff format tests/unit/test_deployment.py tests/integration/test_worker_lifecycle.py src/voiceagent/healthcheck.py` | 0 | One file reformatted, two unchanged |
| `uv run python -m pytest -q tests/unit/test_deployment.py tests/integration/test_worker_lifecycle.py --durations=5` | 0 | **38 passed in 18.73s**, no failures/skips |
| `uv sync --locked` | 0 | Resolved 100 lock entries; audited 99 packages |
| `uv pip check` | 0 | All 99 installed packages compatible |
| `uv lock --check` | 0 | Lock unchanged; SHA-256 74c58ff65d390dce098f8ac2f603034ae9fff5bc8c97f8d1fdcc88dc98d13d32 |
| `uv run ruff check .` | 0 | All checks passed after formatting |
| `uv run ruff format --check .` | 0 | 70 files already formatted |
| `uv run python -m compileall -q src agent.py scripts tests` | 0 | Compilation succeeds |
| `uv run python scripts/inspect_sdk.py > docs/SDK_SIGNATURES.txt` | 0 | Installed 1.8.10 startup/drain/close signatures captured, including native 3600s drain and default 10s job close |

Real local HTTP health/pool startup/shutdown is exercised with zero idle job processes. Tests
inject synthetic registration and controlled job join state to cover 503-before-registration,
reconnect grace, failure, healthy drain and task cleanup. They never register, dispatch or run a
real job subprocess. This is neither a container/OS signal test nor provider-readiness evidence.

Docker build, sent-context/layer/rootfs inspection, Linux model loading, non-root read-only runtime,
actual SIGTERM/in-flight call drain and self-host room acceptance are **BLOCKED: Docker missing**.
Cloud create/deploy/status/logs/secrets/update/rollback and three-turn voice acceptance are
**BLOCKED: CLI unavailable and target/budget/deployment approval not given**. Five-turn local
onboarding, cold/warm timings, costs, resource sizing and listening scores remain unmeasured.
The existing evals/first_live_audio.md checklist applies; no new live gates are silently closed.

### Final verification and exit gates

| Exact command / check | Exit | Observed evidence |
| --- | --- | --- |
| `uv run pytest -q --durations=5` | 0 | **348 passed in 462.35s**, zero failures/skips; 38 new cases beyond Phase 7 |
| Clean-copy installation in that full suite | 0 | **316.11s** total; fresh nested locked editable environment, hash-verified offline wheels, copied unit suite, foreign CWD/host import and env isolation, changed prompt/config, SDK discovery/help, inert deployment artifacts; subprocess timeouts remain unchanged |
| Git/Docker exclusion-policy checks in that full suite | 0 | Existing policy plus 20 allowlist cases; real Docker context/layers remain uninspected |
| `uv run python scripts/check_secrets.py` | 0 | **86 indexed files** checked against **5 configured credential values**, no match/private env/deployment identity; known values/filenames only |
| `git ls-files '.env*' '.venv/*' '.tools/*' 'console-recordings/*'` | 0 | Only `.env.example` listed |
| `git diff --check` and `git diff --cached --check` | 0 | No whitespace errors; Git normalizes captured SDK CRLF to LF on staging |

Final documentation is staged and followed by lint, format, compilation, indexed-secret and
whitespace checks again. No code changed after the passing complete suite. The copied unit cases
and initial targeted 38 cases are not added again to the 348 parent-suite count. Tests do not
prove naturalness, real latency, provider access, Linux execution or production capacity.

Files changed for Phase 8: Dockerfile, .dockerignore, compose.yaml, deploy/livekit.toml.example,
scripts/prepare_models.py, src/voiceagent/healthcheck.py, src/voiceagent/runtime.py,
tests/unit/test_deployment.py, tests/integration/test_worker_lifecycle.py,
tests/integration/test_copy_contract.py, scripts/inspect_sdk.py, docs/SDK_SIGNATURES.txt,
docs/CONTAINER_PINS.json, docs/SELF_HOST.md, docs/DEPLOY_LIVEKIT.md, README.md,
docs/DECISIONS.md, docs/VERIFICATION_REPORT.md and this report. Earlier staged work is retained;
the index is used for the secret check, not a commit or deployment.

| Plan sub-phase | Offline outcome | Required remaining gate |
| --- | --- | --- |
| 8.1 local startup | Help/discovery, settings, bundled models and local SDK lifecycle PASS; runbook complete | Five-turn live onboarding BLOCKED pending usage approval/test project/voice |
| 8.2 container | Build/context/non-root/health/secret contracts PASS | Actual build, layers, Linux startup/model load and SIGTERM/drain BLOCKED: Docker missing |
| 8.3 managed Cloud | Inert template, current official workflow and operations instructions prepared | CLI/account/approved target, create/status/logs/dispatch/three voice turns/update/rollback BLOCKED |
| 8.4 self-host worker | Same image/start/config/secret/health/supervision runbook prepared | Container worker accepting a real room job BLOCKED: Docker and authorized LiveKit usage needed |

**Phase 8 offline preparation and deterministic verification pass. Overall Phase 8 exit gate:
BLOCKED.** No image or deployment success is claimed. Phases 2–7 live gates remain BLOCKED and
Phase 9 is not begun. Next: make Docker/CLI available, build and inspect the image without secrets,
then obtain explicit target/deployment and capped provider/LiveKit-test approval before any real
registration/dispatch/voice/update test. Voice/language authorization and separate recording consent
remain required for the corresponding live checks. No request to paste credentials in chat.
