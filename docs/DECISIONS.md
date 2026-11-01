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
