# VoiceAgent Core — Reusable Real-Time Voice Agent

**Implementation specification and Codex execution plan**  
**Research baseline:** 2026-11-01  
**Status:** Design specification; not an implemented or benchmarked system  
**Target:** A self-contained, copyable `voiceagent/` directory with a LiveKit-compatible Python worker, direct Deepgram STT, Groq LLM, and direct Cartesia TTS.

> **Execution instruction:** Implement this document in phase order. A phase is complete only after its evidence and exit gate are satisfied. Do not report tests as passed unless they were actually run. If credentials, a microphone, external access, or paid services are unavailable, mark affected checks **BLOCKED**, not **PASS**. Do not deploy to a real cloud project without explicit approval.

---

## 0. Mission, boundaries, and non-negotiables

### 0.1 Product goal

Create a **general-purpose reusable voice-agent engine**. A developer should be able to copy the complete `voiceagent/` folder into another repository, configure secrets, a prompt, a voice ID, and optional hooks, and run or deploy a working real-time agent **without rebuilding streaming, turn-taking, interruption handling, or worker lifecycle**.

The engine must prioritize:

1. **Low perceived latency:** minimize time from user finishing speech to first audible agent audio, while retaining correct turn completion.
2. **Genuinely expressive speech:** emotion, lively pitch/intonation, natural rhythm and emphasis, context-appropriate hesitations ("hmm," "um"), pauses, and occasional tested nonverbal behavior—not forced filler insertion.
3. **Conversation quality:** adaptive turn detection, true barge-in, backchannel tolerance, false-interruption recovery, concise voice-first answers, session context, and grounded behavior.
4. **Portability:** source-distributed folder, no required npm/PyPI publication, no proprietary SDK reuse, no project-specific business logic in the core.
5. **Deployment:** first-class LiveKit Cloud agent deployment; also runnable as a standalone Dockerized worker on a project's own hosting.
6. **Evidence:** automated tests, real audio validation, latency measurement, cost/usage observations, and phase-by-phase reports.

### 0.2 Included / excluded

**Included:** Python LiveKit worker; direct provider plugins; `prompt.md`; configuration and optional hook contract; VAD and EOT selection; interruptions; optional expressive delivery; streaming-safe synthesis; observability; tests; Docker; LiveKit deployment; documentation.

**Not in this project:** frontend application, microphone web widget, auth/token-issuing endpoint, RAG/vector database, booking/CRM tools, telephony trunk, persistent cross-session memory, complex agent workflows, multilingual support beyond provider-configurable basics, hosted analytics dashboard, or a separate distributable SDK. The host application owns those things if/when needed. Do not create them as hidden prerequisites.

**No project-specific references:** no named website, resume, brand, customer, or employer-specific prompt/data anywhere in the source examples. A generic sample prompt is required for smoke tests only.

**Legal/source cleanliness:** implement fresh code using official SDKs, documentation, and permissively licensed examples where permitted. Do not copy employer-owned code, configuration, voice samples, proprietary SDK, secrets, or recordings. Keep any external assets and code licenses accounted for.

### 0.3 Provider and deployment assumptions

- Default **STT** = Deepgram `nova-3`, direct `deepgram.STT`; experimental variant = Deepgram Flux via `deepgram.STTv2` plus **STT-based** turn detection. Do not accidentally pair Flux with Nova-style EOT configuration.
- Default **LLM** = Groq `openai/gpt-oss-20b` using the direct LiveKit Groq plugin, streaming, low reasoning effort **if the installed plugin exposes it**; any additional Groq request parameters must be verified against plugin API or passed via a tested, supported route. Never assume LLM reasoning tokens belong in TTS output.
- Default **TTS** = Cartesia Sonic (`sonic-3` as stable initial candidate; benchmark newer compatible Sonic variants), direct `cartesia.TTS` with the developer's Cartesia API key. The default must not secretly require LiveKit Inference billing for STT/TTS/LLM.
- Transport/worker = LiveKit Agents 1.x `AgentSession` and current `AgentServer`/CLI pattern. **Read current docs and installed API signatures** before writing code. Avoid tutorials using superseded SDK APIs.
- LLM, STT and TTS consumption are separate from LiveKit worker hosting. Free/provider credits and rate limits are **not guaranteed**; add clear error handling for quota and payment failures.
- One copied worker can be deployed separately for **each consuming project**, with its own LiveKit deployment ID, credentials/secrets, name/dispatch policy, usage budget, and release process. Never share one deployment config or secret set inadvertently across projects.

### 0.4 Working principles

- Prefer built-in LiveKit capabilities over custom audio middleware.
- No extra LLM call solely to classify emotion, decide whether to end a turn, or route simple replies.
- No network call in the normal response path beyond the providers and LiveKit unless explicitly enabled.
- Make optimizations **opt-in behind flags** and establish measured baselines before tuning.
- Never manufacture fixed latency results or claim voice is "human" based on unit tests alone.
- Keep the prompt as a stable prefix for caching; append changing conversation state afterward. Groq cache is automatic, free to enable on supported models, and **cache hits are not guaranteed**.
- Secrets must not appear in source, images, logs, audio artifacts, CI output, or test fixtures.

---

## 1. Proposed repository contract and file layout

The **entire root folder** is the copyable unit, including its own dependency lockfile, tests, Docker context, and README. The host repository can place it at `<host-root>/voiceagent/` and operate from that directory. It must **not** rely on the host's Python environment, root imports, root `.env`, or current working directory.

```text
voiceagent/
├── agent.py                      # CLI entrypoint shim for LiveKit local/cloud commands
├── src/voiceagent/
│   ├── __init__.py
│   ├── runtime.py                # LiveKit server, entrypoint, session lifecycle
│   ├── providers.py              # Direct Deepgram/Groq/Cartesia factories
│   ├── settings.py               # Typed settings and validation
│   ├── prompts.py                # Robust prompt.md loader
│   ├── turns.py                  # Turn configuration (built-in LiveKit machinery)
│   ├── expression.py             # Optional, bounded speech-delivery adapter
│   ├── hooks.py                  # Optional extension protocol; no specific tools
│   ├── telemetry.py              # Structured metrics and sanitized logging
│   └── lifecycle.py              # Cleanup, timeouts, shutdown helpers if needed
├── prompt.md                     # Generic identity, goals, rules, speech examples
├── config.example.yaml           # Non-secret, portable defaults/overrides
├── .env.example                  # Variable names ONLY; no real secret values
├── pyproject.toml
├── uv.lock                       # Generated and committed
├── Dockerfile
├── .dockerignore
├── .gitignore
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/                 # Non-private synthetic inputs
├── evals/
│   ├── scenarios.md              # Audio/text test matrix and scoring rubric
│   └── results/README.md        # Metadata only; raw recordings ignored
├── docs/
│   ├── COPY_INTEGRATION.md       # How to copy + configure in another project
│   ├── DEPLOY_LIVEKIT.md         # LiveKit Cloud specific flow
│   ├── SELF_HOST.md              # Docker worker contract
│   ├── TUNING.md                 # How to tune measured behavior
│   └── RELEASE_CHECKLIST.md
├── AGENTS.md                     # Codex run protocol and required evidence
└── README.md
```

**Portability safeguard:** package `src/voiceagent/` as an editable local project so the root `agent.py` shim can import it after `uv sync --locked`, even when the enclosing repository has different imports. In `.gitignore`, ignore `.env`, `.env.*`, and `livekit.toml` / other deployment-specific identifiers, but explicitly **unignore `.env.example`** (`!.env.example`). Keep `.env.example` in source control and exclude all real `.env*` files from the Docker build context. Validate this behavior with a clean copy test.

**Keep it lean:** files may be consolidated if two contain only trivial code; do not split modules merely to match this diagram. Preserve *responsibilities* and public contracts. A root `agent.py` shim must work with LiveKit CLI autodiscovery; check that rather than assuming nested Python package discovery. `prompt.md` must load relative to the installed/copied module/project path, never only `Path.cwd()`.

### 1.1 Settings contract (non-secret vs secret)

Document and type-check at least these settings (actual field names may change after SDK verification):

| Area | Configuration |
| --- | --- |
| STT | model, language, Nova keyterms, Flux mode/thresholds (conditional) |
| LLM | model, reasoning effort if supported, max output, temperature, conversation-history budget |
| TTS | model, voice ID, language, baseline emotion/speed/volume |
| Listening | Silero VAD, EOT approach, min/max endpoint delay |
| Interruption | enabled, adaptive/VAD mode, min duration/words, false-interruption recovery |
| Latency | preemptive LLM, preemptive TTS (default off), logging/benchmark flags |
| Humanization | enabled, disfluencies policy, pace presets, pause policy, emotional range, experimentation flags |
| Runtime | auto/explicit dispatch, optional greeting, max session duration, idle timeout, log level |
| Limits | maximum session duration, token/response budgets, request error backoff |

**Expected env vars:** `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` (local/self-hosting); `DEEPGRAM_API_KEY`, `GROQ_API_KEY`, `CARTESIA_API_KEY`; optionally config/prompt paths and deployment-specific settings. In LiveKit Cloud, LiveKit injects the `LIVEKIT_*` variables; **do not add/overwrite them as cloud secrets**. Each other credential remains external to the image.

### 1.2 Host integration contract (NO host app implementation)

The reusable agent documents its *interface*, not a particular host application:

- Worker startup: execute `agent.py` in `dev`, `console`, or `start` mode using the resolved command of the installed SDK.
- Session dispatch: auto-dispatch or **named explicit dispatch**, selected by configuration; document how a host would target the named agent.
- Client connectivity: the consuming project must supply its own authenticated participant/token flow and UI, if applicable. **Do not** implement UI or token endpoint here.
- Application hooks: project code may optionally register tools, conversation metadata, or a custom prompt **without editing provider session orchestration**. Hooks must default to no-op and be unit-testable.
- Separation: deployment settings (`livekit.toml`/agent IDs) and secrets are unique per consuming project. Copy the source template, not production credentials or deployment IDs.

---

## 2. Quality targets and measurement rules

Targets below are **engineering goals**, not claims or guarantees. Establish a baseline on an actual network/environment before declaring pass/fail. A run with cold-start latency must be reported separately from warmed in-call responsiveness.

| Metric | Initial goal / gate | Notes |
| --- | --- | --- |
| End of user speech → first audible agent audio (E2E) | **Target:** p50 ≤ 1.2 s, p95 ≤ 2.0 s under controlled warm conditions | Aspirational; investigate if missed, do not fake pass |
| LLM time to first text token (TTFT) | Report p50/p95; optimize versus own baseline | Includes reasoning/caching effects |
| TTS time to first audio byte (TTFB) | Report p50/p95; verify streaming | Keep connections prewarmed/reused |
| End-of-utterance (EOU) delay | Report p50/p95, premature-EOT rate | Faster is not better if it clips speakers |
| Genuine barge-in → agent yield | **Target:** p95 ≤ 500 ms, measured audio-to-stop | Evaluate both acoustic and transcript evidence |
| Short backchannels mistakenly stopping agent | **Target:** ≤ 1/10 in curated test set | Tiny sample gate, not a population estimate |
| Transcript/response accuracy | 100% critical cases pass; document noncritical misses | No fabricated facts, no reasoning/markup spoken |
| Crash-free lifecycle | 0 unhandled exceptions in scripted suite | Includes forced disconnect, 429, canceled speech |
| Emotion/pauses | Human listening rubric average ≥ 4/5 and no severe failures | Subjective evaluation, recordings and notes required |
| Prompt caching | Record cached/total tokens when surfaced | Never require a cache hit to pass basic functionality |

**Benchmark protocol:** Use at least 20 **warm** interactive turns spanning short, medium, and interrupted utterances (plus at least 5 cold-connect trials recorded separately) per configuration. For A/B comparisons run at least 30 comparable turns or state small-sample limitations. Capture hardware/region, network, timestamp, model IDs, SDK versions, prompt hash/length, noise profile, provider limits, and whether speculative generation was enabled. Do not mix different conditions in one latency percentile.

**Measure:** Use LiveKit per-turn `e2e_latency`, `llm_node_ttft`, `tts_node_ttfb`; per-plugin STT, LLM and TTS metrics; EOU timing; and end-user playback timestamps if the transport supports them. EOU + LLM TTFT + TTS TTFB is a **diagnostic approximation**, not the same as precise E2E and may double count/omit overlapped stages. Compare like-for-like. Log prompt cached token counts when available.

**Rubric for human listening tests (1–5 each):** prosody variation; emotion appropriateness; rhythm/pauses; sparing natural disfluencies; absence of synthetic/robotic artifacts; turn-taking and interruption experience; comprehension. Require short evidence notes and a clear A/B winner, not just "sounds good".

---

## 3. Phase 0 — Research lock, environment discovery, and baseline decisions

### 0.1 Inspect and verify current official APIs

**Tasks**
- Open the official LiveKit Python voice quickstart, direct Deepgram/Groq/Cartesia plugin docs, turn tuning, expressive-mode limitations, and deployment docs listed in §15.
- Confirm compatible releases and Python runtime before choosing a package/lockfile; use exact installed `AgentServer`, `AgentSession`, `TurnHandlingOptions`, provider factory and CLI signatures. Document any discrepancy with this plan.
- Confirm which Cartesia model is currently offered with developer's account and direct plugin, what controls work, how its WebSocket connection is reused, and whether direct inline SSML is forwarded correctly.
- Confirm the Groq GPT-OSS model is accessible to the intended account and if `reasoning_effort=low` / reasoning exclusion is accepted by the **plugin**.
- Validate environment tools: `python --version`, `uv --version`, `lk --version`, `docker --version` if available; detect missing tools without failing silently.

**Verification / evidence**
- `docs/DECISIONS.md` with links, access date, installed versions and exact API differences.
- A compatibility matrix with provider model, plugin, key names, streaming support, optional capabilities, free tier/credits confirmed from dashboard (if accessible).
- Test commands and version outputs attached to `docs/PHASE_REPORT.md` (redact secrets).

**Exit gate:** versions pinned or explicitly pending install; no unverified method/property treated as established API. External account availability may be **BLOCKED** and does not prevent offline scaffolding.

### 0.2 Repository setup

**Tasks**
- Initialize an independent repo with `voiceagent/` as copyable root, `pyproject.toml`, `uv.lock`, strict `.gitignore`/`.dockerignore`, `README.md`, lint/test tasks, and `AGENTS.md`.
- Use Python version supported by all chosen libraries; add Ruff and pytest/pytest-asyncio.
- Set a clear CLI command contract that works when folder is nested in a random host repo. Test editable `src/` package discovery and root shim imports after `uv sync --locked`.

**Verification**
- `uv sync --locked`, `uv run python -m compileall -q src agent.py`, `uv run ruff check .`, `uv run pytest -q` (even if initial suite is small).
- Confirm secrets, local `.env` files, deployment IDs and virtualenv absent from `git status` and `docker build` context; verify `.env.example` stays tracked.

**Exit gate:** clean environment setup, commands pass or documented blockers, folder portable when copied to a temporary directory.

---

## 4. Phase 1 — Core engine, configuration, prompt isolation

### 1.1 Config loader and validation

**Tasks**
- Typed settings with documented defaults and precedence: explicit constructor overrides > environment > example config defaults. No secrets in YAML or code.
- Validate exact missing key names, voice ID presence/format, supported models, nonnegative timeouts, rate and length ranges, and incompatible Nova/Flux EOT settings.
- Configuration print command must show **redacted** effective values; secrets never logged.

**Verification**
- Unit tests for missing API key, malformed config, incorrect voice ID, conflicting mode, environment override, and nested-folder launch.
- Negative config test exits non-zero with specific actionable error; no network calls for validation.

**Exit gate:** all settings/validation tests pass and `config.example.yaml` is sufficient to reproduce defaults.

### 1.2 Prompt loader and speech policy

**Tasks**
- Create generic `prompt.md` with `Identity`, `Goals`, `Speaking Style`, `Accuracy`, `Conversation`, `Boundaries`, `Optional Tools`, and `Failure Responses` sections.
- Keep prompt user-editable, UTF-8, loaded by path relative to module or explicit override, checked for empty/unreadable files and excessive size.
- Default answers brief (1–3 sentences), one follow-up at a time, plain speakable text; prohibit spelling out Markdown/JSON/SSML/LLM reasoning to the user.
- Stable static prompt prefix first, session-specific data at the end; allow a bounded history policy. No unbounded prompt growth.

**Verification**
- Tests: prompt found even when process CWD is elsewhere, missing file fails clearly, markdown loaded once per session, updates applied on **new** sessions as specified, no secrets/PII in sample prompt.
- Text-only golden tests for concise answers, uncertainty, conversation context, and not inventing unavailable facts.

**Exit gate:** prompts change independently of provider/orchestration code; no project-specific content.

### 1.3 Extension hooks (without building specific integrations)

**Tasks**
- Provide a documented optional registration boundary for functions/tools or session metadata. Default empty/no-op. Avoid a generalized plugin framework in v1.
- Hooks may do I/O **only when explicitly registered**; handle timeouts/cancellation without blocking normal voice processing.

**Verification**
- Dummy hook test and no-hook test; malformed hook fails validation and does not break startup.

**Exit gate:** core is usable without any custom functions.

---

## 5. Phase 2 — First working streaming conversation (baseline)

### 2.1 Direct provider chain

**Tasks**
- Instantiate direct Deepgram Nova-3 STT, direct Groq GPT-OSS 20B LLM, direct Cartesia Sonic TTS via current Python LiveKit plugin factories.
- Use `AgentSession` for streaming, speech routing, and history; avoid manually buffering complete LLM responses before passing to TTS.
- Configure a baseline TTS voice from a configurable ID; avoid unsupported default IDs in real deployment.
- For GPT-OSS, test low reasoning effort and prevent reasoning output entering synthesized speech (plugin-specific behavior must be verified).

**Verification**
- Construction/unit test using mocks for all provider instances; verify correct model IDs, API key lookup, streaming mode and options.
- Start in CLI `console` mode and have at least 5 real turns; save **sanitized** transcript and observed metrics, never API keys.
- Test short request, long request, silence, pronouncing names/numbers, and invalid credential to show safe failure.

**Exit gate:** reproducible voice conversation through all three providers, with no hidden second LLM/TTS pipeline.

### 2.2 Worker lifecycle and LiveKit connectivity

**Tasks**
- Use current `AgentServer` + job entrypoint pattern, connect/disconnect, optional greeting, job shutdown, provider close, STT/TTS resource cleanup.
- Confirm worker accepts LiveKit-dispatched jobs; treat production mode and local console mode separately.
- Set explicit session/idle/timeout limits without truncating active speech unexpectedly.

**Verification**
- Launch/shutdown smoke test, room join/leave, participant disconnect during speech, two sequential sessions; confirm no orphan tasks or open sockets.
- When credentials available, use LiveKit Agent Console or a room-based test; otherwise mark that test **BLOCKED**.

**Exit gate:** worker exits cleanly under normal and aborted sessions, logs include reason codes.

---

## 6. Phase 3 — Turn-taking, VAD, interruptions, and speech flow

### 3.1 Baseline Nova-3 + LiveKit turn detector

**Tasks**
- Enable Silero VAD and the currently supported LiveKit audio/semantic turn detector on a Nova-3 profile.
- Start from official turn-tuning defaults (`min_delay` ~0.5 s, `max_delay` ~3.0 s; interruption minimum ~0.5 s), validate configuration against actual SDK.
- Add config options for endpoint delay, dynamic endpointing if Python build supports it, and background noise suppression only if needed.

**Verification**
- Audio cases: 1-second hesitation, trailing "um", user mid-sentence breath, silence, short "yes", extended technical question, background talking.
- Report premature interruption-of-user percentage, EOU p50/p95 and observed delay.

**Exit gate:** no critical clipped speech in curated set; baseline EOU logged.

### 3.2 Alternative Deepgram Flux profile

**Tasks**
- Implement **switchable** Flux `STTv2` / `turn_detection="stt"` profile, rather than simultaneously layering incompatible turn detectors.
- If Flux has incompatible features or provider limits, document them explicitly and leave profile disabled.
- Benchmark same inputs and network/voice conditions as Nova-3 profile.

**Verification**
- A/B matrix (transcription accuracy, false EOT, silence tolerance, response latency, token/wasted-call cost).
- Choose default based on results and document rationale. Never assert "Flux is faster" without evidence.

**Exit gate:** both supported profiles validated, or one marked blocked with reproducible reason; default selected by evidence.

### 3.3 Adaptive interruption and recovery

**Tasks**
- Enable LiveKit adaptive handling where allowed and VAD fallback where unavailable; do not reinvent it with a second LLM classifier.
- Ensure interruptions cancel pending TTS/LLM tasks, clear obsolete audio, and preserve only spoken assistant text in history as supported by LiveKit.
- Handle non-interrupting backchannels ("mhm", "uh-huh", "right") and false interruption recovery; use built-in cooldown/recovery controls where available.

**Verification**
- Overlap scenario: real "Wait, stop" during long speech; time to yield (audio-to-stop), no old speech after new question.
- Backchannels during speech must usually be ignored; spontaneous cough/noise must recover appropriately.
- Interrupt during early/late chunk, reconnect, and when TTS stops after partial output.
- CLI debugger text mode is **not sufficient** for these claims; use audio simulations or live recording.

**Exit gate:** no stale answer resumes after a genuine interruption; interruptions and backchannels quantified.

### 3.4 Interaction ergonomics

**Tasks**
- Avoid repetitive openings; manage follow-up turns, missing inputs, acknowledgments, conversational continuity, and silence.
- Support configurable greeting behavior; never generate duplicate greetings on reconnect.
- No constant verbal encouragement or artificial listening noises by default.

**Verification**
- 10-turn text/debugger conversation with coherent references, one question at a time, and response brevity checks.

**Exit gate:** natural but controlled dialogue with no looping phrases.

---

## 7. Phase 4 — Expressive, genuinely human-like speech

**Principle:** The most natural result may come from a *more expressive voice and better phrasing*, not more manually injected fillers. Establish a plain-TTS baseline, then enable each feature independently and compare. Do **not** add extra LLM calls for emotion selection.

### 4.1 Voice audition / baseline

**Tasks**
- Choose 3–5 Cartesia voices that sound natural under neutral, excited, contemplative, reassuring, and question styles.
- Record identical scripts; evaluate voice quality and TTFB with each model/voice combination.
- Choose an expressive default plus a documented fallback; voice ID is always configurable.

**Verification:** score 5 rubric categories from §2 for each voice; log voice ID/model, audio artifacts outside Git, and latency.  
**Exit gate:** selected voice documented with listening scores and actual availability confirmed.

### 4.2 Natural language behavior (prompt-level)

**Tasks**
- Prefer contractions, short turns, varied openers, contextual acknowledgments, natural sentence rhythm; include examples of rare thoughtful hesitation and gentle self-correction.
- Disfluencies "hmm", "um", "uh", restarts: **contextual and sparse**, never inserted at a fixed per-sentence rate. They must not hide uncertainty, create false impressions of external action, or alter factual meaning.
- Reduce repeated "That's a great question", overly enthusiastic responses, unnatural jokes, and overly long introductions.

**Verification**
- Run a 12-turn scripted exchange, count repetitive openers/fillers, listen for awkward hesitation placement, assess accuracy and answer length.
- Demonstrate change relative to plain baseline; compare latency and token usage.

**Exit gate:** reviewer scores ≥4/5 average for speech naturalness; no material accuracy degradation.

### 4.3 Cartesia emotional delivery and pacing

**Tasks**
- Use direct Cartesia plugin's validated `emotion`, `speed`, and `volume` parameters for a **warm/neutral baseline**. Test small, context-appropriate variations; avoid huge pitch/speed changes.
- Test inline `<emotion>`, `<speed>`, `<volume>`, `<break>` markup **only when direct plugin actually forwards supported markup** and it reaches TTS intact.
- Cartesia emotion steering is beta; switches mid-generation may be unreliable. Prefer coherent delivery per phrase/utterance; limit segmentation.
- Do not claim the LiveKit `expressive=True` switch works with a direct Cartesia API-key plugin: current LiveKit expressive mode requires supported **`inference.TTS`**. A future alternative may be benchmarked as an explicit opt-in using LiveKit Inference, but not silently substituted.

**Verification**
- Test side-by-side neutral, enthusiastic, sympathetic, thoughtful, skeptical tone using same lines; compare voices, clarity and consistency.
- Assert output text is not polluted by `<emotion>`, `<break>` tags or hallucinated token fragments; verify whether tags are spoken aloud.
- Measure incremental TTS first-byte latency and audible glitches when switching modes.

**Exit gate:** enable only controls that demonstrate audible benefit without breaking streaming/transcripts.

### 4.4 Streaming-safe speech markup and pauses

**Tasks**
- First rely on commas, periods, em dashes and natural sentence structure. Introduce explicit short breaks only when human listening tests show a benefit.
- If optional markup is implemented, use an **incremental parser/state machine** that buffers incomplete tags, validates a very small allowlist, normalizes durations/values, and flushes safe plain text on malformed tags; never send token fragments that sound like "less-than emotion".
- Avoid long delayed chunks solely to collect tags or full sentences; never buffer the entire LLM completion.
- Keep display/log transcript *clean* of markup even if synthesis input contains it; ensure transcript/audio alignment remains plausible.

**Verification**
- Property/table-driven tests across chunk boundaries splitting at every character of `<break time="300ms"/>` and `<emotion value="calm"/>`.
- Cases for malformed, nested, unclosed, unsupported tags, interruption mid-tag, unicode, escaped markup, 1-character chunks.
- Benchmark first-audio latency with and without parser; if slower with no perceptual benefit, default it off.

**Exit gate:** no markup spoken, no stalled stream or dropped tail text, proper cancellation and cleanup.

### 4.5 Laughter and nonverbal sounds (experimental)

**Tasks**
- Cartesia direct Sonic docs describe `[laughter]`; LiveKit's expressive-mode Cartesia guidance excludes nonverbal laughs/sighs for its integration. Treat this as **path/model dependent**.
- Test `[laughter]` only in a sandbox setup. If it sounds bad, is spoken literally, or requires unreliable buffering, disable it. Never insert prerecorded laughter/SFX by default.
- Optional controlled disfluency and laughter flags; no compulsory "umm" or giggles on every reply.

**Verification:** A/B real listening with representative content; log whether laughter actually synthesizes as an audio event, not the literal word.  
**Exit gate:** disabled unless supported by the actual production path and scored positively.

---

## 8. Phase 5 — Latency optimizations, model economy, and cache behavior

### 5.1 Streaming and resource reuse

**Tasks**
- Ensure STT, LLM, TTS are streaming; keep Cartesia WebSocket reuse/prewarm enabled. Avoid per-turn client recreation where plugin already manages pooling.
- Confirm LiveKit `AgentSession` prewarm behavior for the selected Python SDK; shutdown releases provider resources.
- Maintain phrase/sentence chunking that is fast but not choppy; no fixed "wait 800 ms" pauses or custom silence gates.

**Verification:** cold vs warm first-turn metrics, subsequent-turn metrics, no duplicate WebSocket connection on every TTS request, no missed cleanup.  
**Exit gate:** prewarm/reuse evidence captured; no avoidable full-response buffering.

### 5.2 Reasoning, prompt budget, caching, and history

**Tasks**
- Test GPT-OSS 20B low reasoning against default/medium (where supported); do not route hidden/reasoning streams into TTS.
- Structure prompt static identity/policies first; mutable session context afterwards. Keep a **bounded** recent-message history and optional summary only if required; avoid an extra summarization LLM in the hot path.
- Collect Groq prompt-cache usage when available from the LiveKit plugin metrics or provider usage; do not assume cache hits or that all raw response metadata is exposed by plugins.
- Apply rate-limit-aware request budgets (max tokens, per-session time, retry/backoff for 429, safe user-facing failure), with no silent switch to paid models.

**Verification**
- 10-turn repeated-prefix test for prompt stability, token growth, naturalness; cached-token measurements if exposed, otherwise **not observable**.
- Real 429/timeout via fault-injected mock, and optional live quota test only if authorized; record response and cleanup.

**Exit gate:** responses remain concise and stable; bounded context; rate-limit failure does not crash worker.

### 5.3 Preemptive generation A/B

**Tasks**
- Establish baseline with LiveKit default preemptive LLM generation; compare on/off using identical scripted utterances.
- Keep preemptive TTS **off** initially; test it later only if cost and cancellation are acceptable.
- Collect wasted LLM/TTS requests from cancellation, erroneous early replies, and responsiveness, not just speed.

**Verification:** >=30 comparable warm turns per condition or explicitly state limitation; report p50/p95 E2E and wasted provider calls.  
**Exit gate:** retain only modes that improve perceived experience without unacceptable cost or cutoffs.

### 5.4 Optional noise processing

**Tasks**
- Benchmark noise cancellation/voice isolation (when supported by deployment) under controlled noises; do not enable blindly if it degrades near-field mic audio.

**Verification:** WER or keyterm accuracy, false speech triggers, latency impact under quiet/noisy conditions.  
**Exit gate:** choice documented, no performance regression in clean environments.

---

## 9. Phase 6 — Robustness, security, and operational boundaries

### 6.1 Provider and transport errors

**Tasks**
- Handle missing/expired API keys, STT/TTS disconnects, Groq 429/5xx, connection hiccups, aborted audio chunks, network timeouts and user leaving.
- Use bounded retries with jitter where safe. Once a partial TTS response is audible, do not replay the full sentence or switch providers mid-utterance without an explicitly proven safe strategy.
- Avoid unnecessary custom fallback orchestration. If provider fallback is desired in a later version, implement only after a full test matrix.

**Verification**
- Fault-injection tests per failure; assert clean shutdown, no infinite retries, no duplicated speech, error code + sanitized context in logs.
- Test 3 simultaneous sessions if provider quotas permit; assess session isolation and cleanup.

**Exit gate:** predictable degradation without unhandled task exceptions.

### 6.2 Security, consent, and data handling

**Tasks**
- Keep provider and LiveKit credentials server-side; never include them in a host client application.
- Use short-lived, limited permissions for future host-issued LiveKit room tokens (host responsibility, documented only).
- Session logs redact secrets, raw prompt payloads by default, and unnecessary personal data. Audio recording and raw transcript persistence **off by default**; enable explicitly with disclosure/retention controls.
- Restrict voice cloning or other licensed/consent-required audio assets to authorized use. Do not claim the agent is a real human.
- Document threat surface: prompt injection, unauthorized tools, replay/credential leakage, public deployment misuse, expensive session floods.

**Verification:** secret scanning, redaction tests, no credentials in git/build, recorded-data disabled by default, prompt-injection text test.  
**Exit gate:** minimum security checks pass.

### 6.3 Session lifecycle and resource accounting

**Tasks**
- Per-session max duration and idle timeout, graceful stop, log resource usage by session, no global mutable conversational state leaking across sessions.
- Add optional concurrency guidance without assuming plan-specific allowances stay fixed.

**Verification:** 2 separate sessions with different test facts, forced timeout, zero shared history, no hanging jobs or leaked background tasks.  
**Exit gate:** lifecycle reliable and quota-aware.

---

## 10. Phase 7 — Verification harness and regression suite

### 7.1 Automated static/unit tests

**Required suites**
1. Config, env precedence, and secret redaction.
2. Prompt path, normalization, static prefix/hash, and history bounds.
3. Provider factory model/options and unsupported settings.
4. EOT mode invariants (Nova vs Flux), interruption settings.
5. Streaming chunk boundary + speech-markup sanitizer behavior, including cancellation.
6. Optional hooks timeout/no-op behavior.
7. Worker session shutdown, disconnect, and timeout.
8. Fault injection: 429, network drop, STT/TTS failures.
9. Project portability nested under arbitrary directory.

**Commands (adjust to actual project manifest and record exact executed versions):**

```bash
uv sync --locked
uv run ruff check .
uv run python -m compileall -q src agent.py
uv run pytest -q
```

`uv run mypy ...` or Pyright is optional if configured; if configured, it becomes a release gate. CI must run unit tests with fake/mock providers and **no live secrets**.

### 7.2 LiveKit debugger and conversation tests

**Tasks**
- Install/verify LiveKit CLI `>= 2.19.0` before using the debugger.
- Exercise `lk agent debugger start`, `lk agent debugger say "..."`, `lk agent debugger events`, `lk agent debugger restart`, and `lk agent debugger stop` for **text-only logic checks**.
- For audio: `lk agent debugger start --audio`; verify STT, TTS and timing. The debugger's audio mode requires an available audio inference path and credits. It cannot assess real-time barge-in or how natural the synthesized voice sounds.
- Develop actual microphone/room-based Agent Console tests and audio simulations for interruption/overlap.

**Verification:** attach sanitized command outputs, debugger transcripts, scenario matrix. A passed text debugger test **does not** certify voice quality or barge-in.

### 7.3 Audio simulations and listening evaluations

**Required scenario matrix**

| Scenario | Expected behavior |
| --- | --- |
| Short greeting and simple request | Fast concise response |
| User pauses mid-thought | Agent waits appropriately |
| Trailing filler "um..." | Avoids premature response |
| User says "uh-huh" during agent speech | Usually continues |
| User says "Stop, I meant..." | Yields and answers updated request |
| False mic/noise interruption | Resumes or recovers smoothly |
| User interrupts during first TTS chunk | Stops old audio without ghost continuation |
| Long factual answer | Streams promptly, maintains logical phrasing |
| Conflicting facts / unknown request | Acknowledges uncertainty, does not invent |
| Repeated exchanges | No formulaic fillers or greetings |
| Emotional changes | Tone appropriate, not exaggerated |
| Pauses, SSML, laughter (if enabled) | No markup spoken, no bizarre artifacts |
| Rapid reconnect/leave | Clean reset and no leaked old content |
| Rate-limited LLM/TTS | Graceful failure without runaway retry |
| Silence / no user input | No infinite unsolicited monologue |

**Verification:** record cases, metadata, transcripts and anonymized audio where consent is obtained. Use LiveKit Agent Simulations for full conversations and audio timing; human listening remains mandatory for emotion quality.

### 7.4 Acceptance report

Produce `docs/VERIFICATION_REPORT.md` containing: date, environment, versions, commands with exit codes, test counts and failures, scenario-by-scenario evidence, p50/p95 and sample sizes, human listening scores, provider spend/quota observations, known limits, **PASS / FAIL / BLOCKED** per gate, and follow-up actions. Never invent a transcript, metric, recording, or external check.

**Exit gate:** automated suite green, critical audio scenarios passed, remaining blockers surfaced honestly; release approver can evaluate actual evidence.

---

## 11. Phase 8 — Local run, container image, and LiveKit Cloud deployment

### 8.1 Local startup and documentation

**Tasks**
- Document `uv sync --locked`, setting provider keys via `.env.local`, `uv run agent.py console`, `uv run agent.py dev`, `uv run agent.py start` **only if verified against the implemented entrypoint**.
- Confirm LiveKit CLI alternatives (`lk agent console`, `lk agent dev`, `lk agent start`) where supported; choose one documented canonical path.
- Ensure model files (Silero/turn detector) downloaded during setup/build if required—not unpredictably per cold job.

**Verification:** fresh clone -> environment setup -> 5-turn local live test; command outputs and onboarding time noted.  
**Exit gate:** a second developer can start locally using README alone.

### 8.2 Docker image

**Tasks**
- Slim glibc-based Python image (Debian/Ubuntu, not Alpine); reproducible lockfile, non-root user, CA certificates, proper shutdown signals, fixed `start` command.
- Include core code/prompt/config in build context; exclude `.env*`, recordings, tests/eval assets as appropriate; exclude secrets.
- Check cold boot/worker health and runtime model downloads; preserve ability to use externally managed secrets.

**Verification**

```bash
docker build -t voiceagent-core:local .
# run with a local temporary --env-file only when credentials are available
```

Inspect build layers/context to verify no `.env` or sensitive data; start container and check it registers against a test LiveKit project where permitted.  
**Exit gate:** Docker image builds, starts, can shut down gracefully and passes health behavior.

### 8.3 Managed LiveKit deployment

**Tasks**
- Never deploy without explicit user authorization and a designated target LiveKit Cloud project.
- From the copyable folder, authenticate (`lk cloud auth`), select target project, deploy (`lk agent create`), inspect (`lk agent status`, `lk agent logs`). Verify current CLI help before each command.
- Use LiveKit Cloud secrets management for `DEEPGRAM_API_KEY`, `GROQ_API_KEY`, `CARTESIA_API_KEY`; **do not set injected `LIVEKIT_URL/API_KEY/API_SECRET` as LiveKit Cloud secrets**.
- Keep `livekit.toml` / agent ID project-scoped and outside reusable template distribution, or use a gitignored per-project override; confirm copy doesn't point to previous deployment.
- Explicitly configure desired auto/explicit dispatch behavior and test one dispatched job end-to-end.
- Test rolling update (`lk agent deploy`), status/logs, rollback procedure, and how new and in-flight sessions behave. Staging only if plan permits.
- Record free-plan cold start versus warm in-call performance independently; paid warm worker options are host/project choices, not a core dependency.

**Verification**
- `lk agent status` shows expected deployment, logs show successful worker startup (without secrets), a real test participant connects and has 3 successful voice turns.
- New version visible after deploy; run a test while updating if safe, and document rollback evidence without modifying other agents.
- Verify no costs/charges triggered beyond authorized account quotas.

**Exit gate:** actual LiveKit Cloud worker deployment tested, or **BLOCKED—requires explicit authorization/account**; deployment instructions are complete regardless.

### 8.4 Self-hosted worker compatibility

**Tasks**
- Document running the same Docker image via `start` on an always-on container platform, with project-owned `LIVEKIT_*` and provider secrets at runtime.
- Document health/resource sizing, process supervision, reconnection, worker logs, and cold start/always-on tradeoff.
- **Do not** implement a specific external hosting provider integration, frontend, or proxy as part of v1.

**Verification:** local Docker worker with LiveKit credentials accepts room job.  
**Exit gate:** self-hosting instructions are accurate, credentials isolated, same source can run without LiveKit Cloud managed worker hosting.

---

## 12. Phase 9 — Portability, integration handoff, and versioned release

### 9.1 Copy-in smoke test

**Tasks**
- Copy `voiceagent/` under an unrelated temporary directory / minimal placeholder host repo (no app integration needed).
- Run setup/tests from within folder, change `prompt.md`, change `config.example.yaml`-derived runtime settings, test no-tool launch.
- Ensure the host cannot accidentally supply an incompatible global `livekit.toml`, stale credential path, import collision, or alternate working directory.

**Verification:** clean copy -> install -> tests -> prompt change -> restart -> new behavior; evidence captured.  
**Exit gate:** no manual edits to core `runtime.py` or provider streaming logic required for a simple new use case.

### 9.2 Versioning and docs

**Tasks**
- Add semantic version and changelog; document compatible Python/LiveKit/provider versions, runtime contract, which config knobs are supported, performance limitations, free-tier caveats, voice licensing, secrets, and per-project deployment independence.
- Write release/runbook with quick start, local debugging, cloud deployment, redeploy, troubleshooting, rollback, and cleanup.
- Include example host responsibilities (token issuing, UI, storage) **only as interface documentation**, no host implementation.

**Verification:** second-person README walkthrough, links validate, commands can be copied and run as written, no removed/retired models.  
**Exit gate:** ready as reusable source folder with reproducible build and honest limitations.

---

## 13. Phase 10 — Optional experiments (NOT release prerequisites)

Only start these after v1 works, tests pass, and baseline is recorded. Put each behind flags; A/B against the v1 baseline and remove experiments that regress naturalness or latency.

1. More advanced delivery planner (simple deterministic response-type cues, **not** another LLM roundtrip).
2. Token-safe SSML generation by the main LLM, using a tested streaming parser/clean transcript.
3. A/B on Cartesia Sonic newer model versions, including direct `[laughter]` support.
4. Better noise isolation and language switching.
5. Optional fallback provider profiles for quota failures, only if user authorizes costs.
6. Optional transcript export and privacy-aware metrics aggregation.
7. More sophisticated session history/summarization **outside the hot path**.
8. Adapt to conversational style over the current session (without persistent user profiling).

**Experiment exit rule:** one-page report with hypothesis, controls, samples, metrics, qualitative score, cost, and keep/remove decision.

---

## 14. Codex execution protocol, stop conditions, and reporting

### 14.1 Begin-of-phase routine

1. Read this file, `AGENTS.md`, relevant project files and current official docs for the APIs being implemented.
2. State exact files to change, tests to add, and what might require credentials/user input.
3. Implement the smallest working vertical slice; don't jump to complex humanization before the baseline stream works.
4. Run the **named verification commands** and relevant audio tests; capture real outputs.
5. Produce or append `docs/PHASE_REPORT.md` with work done, test evidence, pass/fail/blockers and planned next phase.
6. Fix regressions before declaring the phase passed; if required access is missing, continue with independent tasks but don't misstate completion.

### 14.2 Ask the user only when needed

Ask **specific, grouped questions** for inputs that genuinely block a concrete action: authorized API credentials (never request that secrets be pasted into a chat), preferred Cartesia voice/accent/language when a choice is needed, whether testing may consume credits, LiveKit Cloud project choice, permission to deploy, and permission to save/record audio. Offer sensible defaults and continue all nonblocked work. Avoid asking for information that's already in the repo.

### 14.3 Never do these things

- Do not publish a separate Python package, npm library, frontend, or generic business-use application.
- Do not copy private company IP or code.
- Do not implement a vector database or RAG in v1.
- Do not call new LLMs for emotion/backchannels unless an experiment is expressly authorized.
- Do not claim a real audio test has passed when only a text debugger test was run.
- Do not silently enable paid inference or deploy on a cloud account without permission.
- Do not send real API keys into logs, commits, CI, screenshots, or result artifacts.
- Do not use unsupported markup or assume `expressive=True` functions with direct Cartesia plugin.
- Do not force a magic latency threshold by trimming or ignoring user speech.

### 14.4 Required phase report template

```md
## Phase [ID] — [name]
Date/commit:
Files changed:
What was implemented:
Assumptions / docs checked:
Verification commands and exit codes:
Automated tests (pass/fail/skipped):
Live integration tests (pass/fail/blocked):
Audio listening tests (pass/fail/blocked):
Observed p50/p95 / sample size / environment:
Provider consumption (if measurable):
Security/secret checks:
Known defects or blockers:
Exit gate: PASS | FAIL | BLOCKED
Next work:
```

### 14.5 Global definition of done

- [ ] Copyable `voiceagent/` contains its own source, prompt, configuration, lockfile, Dockerfile, tests, and docs.
- [ ] Real Deepgram → Groq → Cartesia streaming session works over LiveKit.
- [ ] Nova vs Flux decision based on actual tests; EOT and backchannel behavior measured.
- [ ] Genuine interruptions yield; stale outputs don't continue; false interruptions recover.
- [ ] Expressive speech tested: emotion, prosody, sparing fillers, pauses; speculative capabilities labeled honestly.
- [ ] Accurate metrics, per-turn p50/p95, no invented performance claims.
- [ ] Groq caching and bounded history treated correctly; usage/rate-limit faults graceful.
- [ ] Secrets, transcript handling, cleanup and concurrent session isolation verified.
- [ ] Unit/CLI debugger/audio simulation/human listening matrix executed or explicitly marked blocked.
- [ ] Docker image starts, LiveKit Cloud deployment proven **only when authorized**, self-host compatibility documented.
- [ ] Entire folder copied to arbitrary host directory and works with only prompt/config/secrets changed.
- [ ] `docs/VERIFICATION_REPORT.md` and release checklist completed honestly.

---

## 15. Authoritative documentation and source links

Use these as starting points, and re-check during implementation because model IDs, quotas and SDK surfaces change. The links below were reviewed for this specification on 2026-11-01.

**Core and provider APIs**

- LiveKit Voice AI quickstart: https://docs.livekit.io/agents/start/voice-ai/
- LiveKit agent sessions: https://docs.livekit.io/agents/logic/sessions/
- LiveKit official prompt guidance: https://docs.livekit.io/agents/start/prompting/
- LiveKit Deepgram plugin (Nova-3 and Flux): https://docs.livekit.io/agents/models/stt/deepgram/
- LiveKit Groq plugin: https://docs.livekit.io/agents/models/llm/groq/
- LiveKit Cartesia plugin: https://docs.livekit.io/agents/models/tts/cartesia/
- LiveKit expressive mode (**Inference TTS only**): https://docs.livekit.io/agents/models/tts/expressive/
- Cartesia emotion, volume and speed: https://docs.cartesia.ai/build-with-cartesia/capability-guides/volume-speed-emotion
- Cartesia SSML: https://docs.cartesia.ai/build-with-cartesia/capability-guides/ssml-tags
- Groq prompt caching: https://console.groq.com/docs/prompt-caching
- Groq reasoning: https://console.groq.com/docs/reasoning
- Groq model/rate limits: https://console.groq.com/docs/rate-limits

**Interaction and latency**

- LiveKit turn-taking tuning: https://docs.livekit.io/agents/logic/turns/tuning/
- LiveKit adaptive interruption: https://docs.livekit.io/agents/logic/turns/adaptive-interruption-handling/
- LiveKit turn overview: https://docs.livekit.io/agents/logic/turns/
- LiveKit observability and data hooks: https://docs.livekit.io/testing/observability/data/

**Verification**

- LiveKit unit tests: https://docs.livekit.io/testing/unit-tests/
- LiveKit Agent Simulations: https://docs.livekit.io/testing/simulations/
- LiveKit CLI Agent Debugger: https://docs.livekit.io/testing/debugger/
- LiveKit testing overview: https://docs.livekit.io/testing/

**Deployment**

- LiveKit Cloud deployment quickstart: https://docs.livekit.io/deploy/agents/quickstart/
- Builds and Dockerfiles: https://docs.livekit.io/deploy/agents/builds/
- Managed deployment versioning/cold start: https://docs.livekit.io/deploy/agents/managing-deployments/
- LiveKit secret management: https://docs.livekit.io/deploy/agents/secrets/
- LiveKit CLI and agent commands: https://docs.livekit.io/intro/basics/cli/

---

## 16. Final implementation policy

Ship a **reliable, fast, expressive, testable voice agent**, not an over-engineered framework. The default architecture is a direct-provider streaming LiveKit Python worker with a separate general-purpose prompt. Advanced humanization is added **only after** basic speech, turn detection, interruptions and latency are working and measured. One copied directory serves one deployment context; each consuming project provisions its **own** LiveKit worker deployment and private provider credentials. The outcome is a clean foundation that can be reused without any frontend or business-specific functionality inside it.
