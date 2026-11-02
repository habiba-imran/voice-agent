# Offline evaluation and evidence levels

Phase 7 adds a repeatable development evaluation without changing runtime behavior, provider
models, dependencies, prompt or experimental defaults. The complete pytest suite remains the
release regression gate; the smaller evaluation command groups existing and new assertions.
Real provider, transport, speech-quality and hosted-simulation acceptance remain BLOCKED.

## Commands

Run from the copied voiceagent directory in its locked development environment:

```powershell
uv run python scripts/evaluate_offline.py --list
uv run python scripts/evaluate_offline.py --output evals/results/phase7_offline.json
uv run python scripts/benchmark.py --turns 10 --concurrency 3 --delay 0.005 --output evals/results/phase7_synthetic.json
uv run pytest -q --durations=5
```

The first command only lists categories. Evaluation accepts repeated --category selections from
a fixed allowlist: conversation, audio_signals, delivery, performance, failures and security.
There is no arbitrary script, live-provider, judge, credential or deployment option. The child
pytest environment strips provider/LiveKit keys, VOICEAGENT overrides, PYTHONPATH and pytest
argument/plugin overrides. It uses the existing external DNS/socket-denial fixture (loopback
only for Windows asyncio). Neither runner loads .env.local itself. All selected tests construct
scripted providers or fake network peers; genuine Silero inference uses bundled local weights.

The evaluator uses the same installed Python and a 240-second child timeout. It creates temporary
JUnit XML, extracts per-category numeric counts/status, and deletes raw XML/stdout rather than
persisting test messages/tracebacks. Nonzero pytest exit, missing categories, failed/error/skipped
cases or missing/malformed report cannot become PASS_OFFLINE. The output reports JUnit case
records, not an invented provider success rate. The environment, report guards and list command
have deterministic tests. Raw evaluation artifacts remain excluded from Git/Docker.

Reports include SDK/Python versions, prompt/signal-manifest and generated PCM hashes, synthetic provenance,
configured-control A/B diagnostics and null listening/caller-heard values. The benchmark separately
reports measured local component/sink-acceptance distributions with sample counts, per condition
and outcome. Its script delays and event/PCM markers are not real provider latency. See
PERFORMANCE.md for percentile/clock definitions, limitations and the real-audio protocol.

## Supported SDK APIs and limits

The installed 1.8.10 public AgentSession.run, RunResult.events, expect.next_event().is_message(),
ChatMessageAssert.event and expect.no_more_events are used directly. Scripted providers exercise
the normal production VoiceAgent LLM node and native session pipeline. We pass output_options=None
to disable structured-output re-prompt retries. No LLM judge is instantiated. Tests verify one
reply per turn, serialized correction history, interrupted run events and obsolete-tail suppression.
They do not establish that Groq answers a question correctly: fake replies are predetermined.

The SDK RunResult assertion interface lives in livekit.agents.voice.run_result, not a Python
livekit.agents.testing package. SDK_SIGNATURES.txt records inspected signatures. Older examples
or current documentation may suggest model-based judges; those need paid access and are excluded
from these offline commands. No new test package or SDK upgrade is required.

Hosted Agent Simulations are different: the current official workflow uses CLI >=2.19.0, Cloud
access and model-driven users/judges; audio mode uses real STT/TTS/media. CLI is unavailable here.
The worker also disables SessionHost for remote driving. Prepared YAML was shape-checked only;
running debugger/Cloud scenarios first needs compatibility review and an explicit authorized
opt-in path. We do not silently enable remote observation or change record=False. Commands and
actual CLI/schema/registration are unverified. See evals/scenarios.md for coverage and the template.

## Reading evidence

| Evidence | Establishes | Does not establish |
| --- | --- | --- |
| Pure transforms/config assertions | Stable styles/controls, factual text preservation, sparse filler budget, safe limits | Audible expression or model adherence |
| AgentSession/RunResult with scripted STT/LLM/TTS | Native routing/history/cancellation/cleanup, one committed response | Real speech recognition, reasoning or network timing |
| Fake Cartesia WebSocket with actual plugin | Serializer, context IDs, pool/prewarm/reuse/cancellation | Remote socket access, voice licensing or audible interpretation |
| Generated PCM plus real Silero | Framing and finite local model inference | Natural hesitation/noise/overlap classification accuracy |
| Deterministic clocks/controlled-delay benchmark | Collector math, correlated local timing, bounded state, synthetic concurrency | Caller-heard audio, real latency improvement or capacity guarantee |
| Future authorized real room/audio | Only measured and reviewed scenarios | General production quality, untested accounts/devices or soak |

No new audio/transcript persistence, network service, frontend or host integration exists. For
CI, use the locked offline-test commands with no provider secrets; preserve the network-denial
fixture and fail on test errors. Full clean-copy verification requires locked package artifacts
or dependency access; local wheelhouse/cache setup is described in PHASE_REPORT.md. Don't enable
hosted/paid tests in CI under the offline category label.

First authorized audio steps and required approvals are in
[first_live_audio.md](../evals/first_live_audio.md). Humanization remains disabled until the
existing A/B listening gate passes. Phases 2–6 and Phase 7 real-audio/hosted gates remain BLOCKED.

Official documentation rechecked 2026-11-02:
[unit tests](https://docs.livekit.io/testing/unit-tests/),
[Agent Simulations](https://docs.livekit.io/testing/simulations/),
[scenario format](https://docs.livekit.io/testing/simulations/write-a-scenario/),
[CLI debugger](https://docs.livekit.io/testing/debugger/).
