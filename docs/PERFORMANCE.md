# Performance measurement contract

Phase 5 supplies offline instrumentation and a repeatable local benchmark. Live performance
acceptance remains BLOCKED. All production endpoint thresholds, humanization-off and
preemptive-generation-off defaults are preserved. No provider request, room, recording or
deployment is authorized by the benchmark command.

## Collection and definitions

`latency.metrics: true` attaches one observer per session; false removes the observer, output
wrapper and completion hook work. `latency.metric_window` defaults to 256 samples per fixed
metric/outcome series (16–10000). Active speech-handle state is bounded by the same limit;
eviction is counted and removes callbacks. No audio or transcript is retained by this collector.
The SDK still manages its own session history and buffering; these are not a claim that all
SDK internals have fixed-size queues.

Structured `performance_summary` logs contain linear-interpolated p50/p95, retained sample
counts, lifetime observation counts, numeric token totals and explicit missing metrics. Outcomes
are separated, never silently dropped from a completed-turn distribution. Percentiles describe
the retained window, not all historic turns. Empty/unobserved measurements are absent or null;
negative, non-finite, boolean and nonnumeric values are rejected. All duration values are seconds.

| Field | Boundary and limitation |
| --- | --- |
| `sdk_eou_s` | SDK `end_of_turn_delay`: SDK speech-end anchor to turn completion, not annotated human speech end |
| `sdk_stt_finalization_s` | SDK `transcription_delay`; no reconstruction from transcript text |
| `detected_end_to_final_event_s` | Local detected speaking→listening event to subsequent final transcript event; missing if final arrives first; not acoustic STT accuracy or end-of-speech timing |
| `sdk_llm_ttft_s` | SDK ChatMessage `llm_node_ttft`; pipeline-node boundary |
| `provider_llm_ttft_s` | Provider-plugin `LLMMetrics.ttft`, independently labelled; never pooled with node TTFT |
| `sdk_llm_first_sentence_s` | SDK `llm_node_ttfs`, when available; first sentence handed toward TTS |
| `sdk_tts_ttfb_s` | SDK `tts_node_ttfb`; node boundary, not audio-device playback |
| `provider_tts_ttfb_s` | Plugin TTS first chunk/byte timing, independently labelled |
| `eot_hook_to_sink_accept_s` | Public `Agent.on_user_turn_completed` entry to first downstream `AudioOutput.capture_frame` return; server sink acceptance estimate only |
| `eot_hook_to_handle_done_s` | That hook to public SpeechHandle completion callback; server response lifecycle, not verified playback completion |
| `speech_handle_lifecycle_s` | Public speech-created event to done, including speculation; scheduled interrupted handles and unscheduled cancelled handles are separate |
| `sdk_playback_latency_s`, `sdk_e2e_s` | SDK-reported server/sink estimates; not independent remote playback observations |
| `sdk_llm_duration_s`, `sdk_tts_duration_s` | Plugin request lifetimes, including cancellation where reported |
| `sdk_stt_acquire_s`, `sdk_tts_acquire_s` | Plugin connection acquisition durations; independent connection-observation/reuse counters |
| `sdk_prompt_tokens`, `sdk_completion_tokens` | Numeric SDK usage by request, plus session totals; no estimates from characters |
| `positive_cached_tokens` | Strictly positive SDK-reported cached input; not inferred from repeated prompts |

Local intervals use `time.perf_counter`. SDK durations are preserved unchanged: some SDK
speech/EOU anchors use wall time, so the report explicitly records that provenance. No wall-clock
timestamp is subtracted from a local monotonic timestamp. Sink identity is captured before
awaiting downstream backpressure, preventing a frame from being attributed to a newer turn.
The wrapper relays pause/resume, clear/flush and playback events; it adds no audio buffer or task.
Speculative unscheduled handles cannot consume a committed-turn hook anchor. Missing anchors
remain unmeasured rather than guessed.

Logs correlate a generated session ID with SHA-256-shortened speech, request and message IDs.
Per-turn numeric values and available provider-request IDs are allowlisted. Raw conversations,
audio, prompt text, provider error bodies and credentials are never serialized by the observer.
There is no remote metrics exporter. Normal configured credential/PII log filtering remains active.

Timeout and error counts come from public error events; a nonrecoverable error marks the
currently observed handle failed. Request cancellation comes from plugin flags; speculative
handle cancellation and interrupted committed speech have separate lifecycle counts. A
ChatMessage's interrupted flag supplies its own SDK-metric outcome, distinct from handle failure.
The deprecated `metrics_collected` event is retained only for request durations, cancellation,
usage and connection data not present in per-turn reports. Primary turn timings use current
`conversation_item_added` / `ChatMessage.metrics`. Upgrade compatibility needs reinspection.

The SDK does not expose a public retry-attempt event here. `retry_attempt_count` is null;
recoverable-error count does not assert that a retry actually ran. Both session retries and
Groq client retries are constrained to zero by Phase 6. No replay loop or provider fallback is added.
The SDK can default unreported cache usage to zero: `cache_reporting_unknown_or_zero` preserves
that ambiguity. No cache-hit ratio or cost saving is computed from those zeros. Actual usage,
cache behavior, requests lost before usage emission and currency spend remain unverified.

## Streaming, prompt and lifecycle decisions

The existing LLM node forwards chunks through the same direct Groq client. Optional humanization
keeps only bounded control/filler-prefix state, emits incrementally and closes on cancellation.
It adds no LLM classifier, timer, queue, provider client or reconnect. The main response retains
low reasoning and `include_reasoning=false`. Native TTS sentence/phrase streaming remains intact;
no tiny-text flush policy, forced pause or whole-response aggregation was introduced.

Stable prompt text plus the optional stable delivery policy precede variable data using installed
`Instructions(common, dynamic=...)`. Native truncation preserves both instruction sections while
bounding recent request items. Groq's OpenAI-compatible serializer merges dynamic instructions
into the same wire system message, after the stable text. This improves internal section clarity
and preserves a reusable token prefix; it does not create an explicit Groq cache boundary or
guarantee a cache hit. No prompt padding, summary request or semantic context deletion is added.
Ten native turns verify serialization, stable text, one instruction copy and bounded history;
real coherence, token growth and natural speech remain live gates.

Provider instances are constructed once per session and owned by an AsyncExitStack. Native
Cartesia pool prewarming/reuse is verified with its actual plugin and a fake WebSocket. Nova STT
keeps a streaming connection for the stream lifetime rather than pooling per-turn connections;
the SDK controls reopening on stream errors/options changes. This is source/fixture evidence,
not successful remote WebSocket establishment. AgentSession already calls model prewarm; custom
pooling, extra warmup provider requests and per-turn provider reconstruction were rejected.
Worker prewarm still initializes local Silero/mini models. The rare missing-prewarm fallback now
uses `asyncio.to_thread(load_models, settings)` to avoid synchronous initialization on the event
loop. A unit check verifies execution on another thread. No startup latency improvement is
claimed without a cold-start measurement. Native initialization itself is not forcibly cancellable.

Normal, failed and cancelled lifecycles retain SDK shutdown and provider cleanup. Tests cover
startup failure, session cancellation, faults, repeated sessions and background task closure.
They do not certify remote socket recovery, process RSS stability over days or worker capacity.

## Native speculative generation

`latency.preemptive_llm: true` now selects the installed native preemptive LLM implementation
explicitly; default remains false. It is experimental and requires approval before live usage.
`preemptive_tts` remains constrained to false. SDK defaults bound speculative starts to three
attempts per user turn and suppress them after ten seconds of speech; these are speculative
attempt limits, not transport retry settings. Intermediate transcripts can cancel a pending
preflight; final context equivalence decides adoption. No custom speculation controller exists.

Native tests cover adoption without a duplicate request, corrected-interim cancellation,
no early TTS/audio, obsolete-tail suppression, humanization on/off, correlated cancellation and
shutdown. These are correctness fixtures, not a 30-turn cost/latency A/B. Speculation can consume
extra Groq input/output tokens before cancellation. Positive cached input may reduce some cost
where available but cannot make wasted requests free. Evaluate off/on using the protocol below
before enabling it. Humanization remains disabled pending separate listening acceptance.

## Offline benchmark

From this directory, in the locked development environment:

```powershell
uv run python scripts/benchmark.py --turns 10 --concurrency 2 --delay 0.005 --output evals/results/phase5_synthetic.json
```

This developer tool needs the shipped `tests/unit/turn_harness.py`; it is not a runtime import.
It never loads `.env.local`, uses empty credentials and blocks external Python DNS/connect calls
(loopback is allowed for Windows asyncio). It runs real AgentSession with scripted STT/VAD, a
synthetic LLM and marker PCM. Nova, local-mini routing and Flux EOT paths are exercised, with
test-only endpoint delays 0.02/0.1 s and echo warmup disabled. Mini's probability is scripted;
actual binary loading has a separate silence smoke test. None of these choices tune production
thresholds or infer speech accuracy.

Each of 12 groups has ten alternating short/long turns, an interrupted request, its replacement,
and an injected nonrecoverable fault. Replica 0 injects 429, replica 1 a timeout. Stage delays are
controlled, but wall-clock scheduling is not deterministic. Reports separate each profile,
humanization flag, replica and outcome; do not average percentiles across groups. Resource checks
assert zero active LLM/TTS generators, closed VAD streams and zero surviving asyncio tasks.
Remote provider connections and real CPU speech inference are explicitly not exercised.

The report also measures 200 text-only transformations per condition after eight warmups,
96 input chunks each, recording first output and total processing p50/p95. This isolates actual
guard overhead from network/synthesis and does not measure listener perception. Requests remain
zero. Humanization-disabled is the comparator, not a benchmark of a historical application commit.
No claimed before/after network speedup can be derived. See PHASE_REPORT.md for measured results.

## Future real-audio protocol — BLOCKED pending approval

First close Phase 2's five voice-turn/room lifecycle gate and Phase 3/4's listening gates. Obtain
explicit approval for credits, a confirmed authorized Cartesia voice/language and microphone or
fixture playback. Recording requires separate consent. Use the same approved speech inputs and
response task across Nova/VAD, Nova/local-mini and Flux, preserving thresholds in TUNING.md.
Counterbalance profile order and report SDK/model/voice versions, worker/provider/LiveKit regions,
network, audio format, device/client and exact settings. Reuse established connections for warm
trials; separate five cold-connect trials and at least 20 warm turns per condition. Do not mix
cold/warm or interrupted/completed samples.

Include hesitations, trailing fillers, short requests, backchannels, breath/cough, background
talk, long utterances, rapid follow-ups and corrections, early/late interruption, reconnect and
shutdown during speech. Annotate actual user speech end independently of VAD. Measure client
playback start and audio-to-stop with a common/validated clock, or state synchronization error
and retain only justified component intervals. Without remote playback observations report
caller-heard E2E as unmeasured. Don't sum component medians to invent E2E. Measure false EOTs,
clipped speech, false stops, transcript errors and interrupted-history correctness as well as delay.

Plan targets: warm caller-heard E2E p50 ≤1.2 s, p95 ≤2.0 s; genuine barge-in audio-to-stop
p95 ≤500 ms. These are aspirational acceptance targets, not passed gates or hard unit-test bounds.
Report distributions, sample counts, incomplete/faulted trials and human listening scores. Do not
lower silence thresholds to hit latency targets while clipping speech. Keep Sonic prosody/voice
and response tasks constant; apply evals/humanization_ab.md for enabled/disabled comparisons.

For preemptive LLM on/off, collect at least 30 comparable warm turns per condition, including
stable preflights and corrected/resumed utterances. Record every request/adoption/cancellation,
SDK usage including cancelled attempts where emitted, unknown usage, wasted calls/tokens,
positive cached usage, latency, cutoffs and listener ratings. Compare low/default reasoning only
with a separate capped request budget and speech-quality review; low reasoning is preserved now.
Stop on approval limits or quality regressions; use provider quota/spend evidence separately.
Preemptive TTS stays disabled. Noise cancellation remains deferred until quiet/noisy A/B measures
recognition/false-trigger regressions and deployment support. No new dependency is introduced.

Official sources checked 2026-11-02: [LiveKit data hooks](https://docs.livekit.io/testing/observability/data/),
[native turns](https://docs.livekit.io/agents/logic/turns/),
[direct Cartesia](https://docs.livekit.io/agents/models/tts/cartesia/),
[Groq caching](https://console.groq.com/docs/prompt-caching),
[Deepgram Flux](https://developers.deepgram.com/docs/flux/configuration).
The pinned 1.8.10 source, SDK_SIGNATURES.txt and offline wire/session tests determine supported APIs.
