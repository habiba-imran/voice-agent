# Verification report — initial baseline

Evidence collected 2026-11-01 through 2026-11-02, Asia/Karachi. This is a source-distributed
baseline, **not a production-readiness or voice-quality certification**. PHASE_REPORT.md records
exact commands, failures, corrections and process-local environment settings. DECISIONS.md and
SDK_SIGNATURES.txt contain the source/API compatibility evidence.

| Gate | Status | Evidence / remaining work |
| --- | --- | --- |
| Phase 0 research and environment | PASS | Official docs, exact pinned SDKs, independent repo and source contract |
| Lock generation / consistency | PASS | 100 entries; unchanged SHA-256; locked sync audits 99 installed packages |
| Isolated dependency installation | PASS | Official, hash-verified artifacts; editable package installed; dependency check clean |
| Installed SDK compatibility | PASS | Agents and selected plugins 1.8.10; public signatures captured from isolated environment |
| Phase 1 settings/prompt/hooks | PASS | Locked checks for precedence, redaction, snapshots, no-op/failure/tool/cancellation behavior |
| Phase 1 text golden examples | PASS, limited sample | Five approved Groq requests; automatic assertions and manual review passed |
| Complete offline suite | PASS | 78 passed after fixing a real host-import collision; no skipped tests |
| Lint / format / compile | PASS | Locked Ruff and compileall exit 0; phase report records final reruns |
| Git/Docker exclusion policy | PASS | Env/deployment/recording/cache policy checked; .env.example remains eligible for Git |
| Actual Docker build/layers | BLOCKED | Docker unavailable; image phase not started |
| Clean nested source copy | PASS | New venv/editable install, no copied credentials/venv, foreign CWD and host shadowing test |
| Actual SDK discovery / current CLI help | PASS | Copied agent.py:server discovered; start help validated without network |
| Local Silero model | PASS, local only | Bundled CPU model loads and stream closes; no microphone or speech accuracy evaluation |
| Phase 2 provider/session implementation | PASS, offline only | Direct factories, native session options, bounded streaming and lifecycle/logging tests |
| Phase 2 real streaming conversation | BLOCKED | Five real Deepgram/Groq/Cartesia voice turns not authorized or run |
| Real worker registration / room lifecycle | BLOCKED | No live registration/room session; help/discovery are not connectivity proof |
| Voice selection / expressiveness | BLOCKED | Cartesia voice access/licensing and listening tests unverified |
| Acoustic interruption / turn detection | BLOCKED | Native SDK configured; no audio-to-stop or false-interruption measurements |
| Latency / prompt caching | BLOCKED | No voice timing samples or observed cache hit counts |
| Provider fault / concurrency acceptance | BLOCKED | Mock coverage exists; full transport/quota/concurrency matrix is a later phase |
| LiveKit Cloud deployment | NOT ATTEMPTED | Explicitly prohibited by the current instruction; no deployment actions performed |

The only authorized live consumption was **five Groq GPT-OSS 20B text requests**, max 256 output
tokens each, low reasoning, reasoning output excluded, no retries. All five completed successfully.
Currency spend, actual token usage, cache tokens and account quotas were not collected. That
five-request budget is exhausted. No Deepgram/Cartesia or other provider requests were performed.

Measured warm voice turns: **0**. Cold-connect trials: **0**. E2E/voice TTFT/TTFB/EOU p50/p95:
**not measured**. Audible barge-in yield and human listening scores: **not measured**.
No audio was recorded and no real user transcript was persisted. Synthetic text outcomes are
summarized in the phase report; mocked numeric fixtures are not provider measurements.

Phases 0 and 1 pass. Phase 2's offline baseline is implemented, while its overall exit gate remains
**BLOCKED** pending explicit provider/audio-test approval and actual LiveKit room acceptance.
Phases 3 onward remain unstarted. No frontend, RAG, application-specific tools, package publication,
advanced emotion processing, speculative optimization, or deployment was added.
