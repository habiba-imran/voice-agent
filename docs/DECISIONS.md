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

Installed signatures, pinned transitive versions, and deviations are appended after successful
environment setup. No uninstalled signature is treated as verified runtime evidence.
