# Research lock and decisions

Access date: 2026-11-01 (Asia/Karachi). This is an implementation record, not a benchmark.
The entire parent implementation plan was read before creating source files.

## Environment

Initial workspace contained only VOICEAGENT_IMPLEMENTATION_PLAN.md; it was not a Git repository.
The independent source repository lives inside voiceagent/. Python reports 3.12.10; uv reports
0.10.6. uv also located managed CPython 3.12.12 during its first resolution attempt.
`lk` and `docker` are not installed/on PATH. No provider/LiveKit credential variables were present
at discovery. The user will fill the empty, ignored .env.local later. This does not authorize
paid tests, recording, or deployments.

## Official sources checked

- [LiveKit quickstart](https://docs.livekit.io/agents/start/voice-ai/): AgentServer, AgentSession,
  Agent, root CLI pattern; no legacy VoicePipelineAgent.
- [Deepgram plugin](https://docs.livekit.io/agents/models/stt/deepgram/) and
  [Deepgram Nova-to-Flux migration](https://developers.deepgram.com/docs/flux/nova-3-migration):
  Nova uses STT v1, Flux uses v2 and integrated turn events. They require different EOT profiles.
- [Groq plugin](https://docs.livekit.io/agents/models/llm/groq/) and
  [Python reference](https://docs.livekit.io/reference/python/livekit/plugins/groq/index.html):
  direct groq.LLM, reasoning_effort and max_completion_tokens are documented. Do not pass
  include_reasoning directly to a constructor that does not expose it.
- [Groq caching](https://console.groq.com/docs/prompt-caching): GPT-OSS 20B is listed as supported;
  caching is automatic and cache hits cannot be guaranteed. A stable prefix is retained.
- [Groq reasoning](https://console.groq.com/docs/reasoning): GPT-OSS does not support reasoning_format;
  include_reasoning=false is the provider mechanism. Plugin routing must be proven before use.
- [Cartesia plugin](https://docs.livekit.io/agents/models/tts/cartesia/) and
  [Python reference](https://docs.livekit.io/reference/python/livekit/plugins/cartesia/index.html):
  direct cartesia.TTS with explicit key and user-selected voice; no inferred voice availability.
- [Cartesia controls](https://docs.cartesia.ai/build-with-cartesia/capability-guides/volume-speed-emotion)
  and [SSML](https://docs.cartesia.ai/build-with-cartesia/capability-guides/ssml-tags): controls are
  guidance, not deterministic pitch shifts; split tags can be spoken. No markup enabled initially.
- [LiveKit expressive mode](https://docs.livekit.io/agents/models/tts/expressive/): requires a supported
  inference.TTS, so expressive=True will not be used for the direct Cartesia pipeline.
- [Turn tuning](https://docs.livekit.io/agents/logic/turns/tuning/) and
  [adaptive interruption](https://docs.livekit.io/agents/logic/turns/adaptive-interruption-handling/):
  current docs show TurnHandlingOptions. Installed signature evidence must determine actual wiring.
- [Deployment quickstart](https://docs.livekit.io/deploy/agents/quickstart/) and
  [secrets](https://docs.livekit.io/deploy/agents/secrets/): no deployment authorized. Cloud injects
  LIVEKIT_*; do not overwrite those as cloud secrets.

## Compatibility matrix

| Component | Selected model / API | Key | Evidence / limitations |
| --- | --- | --- | --- |
| LiveKit | Agents 1.8.10, Python 3.12 | LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET | PyPI JSON queried; install/lock evidence recorded separately |
| Deepgram | nova-3, deepgram.STT | DEEPGRAM_API_KEY | Streaming documented; account availability BLOCKED |
| Deepgram alternative | flux-general-en, deepgram.STTv2 | DEEPGRAM_API_KEY | stt EOT required; execution disabled until Phase 3 |
| Groq | openai/gpt-oss-20b, groq.LLM | GROQ_API_KEY | Streaming and caching documented; account/credits/cache hit BLOCKED |
| Cartesia | sonic-3, cartesia.TTS | CARTESIA_API_KEY | Streaming documented; voice UUID/availability/listening BLOCKED |
| Turn detection | Silero VAD initially | none | Semantic/Flux comparison deferred until baseline audio gate |

No account dashboards were available. Free credits, quotas, permissions, model/voice access, and
supported account regions are NOT confirmed. No official model retirement claim is inferred.

## Configuration and packaging choices

- Copy the entire voiceagent/ directory, including editable src package and lockfile. This is
  source distribution only. Installing a wheel alone is outside the supported portability contract
  because prompt/config must remain editable beside agent.py.
- Explicit overrides > process environment > this folder's .env.local > selected YAML > typed
  defaults. Relative paths resolve from the copied project, never the host's working directory.
  Parent .env files and shell interpolation of secret values are intentionally excluded.
- English is the initial validated language. Other languages/models require explicit compatibility
  validation rather than accepting arbitrary unsupported values.
- No default voice UUID: the developer must select an authorized Cartesia voice. A UUID is only
  a format check; it does not establish availability or licensing.
- Baseline VAD, explicit named dispatch, no greeting, speculative generation off, no markup,
  no laughter, no transcript/audio persistence, no custom audio interruption framework.
- Hook failures disable optional extensions for that session; external tools are never loaded
  implicitly. Bounded recent history will be enforced at the LiveKit integration boundary.

## Lock and environment evidence

`uv.lock` generated successfully: 100 packages, registry https://pypi.org/simple. Agents and all
selected direct provider/Silero/turn-detector plugins pin to 1.8.10. Pydantic pins to 2.14.2;
pytest to 9.2.0, pytest-asyncio to 1.4.1, Ruff to 0.17.3. Build backend Hatchling pins to 1.33.0.
`uv lock --check --offline` succeeds with the explicit verified Python 3.12.10 interpreter.

The isolated install failed on a 300-second client cache-lock timeout for pluggy while preparing
the editable Hatchling build. Native TLS/lower concurrency and dependency-first retries did not
complete downloads. Offline sync confirms a required 1.8.10 wheel is still unavailable in cache.
The partial .venv must not be treated as working. Global Python has LiveKit 1.6.5; its inspected
signatures are discovery only and do not certify 1.8.10. Installed 1.8.10 API and clean-copy tests
remain **BLOCKED**. See PHASE_REPORT.md for exact commands/results and candidate tool diagnostics.

The official uv environment/caching docs were also checked during diagnosis:
[environment](https://docs.astral.sh/uv/reference/environment/),
[cache safety](https://docs.astral.sh/uv/concepts/cache/). No cache internals were manually removed.
No workspace-local uv upgrade completed; global uv 0.10.6 is unchanged.

## Verified recovery and baseline — 2026-11-01 through 2026-11-02

The installation blocker is resolved. Official artifacts were recovered into an independent,
ignored wheelhouse using resumable HTTPS ranges and full hash/size validation. No active uv cache
holder existed; the relevant lock files opened exclusively. Sustained CDN downloads were slow
even with curl and verified TLS. Defender's sole recent alert was unrelated to uv or this project.
No security settings, DNS, global Python/uv installation, or unrelated caches were changed.

Hash-checked locked requirements seeded a fresh isolated environment/cache. The first editable
build revealed Hatchling's dynamic editables~=0.3 requirement; verified editables 0.5 resolved it.
The editable build, plain final `uv sync --locked`, `uv pip check`, actual SDK inspection and
clean copied installation all pass. uv.lock is unchanged. PHASE_REPORT.md records exact commands,
test counts, environment flags and the prior failures; SDK_SIGNATURES.txt contains public APIs.

Installed API findings and implementation choices:

- AgentServer uses THREAD execution by default on this Windows host. The entrypoint/setup functions
  are top-level callables bound with partial; they do not hold conversational state globally.
- `cli.run_app` still exists but routes through a deprecated rich Python CLI. The current thin
  `python -m livekit.agents` interface discovers a global AgentServer. The root shim now exports
  server on import. `start`/`dev` use the modern module; console needs a LiveKit CLI TCP driver.
  The installed discoverer and current start help were exercised in the clean copy. `lk` itself
  is missing, so Go CLI/dev hot reload, console audio, and debugger operations remain untested.
- Discovery inserted the copied root ahead of CWD but left editable src behind the host CWD.
  The enhanced test caught a host voiceagent.py shadowing the copy. Prepending this copy's src
  fixes the collision; the original host file is unchanged.
- `AgentSession` defaults to inference.VAD if vad is omitted. The baseline always supplies local
  Silero and direct provider instances; it does not enable LiveKit Inference or expressive mode.
- AgentSession construction eagerly prewarms the LLM through a provider metadata request. Offline
  session tests therefore mock the session as well as providers. No real session was constructed
  or started with user credentials during offline checks.
- `SessionConnectOptions` and current TurnHandlingOptions are used directly. Nova+VAD is the
  Phase 2 baseline. Semantic/Flux, advanced humanization, and speculative generation are gated.
- `ModelSettings` only exposes tool_choice. Groq's constructor does not expose include_reasoning;
  its supported chat extra_kwargs/extra_body route is used by the public llm_node override.
  Five approved text requests accepted low reasoning/include_reasoning=false and passed checks.
- `ChatContext.truncate` mutates in place, preserves leading instructions and removes dangling
  tool-call prefixes. The LLM node uses it before streaming each request. No full-response buffering
  or extra emotion, end-of-turn, summarization, or routing LLM call is introduced.
- Shutdown uses native AgentSession shutdown/aclose, with graceful draining for session/idle
  limits. An AsyncExitStack closes provider clients even after partial construction or startup
  failure. Recording and session-host capture are explicitly off. Lifecycle/stream-cancellation
  tests are mocked; actual transport and acoustic cancellation remain unverified.

Phase 0 and Phase 1 pass. Phase 2 is implemented and tested offline but its exit gate is BLOCKED
on live voice/room acceptance. Exactly five Groq text requests were approved and completed; that
budget is exhausted. Deepgram/Cartesia requests, voice availability/listening, room registration,
latency/caching benchmarks and deployment have not been approved or executed.

## Phase 3 offline scope and installed APIs — 2026-11-02

The user explicitly authorized Phase 3 offline work despite the still-blocked Phase 2 voice
gate. This supersedes phase-order restrictions only for this offline implementation; it does
not authorize provider consumption or satisfy either live exit gate. The five Groq requests
remain the only authorized/completed provider calls. No new dependency version is needed.

Official turn detector, tuning, adaptive interruption and direct Deepgram pages linked above
were rechecked, along with [Flux EOT configuration](https://developers.deepgram.com/docs/flux/configuration).
The installed 1.8.10 source was inspected before adding each option. Findings:

- The text-based turn-detector plugin is deprecated. Use the current public
  `inference.TurnDetector(version="v1-mini")` for the existing `semantic` selector. It runs on
  local CPU with bundled native weights; it does not require EnglishModel, Hugging Face files,
  a second conversational LLM request or a new dependency. Pinning the version prevents dev or
  hosted auto-selection of Cloud inference. `livekit.local_inference.init_eot()` prewarms it
  when that profile is selected. The real binary was exercised on synthetic silence; this is
  loading/prediction evidence, not speech-classification accuracy.
- Preserve the Phase 2 Nova/VAD default and fixed 0.5/3-second endpoint bounds until audio
  comparisons justify another default. Dynamic endpointing (`mode`, `alpha`) is exposed for
  Nova. The native detector starts prediction after 200 ms silence and requires Silero segment
  closure at least 50 ms later; validate `min_silence_duration >= 0.25` with the local detector.
- Flux is explicitly required by plan 3.2, so add a separately selectable direct `STTv2`
  profile with `turn_detection="stt"`. STT owns EOT; VAD remains for barge-in. Set SDK fixed
  endpoint delays to zero in that profile to avoid adding Nova/default 0.5-second waits after
  Flux events. A native-session test confirms final transcript/VAD silence alone does not
  commit a Flux turn; the provider END_OF_SPEECH does. Actual provider streaming/A-B remain blocked.
- Current Deepgram documentation permits EOT timeout 500–60000 ms and threshold up to 1.0;
  the plugin docstring still describes a 3000 ms timeout default while Deepgram documents
  5000 ms. Leave unspecified values with the provider and recommend explicit values for A/B.
  Keep the application's existing threshold maximum of 0.9: 1.0 needs manual ForceEndTurn,
  which is outside this phase. Enforce eager threshold <= effective EOT threshold.
- Adaptive interruption is a separate Cloud service, not a local classifier. Keep `mode=vad`
  by default; `mode=adaptive` additionally requires `allow_cloud_inference=true` and LiveKit
  API key/secret even for console mode. Do not construct an extra adaptive client: AgentSession
  creates, gates and closes its own detector. AgentServer exports its configured LiveKit keys
  into the job environment in the installed SDK, so the SDK can authenticate without this
  module mutating `.env.local`. On unrecoverable detector errors the SDK falls back to VAD.
  Tests inject verdicts and errors through its actual stream/event path; no Cloud access tested.
- Native pause/resume retains pending generation for a false interruption. A committed real
  turn cancels that speech/generation and clears queued output. The SDK trims history using the
  sink's synchronized played transcript; no custom history repair or parallel cancellation
  engine is added. A sink lacking pause support cannot offer the same recovery guarantee.
- VAD/word thresholds cannot reliably classify brief acknowledgments; do not implement hardcoded
  phrase suppression. Adaptive backchannel verdicts gate STT before the LLM. Boundary controls,
  word/duration gates, recovery timeout (including disabled), resume and uninterruptible-audio
  discard settings map to public InterruptionOptions. They are centralized in turns.py.
- Preserve automatic SDK echo-cancellation warmup (normally initial 3 seconds of agent speech).
  Native tests disable it through the public constructor because their synthetic PCM cannot
  echo. This distinction matters for initial barge-in acceptance and is recorded in TUNING.md.
- Public metrics supply EOU plus interruption counters/component durations; false-recovery
  logging includes only the resumed boolean. No raw prompt, user transcript, waveform or
  utterance is persisted. No new audio-to-stop, human listening or latency claim is inferred.

Production code uses public APIs only. Tests intentionally inspect some locked SDK behavior
and inject CPU/adaptive predictions to exercise its state machine; they should be revisited
when upgrading. All automated Python tests now block external DNS/connections while permitting
loopback needed by Windows asyncio. The clean-copy test strips credentials and reruns the unit
suite in its own environment. No custom live harness is executed and no deployment performed.

## Phase 4 direct speech delivery — 2026-11-02

The user explicitly authorized Phase 4 offline implementation while Phase 2/3 live gates remain
blocked. This does not authorize provider consumption, listening, recording or deployment. Keep
humanization disabled in the example/default configuration until the real A/B gate passes.

Rechecked official sources:

- [Cartesia controls](https://docs.cartesia.ai/build-with-cartesia/capability-guides/volume-speed-emotion)
- [Cartesia markup](https://docs.cartesia.ai/build-with-cartesia/capability-guides/ssml-tags)
- [LiveKit direct Cartesia](https://docs.livekit.io/agents/models/tts/cartesia/)
- [LiveKit expressive mode](https://docs.livekit.io/agents/models/tts/expressive/)

Installed 1.8.10 source and actual in-memory WebSocket tests establish that constructor controls
become Sonic 3 `generation_config`; each synthesis stream snapshots options, uses its context ID
and returns its connection to the native pool. Later `update_options` affects future streams.
The application uses coherent constructor controls, not shared mid-stream mutations. Streaming
requests reuse the session's existing direct TTS client. No new dependency/version is needed.

Emotion auto deliberately omits the emotion field. The main Groq reply supplies contextual
language and Sonic interprets its subtext; static validated emotions remain selectable. There
is no second classifier/request, prefix emotion protocol, random emotion routing or claimed
deterministic pitch variation. Numeric pitch/intensity controls are absent from the installed
API and rejected in configuration. Speed remains <=1.5 despite a looser 2.0 SDK source warning.

Complete tags can reach the direct plugin's WebSocket, as the fake-wire test verifies. That
does not prove live interpretation. Active tags/timed breaks and laughter stay disabled.
LiveKit expressive session mode requires Inference TTS, so the session remains expressive=False;
no change of billing path is hidden. Sonic's documented nonverbals and Inference guidance are
path-dependent. Voice/model/listening/availability confirmation remains blocked.

The external generic prompt now permits contextual style under an optional stable delivery
policy, without mandatory fillers or invented self-corrections. Prefix filtering is restricted
to leading hmm/uh/um/umm, with one or none per text-bearing generation, cooldown and repetition
limits. Tool-only/empty generations do not bypass the budget. Meaningful well/actually/you-know,
quoted text and body identifiers are preserved; broader filler constraints are prompt guidance,
not an asserted semantic classifier. No filler is inserted where the LLM did not produce one.

A bounded per-generation guard strips known speech-control tags/stage tokens from visible text
before both TTS and history. It retains technical comparisons and unknown type expressions.
Removed controls separate adjacent words without adding duplicate punctuation. Malformed unclosed
known controls discard ambiguous attributes until newline/EOF; arbitrary malformed XML cannot
be losslessly repaired. It is a speech-control guard, not a general sanitizer. Active SSML is
unavailable. The transform preserves tool/usage metadata and input objects, closes on cancellation,
and creates no queues, tasks, sleeps, additional clients or full-response buffer.

Safe fallback is ordinary plaintext or a configurable neutral profile; invalid controls fail
before requests. No automatic retry/replay after provider failure is introduced. The revised
prompt has not been sent to Groq, so five prior authorized text examples do not certify it.
HUMANIZATION.md documents settings/limits and evals/humanization_ab.md specifies the unexecuted
listening/voice-audition protocol. CPU overhead, first-audio cost, naturalness and prosody remain
unmeasured. Offline tests cannot close Phase 2/3/4 live gates.

## Phase 5 offline performance — 2026-11-02

The user explicitly authorized Phase 5 offline work despite the preceding live gates remaining
blocked. No additional provider request, room, recording or deployment is authorized. The lock,
prompt, direct provider routing, production endpoint thresholds and disabled humanization/
preemptive defaults remain unchanged. No new dependency or classifier is added.

Installed SDK source plus refreshed SDK_SIGNATURES.txt establish public Instructions.dynamic,
Agent.on_user_turn_completed, SpeechHandle callbacks, AudioOutput chaining and ChatMessage.metrics.
Current [data-hook documentation](https://docs.livekit.io/testing/observability/data/) prefers
per-turn reports; deprecated request metrics remain a supplement for usage/cancellation/reuse.
The observer bounds its series/active handles and emits numeric summaries with opaque correlation
IDs. It keeps local monotonic intervals distinct from SDK intervals with wall-time anchors.
Server sink acceptance is explicitly not measured audible latency. Retry attempts remain null;
SDK cache zero cannot distinguish missing reporting. No inferred cache-hit rate is generated.

Stable/dynamic instruction sections clarify policy versus session data. The actual Groq/OpenAI
serializer merges them after preserving the stable text prefix; this is not an explicit cache
breakpoint. Ten native request snapshots and their provider serialization check bounded history
and no duplicate instruction. [Groq caching](https://console.groq.com/docs/prompt-caching) lists
GPT-OSS 20B but promises no particular hit for this application. Cache/token/spend improvements
and low-versus-default reasoning remain unmeasured; low reasoning/excluded reasoning is retained.

Native Cartesia prewarm and same-WebSocket reuse are verified with an in-memory peer; production
adds no custom pool or extra warmup request. Nova uses its existing long-lived STT stream. Missing
worker model prewarm now falls back to a worker thread, verified independently of remote access.
The SDK's [native turn handling](https://docs.livekit.io/agents/logic/turns/) handles experimental
LLM speculation; production TTS speculation stays forbidden. Adoption, stale interim cancellation,
humanization interaction and cleanup tests precede any future 30-turn live A/B.

`scripts/benchmark.py` compares real SDK control flow with scripted recognition/delays and marker
PCM. It uses empty credentials, no env loading and an external networking guard. Measurements
are explicitly synthetic and profile/outcome-specific; text-only overhead is measured separately.
PERFORMANCE.md records boundaries, rejected premature tuning/pooling/fragmentation, real-audio
protocol and acceptance targets. PHASE_REPORT.md records exact checks and failures. Real latency,
cache usage, cold/warm remote connection reuse, acoustic quality and capacity remain BLOCKED.

## Phase 6 failure, session and security policy — 2026-11-02

The user authorized offline Phase 6 implementation, not provider requests, recording or deployment.
Phases 2–5 live gates stay blocked. Rechecked official [sessions](https://docs.livekit.io/agents/logic/sessions/),
[events/errors](https://docs.livekit.io/reference/agents/events/),
[fallback strategies](https://docs.livekit.io/agents/logic/fallback-strategies/) and
[PII scope](https://docs.livekit.io/testing/observability/pii-redaction/).
Installed shutdown/interrupt, APIConnectOptions and RoomOptions signatures are captured anew.

Keep LiveKit's native streaming/cancellation and one direct chain. Terminal errors close rather
than replaying partial speech, adding providers or making an extra apology LLM/TTS request.
Automatic retry settings are constrained to zero: the SDK first-retry interval is 0.1 s and
no safe jitter/Retry-After configuration is exposed here. Do not promise rate-limit-aware replay.
Existing nonzero settings now fail validation explicitly. Recoverable SDK notifications do not
trigger custom response generation. Fault tests retain real native stream loops and public events.

One local lifecycle helper latches stop reasons, bounds startup/drain/close, escalates an expired
native drain with public force interruption, and joins its watchdog. This avoids cancellation of
the SDK's internal drain task, whose teardown is SDK-owned. Terminal room disconnect is separate
from transient reconnection; RoomOptions enables linked-participant close without deleting rooms.
Provider close attempts remain reverse ordered and individually bounded; errors propagate as
fixed cleanup codes after remaining clients are attempted. Cooperative-cancellation limitations
and supervisor termination grace are explicit in RELIABILITY_SECURITY.md.

Per-session request and latest-input byte limits precede LLM invocation, supplementing token,
duration/history and explicit tool-step bounds. No global conversational state or summarizer is
added. Registry state in log filters contains only bounded redaction values, merged atomically
so overlapping session setup cannot remove older protections. Unknown SDK message bodies/PII/
exception payloads are suppressed; numeric core failure summaries retain category and status.
Remote LiveKit URLs require TLS and forbid credentials/query/fragment. Config printing and
startup guard against known secrets in noncredential text; this is not a general PII scanner.

Three concurrent native sessions and deterministic timeout/partial-failure matrices test isolation,
cleanup and unchanged streaming/humanization/interruption. Prompt-injection checks verify fixed
policy/tool/config boundaries without claiming real model refusal. Host short-lived tokens,
authenticated admission, tool authorization, tenant limits, voice licensing and retention remain
documented responsibilities. No host application, Cloud redaction service or new dependency is
introduced. Real transport recovery, quotas, capacity, socket/RSS soak and acoustic acceptance
remain unverified; RELIABILITY_SECURITY.md gives the exact scope and remaining approvals.

## Phase 7 evaluation evidence — 2026-11-02

The user authorized offline testing/simulations, not live provider requests, Cloud simulations,
recording or deployment. Runtime code, prompt, locked dependencies and disabled experiment defaults
remain unchanged. Existing failure/streaming/turn tests are reused in a grouped runner rather
than adding another conversational engine.

Official [unit-test APIs](https://docs.livekit.io/testing/unit-tests/),
[Agent Simulations](https://docs.livekit.io/testing/simulations/),
[scenario format](https://docs.livekit.io/testing/simulations/write-a-scenario/) and
[CLI debugger](https://docs.livekit.io/testing/debugger/) were rechecked. Installed public
AgentSession.run, RunResult event assertions and no_more_events are used with scripted providers,
output_options=None and no LLM judge. This verifies native context/event behavior, not actual model
accuracy. There is no Python livekit.agents.testing package in the locked environment; the public
assertion types live in voice.run_result. Signatures are captured in SDK_SIGNATURES.txt.

Hosted simulations use real Cloud/media/model services. The CLI is unavailable here and the
worker intentionally sets session_host=False. Hosted/debugger integration is therefore blocked
on both approval and a reviewed opt-in path; it is not claimed working merely because YAML is
prepared. No remote observation or recording default is enabled. Five generic scenarios receive
local shape/ID checks only. The first authorized real-audio route uses a local worker/test room,
with budget, authorized voice, input consent and separate recording approval.

Generated PCM fixtures are seeded tones/noise/silence, not speech or voice samples. Local Silero
inference on them is genuine CPU processing, while session STT/VAD verdicts remain scripted.
No WER, naturalness, emotion or end-user latency value is inferred. Identical-text twelve-generation
humanization A/B validates only text preservation, sparse leading fillers, punctuation and control
selection; listening scores and real tokens remain null. Existing fake-wire Cartesia tests retain
control/pool coverage.

The offline runner strips child credentials/settings overrides and keeps only numeric categorized
JUnit evidence, provenance/hashes and controlled A/B summaries. Failures, skips, empty categories
and incomplete reports cannot become PASS_OFFLINE. Complete pytest remains the release gate;
the copy test now includes only the prepared non-secret scenario template, never evaluation
results. EVALUATION.md, evals/scenarios.md and evals/first_live_audio.md distinguish offline evidence,
hosted preparation and actionable live gates. No later deployment/release work was started in Phase 7.

## Phase 8 deployment preparation — 2026-11-02

Deployment artifacts are prepared without deploying, authenticating, installing system tools or
changing provider/humanization behavior. Docker and `lk` are unavailable. Public registry manifest
bytes were hash-verified for pinned Python 3.12.16 slim Bookworm and uv 0.10.6 images, with amd64
entries present. No image layers were pulled or built; Linux compatibility and vulnerability
status remain unverified. Runtime dependencies use the unchanged uv.lock, while Debian security
packages are resolved at build time. This is not a whole-image bit-reproducibility claim.

The multi-stage image retains editable source at /app because the reusable folder's settings and
external prompt resolve relative to src/voiceagent. A wheel-only install would break that contract.
Only locked runtime dependencies/source/prompt/example settings enter the final non-root image.
A deny-default Docker context, explicit COPY statements and no secret build arguments protect the
build boundary. Runtime secrets are injected externally. Compose adds read-only rootfs, bounded
tmpfs/logs, dropped capabilities and an init process; no automatic restart loop or exposed ports.
Raw env-file format requires Compose >=2.30 and literal unquoted UTF-8 values. These are prepared
contracts, not executed Docker runtime evidence.

Build-time local model initialization is network-disabled and uses bundled Silero/mini models;
the legacy all-plugin download-files workflow is avoided. Native SDK HTTP health, drain, signals,
admission and cleanup are reused. Per-job initialization now uses the existing startup setting;
per-job shutdown is derived as drain + 5*close + 5 seconds (60 by default), rather than the SDK's
10-second default that can undercut the existing 55-second cooperative cleanup budget. Worker drain
remains the native 3600 seconds; Compose allows 62 minutes. Tests use actual local SDK HTTP/pool
startup/closure with synthetic registration and job state. No real registration, job process,
Linux signal, call or container cleanup is inferred from those tests.

The Cloud example has placeholders only; actual project/agent TOML stays ignored and out of images.
`lk agent create` is explicitly documented as an immediate deployment, requiring approval.
Cloud injects LIVEKIT credentials; only provider secrets and reviewed voice/settings overrides
belong in the private secrets file. Runbooks cover target review, status/logs, rolling updates,
secret merges, paid-plan rollback and reviewed-source redeploy on other plans. All unexecuted
Cloud/self-host/live gates remain BLOCKED. No release/Phase 9 work is claimed complete.

## Cloud startup URL compatibility and temporary diagnosis — 2026-11-02

The reported startup error comes from our require_credentials(room=True) guard, before the native
worker starts. Environment loading preserves process env > project dotenv precedence and does not
change LIVEKIT_URL. The installed Agents 1.8.10 connection loop accepts HTTP/HTTPS base URLs and
maps them to WS/WSS when constructing the registration endpoint. Our scheme whitelist rejected
both aliases before that code ran. Synthetic tests reproduce that mismatch independently of
network access. The fix accepts https under the same remote TLS policy as wss, and http only for
the existing three permitted loopback hosts, delegating conversion to the SDK. No environment or
credential mutation, Cloud-marker bypass, new dependency/provider or Cloud action is introduced.
Explicit None checks also reject empty userinfo instead of treating an empty username as absent.

This confirms a code defect, not the existing Cloud deployment's injected URL or full CrashLoop
cause. The user verified only the project-list URL (wss, non-loopback); a normal URL with that shape
already passes our validator. The actual injected value and remote logs remain unavailable. At
the user's request a temporary pre-validation room-startup stderr line exposes only whitelisted
scheme and loopback/non-loopback/unknown labels, without DNS, hostname, URL components, credentials
or parser errors. It is emitted even when startup validation fails and omitted for help/console/
config/validate. Remove it after runtime confirmation. Actual recovery needs a separately approved
update of the same existing agent and review of these safe labels; do not create a new deployment
or change credentials to work around an unconfirmed diagnosis.

## Phase 8 qualitative live evidence and Phase 9 preparation — 2026-11-02

The owner confirms Cloud deployment/running state and at least one audible real-microphone
Deepgram → Groq → Cartesia conversation on revision 1fe4b9f. Local Git resolves that revision to
the current HEAD. This is owner-confirmed qualitative evidence, not an independently reviewed
Cloud export. Exact turns, stage/end-to-end timings, errors, cleanup, interruption performance,
cache/usage/cost and deployed runtime settings were not collected. Existing phase5/phase7 numeric
reports remain explicitly synthetic/offline. Startup is reported recovered; the injected URL
shape and original failure trigger are still unknown, so success does not prove that hypothesis.

Phase 9 preparation adds a source-candidate changelog, release/runbook and acceptance matrix,
updates stale no-live-test wording, and strengthens the existing copy test with a foreign host
LiveKit binding. No runtime/provider/prompt/dependency changes are made. A private candidate ZIP
is assembled from scanned staged source with external hashes, excluding private env/Cloud bindings,
caches, recordings, local metrics and Git state; it is not a tagged/published release or wheel-only
distribution. Version remains 0.1.0. Core imports remain independent of portfolio/customer projects.

No destructive cache/private-file cleanup, credential modification, new live test or deployment
is performed. Temporary diagnostic removal awaits safe runtime confirmation. Final release still
needs quantitative/scenario/operational/image evidence and license/ownership/voice-rights review.
No project source license is present; choosing one or publicly distributing is not implied.

## Post-roadmap customization and integration

The user's post-Phase-9 request explicitly authorizes general React/Next.js integration references;
the earlier roadmap's no-frontend boundary still applies to application/portfolio functionality
inside the core. Existing provider clients, root prompt/defaults and credentials remain unchanged.
Customization is opt-in through a private customization/.env.local or explicit path variables,
not an automatic switch merely because the new directory exists. Legacy runtime.greeting maps
to the custom greeting; ambiguous old/new greeting configurations fail validation.

New greetings and ending use native SDK speech handles. Ending runs inline to preserve tool
context and avoid circular waits. New observed user activity cancels hangup on all playout paths,
including exceptions/timeouts. A normal cancelled-tool string allowed an automatic old-context
LLM reply to invoke ending again in native tests. The runtime now uses the installed public
StopResponse exception for that outcome, suppressing the stale reply without another model call.
The LLM ending tool defaults off, and the direct application action remains explicit/trusted.

The independent gateway uses the already-locked LiveKit server SDK, aiohttp/PyJWT and persistent
SQLite. Production topology is one central gateway host with a shared durable local DB across
its workers; no process-local counter fallback, ephemeral/serverless DB or independent multi-host
replicas are supported. A multi-host shared-store adapter is deferred. Browser tokens have scoped
microphone/join grants and no embedded dispatch; room creation/dispatch stay server-owned.
Strict Cloud token revocation, ownership, bounded persisted cleanup and conservative upfront
usage reservations protect repeated-token/session paths. Authentication/challenge/trusted-network
mapping belongs to the host adapter, which intentionally fails closed until implemented.

Only the integration examples add npm dependencies, separately pinned/locked and private; worker
Python dependencies are unchanged. SDK types and mock client/server flows are verified separately
from actual Next.js builds, browser audio, Cloud revocation and public-site security acceptance.
Prior Phase 9 quantitative, operational, diagnostic, licensing and voice-rights blockers remain.
