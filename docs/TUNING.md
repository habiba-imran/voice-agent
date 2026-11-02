# Turn-taking configuration

Phase 3 supplies offline-verified controls, not measured acoustic performance. Keep the Phase 2
default until authorized listening tests justify a change. Settings are loaded once per worker;
restart after editing the selected YAML or process environment. Do not edit provider/session code.
Nested environment overrides use names such as `VOICEAGENT_LISTENING__MIN_ENDPOINT_DELAY=0.8`.
Optional Phase 4 delivery controls are described in [HUMANIZATION.md](HUMANIZATION.md). They do
not replace these turn/interruption mechanisms and remain disabled by default.

## One end-of-turn strategy per profile

| Profile | Configuration | End-of-turn owner | Status |
| --- | --- | --- | --- |
| Baseline Nova | `stt.model: nova-3`, `listening.turn_detection: vad` | Local Silero activity plus LiveKit endpoint delay | Default preserved; real audio gate blocked |
| Nova + local audio turn detector | `stt.model: nova-3`, `listening.turn_detection: semantic` | LiveKit `inference.TurnDetector(version="v1-mini")` plus local Silero | Selectable; bundled native model tested on silence, speech accuracy unverified |
| Flux alternative | `stt.model: flux-general-en`, `listening.turn_detection: stt` | Direct Deepgram `STTv2` EOT events | Selectable; event/factory tests pass, real provider gate blocked |

`semantic` is the existing configuration name; it selects the current audio turn detector. The
deprecated transcript-based English/Multilingual model is not imported or used. The mini model
runs locally on CPU and its initialization is front-loaded by worker prewarm. Its native weights
are included in the locked dependency; no Hugging Face download is needed for this path. The
full Cloud turn detector is not auto-selected, even in dev mode. No extra conversational LLM
request, summarizer, custom silence engine, or transcript classifier is introduced.

For a local detector profile, use these overrides in a non-secret YAML selected with
`VOICEAGENT_CONFIG_PATH`:

```yaml
listening:
  turn_detection: semantic
  endpointing_mode: fixed
  min_endpoint_delay: 0.5
  max_endpoint_delay: 3.0
```

For the separately selectable Flux profile:

```yaml
stt:
  model: flux-general-en
  eot_threshold: 0.7
  eot_timeout_ms: 3000
  eager_eot_threshold: null
listening:
  turn_detection: stt
```

Flux owns the turn boundary, while local Silero still detects interruptions. The adapter sets
LiveKit's fixed endpoint delays to zero for this profile: otherwise 1.8.10 can add its default
0.5-second wait after the provider's EOT. Nova endpoint settings are not applied to Flux and
dynamic endpointing is rejected with Flux. Nova rejects Flux-only thresholds/timeouts. These
choices avoid a second turn detector or an additional silence threshold on top of Flux. They
are not a measured speed comparison; Nova remains default because there is no authorized A/B.

## Listening settings and trade-offs

| Setting under `listening` | Default | Effect |
| --- | --- | --- |
| `turn_detection` | `vad` | `vad`, local audio `semantic`, or Flux `stt` as above |
| `endpointing_mode` | `fixed` | Nova only; `dynamic` lets the SDK learn pauses within the configured bounds |
| `min_endpoint_delay` | 0.5 s | Nova delay after the SDK's speech-end anchor; increasing it tolerates short pauses but delays replies |
| `max_endpoint_delay` | 3.0 s | Patience when the local detector predicts an incomplete turn; plain VAD does not use this as semantic protection |
| `endpointing_alpha` | 0.9 | SDK smoothing for dynamic Nova endpointing; higher retains more history; range (0, 1) |
| `vad.min_speech_duration` | 0.05 s | Minimum Silero speech onset; lower admits more brief noises |
| `vad.min_silence_duration` | 0.55 s | Silero speech-end silence; lower detects pauses sooner and can split thoughts; local audio detector requires at least 0.25 s |
| `vad.prefix_padding_duration` | 0.5 s | Retained speech prefix; this is not an extra endpoint wait |
| `vad.activation_threshold` | 0.5 | Silero speech probability; raising it can miss quiet speakers |

Minimum delay must not exceed maximum delay. Silero's silence detection and LiveKit's endpoint
delay have different purposes; changing both can compound their effect. A VAD-only setup cannot
tell whether a one-second pause, breath, or trailing “um” finishes a sentence. The local audio
detector can select the longer delay; the deterministic tests script that probability and do not
establish its accuracy on human speech. `max_endpoint_delay` is not a maximum utterance duration
and does not force the agent to talk over continuous speech.

Flux `stt.eot_threshold` remains restricted to 0.5–0.9 in this application. Although current
Deepgram documentation also permits 1.0, this worker does not implement manual ForceEndTurn.
`eot_timeout_ms` accepts 500–60000 ms. `null` leaves these values to Deepgram; SDK docstrings and
current provider documentation disagree about the timeout default, so set it explicitly when
comparing profiles. Eager threshold must be no greater than the effective EOT threshold (0.7
when unset). Preemptive LLM generation remains off by default; Phase 5 permits explicit native
opt-in for a separately approved experiment. Preemptive TTS remains unavailable. See
[PERFORMANCE.md](PERFORMANCE.md) for cancellation tests, wasted-token risk and the 30-turn A/B gate.

## Interruptions and recovery

| Setting under `interruption` | Default | Effect |
| --- | --- | --- |
| `enabled` | true | Native permission to interrupt speech |
| `mode` | `vad` | `adaptive` requires the explicit Cloud opt-in below |
| `min_duration` | 0.5 s | Speech duration before VAD interruption; smaller admits more incidental sounds |
| `min_words` | 0 | Optional transcript word gate; raising it can delay a one-word “stop” and is not backchannel classification |
| `false_interruption_timeout` | 2.0 s | Native recovery timer after a tentative interruption ends; `null` disables recovery |
| `resume_false_interruption` | true | Resume paused output when the SDK decides the interruption was false |
| `discard_audio_if_uninterruptible` | true | SDK discards input while uninterruptible speech plays |
| `backchannel_boundary` | [1.0, 1.0] s | Native start/end boundary controls for adaptive handling; `null` disables boundaries |
| `allow_cloud_inference` | false | Application opt-in required to select adaptive mode; not an SDK argument |

LiveKit owns speech handles, buffering, cancellation, transcript gates and turn ordering. A
tentative interruption can pause playout while retaining generation for recovery. A final real
user turn interrupts that handle, cancels obsolete generation, clears queued output and uses
the new request. A false interruption can resume the same handle rather than starting another
LLM call. Recovery requires an audio output supporting pause/resume; sinks without that support
cannot guarantee resumption. It also depends on transcripts and timing: VAD mode cannot reliably
classify “yeah”, “hmm” or “right” as acknowledgments. An actual short request must remain answerable.
Near adaptive turn boundaries the SDK can defer to VAD, so a backchannel may still interrupt
there. Boundary timing needs the same listening checks as duration and recovery settings.

Adaptive mode is a separate LiveKit Cloud inference service, including when the worker itself
is independently hosted. It requires LiveKit API credentials and applicable service access/quota.
Do not enable it or run it without approval for provider testing. To select it after approval:

```yaml
interruption:
  mode: adaptive
  allow_cloud_inference: true
```

The SDK creates and owns the adaptive client and falls back to VAD on an unrecoverable error or
unavailable access. The worker passes its configured LiveKit credentials to AgentServer; the
installed server exports them to its job environment for SDK authentication. No `.env.local`
contents or global shell settings are rewritten by this module. Mock verdict/failure tests prove
SDK routing, not acoustic classification, successful Cloud authentication, or quota availability.

The SDK has an automatic initial echo-cancellation warmup, normally three seconds of initial
agent speech, during which audio interruptions can be suppressed. Production preserves this
behavior. Synthetic tests use the public `aec_warmup_duration=None` constructor option because
their PCM cannot echo; they exercise warmed conversation behavior and do not establish first-turn
barge-in behavior. No custom “stop” tool, background encouragement, or greeting-on-reconnect
handler is added. The existing literal greeting is emitted once per job.

## Evidence required before acoustic acceptance

Automated tests run the actual 1.8.10 session with scripted STT/VAD/LLM/TTS and an in-memory PCM
sink. They cover pause cancellation/rearming, bounded semantic waiting, Flux EOT ownership,
playout clearing, interrupted transcript trimming using the sink's reported spoken prefix,
rapid corrections, false recovery, adaptive verdict/failure routing, shutdown and task cleanup.
The SDK owns interrupted history; its accuracy in production depends on actual playout and
provider-aligned timestamps. The silent mini-model test verifies loading and prediction only.

SDK per-turn metrics, numeric interruption counts and bounded p50/p95 summaries are logged when
`latency.metrics` is enabled, alongside native false-recovery events. The server audio-sink
acceptance estimate is measured after the public turn-completed hook; it is not audio-to-stop
or caller-heard latency. No raw user speech, prompt or transcript is logged by these handlers.
PERFORMANCE.md defines clock provenance, cache/retry unknowns and window limits. The synthetic
benchmark's short endpoint delays are fixture settings and do not change the defaults above.

The remaining acceptance run requires separate approval: first complete Phase 2's five real
voice turns and room lifecycle, then run the same Phase 3 script for Nova VAD, Nova mini and Flux.
Include a one-second hesitation, trailing filler, breath, short “yes”, long question, background
talk, cough, abandoned speech, “yeah/hmm/right”, early/late “Wait, stop”, rapid corrections and
disconnect during speech. Observe actual playback and interrupted history. Count clipped turns,
false EOTs, genuine interruptions and false stops; measure EOU and audio-to-stop distributions.
Use the plan's 20 warm turns plus five separate cold trials per measured configuration; no
recording without additional consent. A ten-turn real text conversation for coherence and
brevity is also blocked by the exhausted Groq budget. Scripted ten-turn tests verify ordering only.

Sources rechecked 2026-11-02: [turn detector](https://docs.livekit.io/agents/logic/turns/turn-detector/),
[turn tuning](https://docs.livekit.io/agents/logic/turns/tuning/),
[adaptive handling](https://docs.livekit.io/agents/logic/turns/adaptive-interruption-handling/),
[direct Deepgram plugin](https://docs.livekit.io/agents/models/stt/deepgram/),
[Flux EOT parameters](https://developers.deepgram.com/docs/flux/configuration).
Installed SDK source and signatures take precedence for arguments available in the pinned build.
