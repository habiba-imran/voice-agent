# Acceptance scenario map

All text and signal inputs are generic, synthetic and source-owned. PASS_OFFLINE means only the
named deterministic assertion passed. No row certifies speech quality, provider access or remote
playback. Use docs/EVALUATION.md for commands and first_live_audio.md for the first authorized run.

| Scenario | Existing/new executable evidence | Remaining real acceptance |
| --- | --- | --- |
| Greeting/simple question | test_turn_behavior::test_normal_turn_commits_once_and_streams; test_sdk_runs | Brief spoken answer, initial echo warmup |
| Multi-turn correction/context | test_sdk_runs::test_native_run_results_keep_multiturn_corrections_and_one_reply; ten-turn history tests | Groq understanding, accuracy and brevity |
| Mid-thought hesitation/trailing um | test_turn_behavior::test_pause_then_continuation_produces_one_combined_turn; semantic-negative-EOT tests; hesitation signal recipe | Real one-second pause/breath classification, clipped turns |
| Uh-huh/yeah/right during speech | Native controlled-adaptive backchannel and word-gate tests | Acoustic backchannel accuracy and real Cloud service access |
| Genuine stop/correction | test_sdk_runs::test_native_pending_run_interruption_cannot_emit_obsolete_tail; native early/late LLM/TTS interruption tests | Caller-heard audio-to-stop and interrupted-history alignment |
| False mic/noise interruption | test_turn_behavior::test_noise_pauses_then_resumes_same_generation; false_interruption recipe | Real noise/cough classification and reliable resume |
| First audio chunk interrupted | Native before-first-token/during-TTS tests and preemptive cancellation matrix | Actual remote chunk/transport cancellation |
| Long factual response | Native incremental chunk/marker tests, expression factual/technical split tests | Concision, pronunciation, natural phrase continuity |
| Conflicting facts/unknown request | Serialized context tests; prepared Cloud context/unknown scenarios; earlier five-case text fixtures | Real refusal/uncertainty behavior with current prompt |
| Repeated exchanges | Ten-turn ordered history tests; twelve-generation controlled delivery A/B | Natural variation, repetition/filler frequency in real model output |
| Contextual emotions/styles | Every supported style policy test; Cartesia fake-wire emotion/control serialization | Audible emotion/pitch/intonation appropriateness |
| Punctuation/markup/nonverbals | Expression tests across character splits; exact A/B body preservation | Actual pauses/prosody; active markup/laughter remain disabled |
| Rapid speech/follow-ups | rapid_speech signal recipe; ordered three-turn PCM-feed test; rapid interruption tests | Rapid spoken-word recognition and turn ordering |
| Background noise/overlap | Deterministic noise/mixed-tone/overlap recipes and actual local Silero processing smoke | WER, false triggers and foreground/background separation |
| Reconnect/leave | Entrypoint room/participant events, repeated shutdown callbacks, concurrent-session isolation | Live transport reconnect, duplicate-greeting/audio behavior |
| Rate limits/invalid credentials | Native STT/LLM/TTS 401/403/429/503/timeout/network matrix before/after partial output | Provider account/error translation, quotas and costs |
| Silence/no user input | Native silence/no-extra-response and idle/duration deadline tests; zero PCM recipe | Room silence/idle shutdown with real devices |
| Concurrency/resources | Three independent native sessions; bounded metrics; benchmark cancellation/fault/cleanup | Remote sockets, RSS soak, capacity and provider concurrency limits |

Module names above refer to tests/unit; the SDK/node/provider mocks are deliberate. The user,
transcript and response content in these tests is predetermined. No model judge or naturalness
score is used. Existing tests provide most of this coverage; Phase 7 adds shared fixtures, native
RunResult assertions, control A/B diagnostics and a consolidated runner rather than duplicating
production turn-taking logic.

## Reproducible signal recipes

tests/fixtures/audio_scenarios.json defines six stable IDs, seeds, 16 kHz mono PCM and 20 ms
frames. tests/unit/audio_fixtures.py generates deterministic signed 16-bit little-endian samples
entirely in memory. Tones (220 Hz), seeded bounded noise, a second overlapping tone (330 Hz) and
silence stand in for timing/framing only. They contain no spoken words, voice samples or recorded
person. Total duration is capped at 20 seconds; no device, provider, file recording or model
download is involved. The manifest hash is included in the offline report.

Each recipe includes an English script for a future consenting speaker. To test acoustic speech
behavior, replace placeholders with the same authorized speech recording across conditions, or
read the same script live; obtain storage consent separately. Retain speech/noise timing and
document device/level/SNR actually measured. The fixture's bounded noise amplitude is not a
calibrated room-noise or speech SNR. Never call the tone sequence a speech-recognition test.

Actual local Silero runs process generated silence/background signals and emit finite probability
events. That is CPU-model plumbing evidence; no speech-classification threshold or quality score
is asserted from these signals. Other native session tests explicitly script STT/VAD verdicts.

## Humanization A/B

delivery_evaluation.py compares twelve identical text streams with humanization disabled/enabled.
It verifies exact substantive text, identifier/URL/decimal and punctuation preservation, leading
filler accounting, static delivery guidance and neutral-versus-auto Cartesia options. Both sides
use the same deliberately repetitive source strings. These counts characterize the guard, not
what Groq spontaneously says or a person's perception. CPU overhead has a separate benchmark.

Use humanization_ab.md for authorized voice audition and actual listening. Use the same voice,
model, prompt, task, network and consented inputs across conditions; counterbalance order. No
emotion, pause, naturalness or caller-heard latency winner is selected offline.

## Prepared hosted scenarios — NOT RUN

livekit_scenarios.yaml follows the current documented id/name/scenarios format and supplies five
generic caller goals. Local tests validate shape and unique IDs, not the installed CLI/server
schema. They are future templates with no attached verdict, account, deployment identity or
userdata. Cloud simulation users/judges and audio pipelines use real services. Both text and
audio modes require fresh explicit approval; simulation is not a synonym for offline.

The current worker intentionally uses session_host=False. Remote debugger/simulation driving
needs a reviewed, explicit SessionHost opt-in path before it can be treated as compatible.
This phase does not enable it, alter recording defaults or claim the templates are runnable
against this worker. The existing local room worker is the first live-audio path after approval.
