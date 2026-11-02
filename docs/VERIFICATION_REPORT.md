# Verification report — baseline, delivery, reliability, evaluation and deployment preparation

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
| Complete offline suite | PASS | Latest startup-fix run: 392 passed, zero failures/skips in 392.23s; includes independent copied unit rerun (264.27s total copy verification) |
| Lint / format / compile | PASS | Locked Ruff and compileall exit 0; phase report records final reruns |
| Git/Docker exclusion policy | PASS | Env/deployment/recording/cache policy checked; .env.example remains eligible for Git |
| Phase 8 image/deployment contracts | PASS, static only | Locked/pinned multi-stage image, non-root exec command, deny-default context, hardening, inert TOML and copied deployment metadata tested |
| Phase 8 health/lifecycle | PASS, offline only | Native SDK loopback HTTP/pool start/close and controlled job drain; synthetic registration/job state, no real job subprocess or OS signal |
| Actual Docker build/layers | BLOCKED | Docker unavailable; no image build, layer/rootfs inspection, Linux native-model or hardened runtime verification |
| Clean nested source copy | PASS | New venv/editable install, no copied credentials/venv, foreign CWD and host shadowing test |
| Actual SDK discovery / current CLI help | PASS | Copied agent.py:server discovered; start help validated without network |
| Local Silero model | PASS, local only | Bundled CPU model loads and stream closes; no microphone or speech accuracy evaluation |
| Phase 2 provider/session implementation | PASS, offline only | Direct factories, native session options, bounded streaming and lifecycle/logging tests |
| Phase 2 real streaming conversation | BLOCKED | Five real Deepgram/Groq/Cartesia voice turns not authorized or run |
| Phase 3 offline turn-taking/recovery | PASS | Actual 1.8.10 session with scripted providers/verdicts, synthetic PCM, cancellation/history/task assertions |
| Phase 3 local audio detector binary | PASS, smoke only | v1-mini loads and predicts on synthetic silence with no external network |
| Phase 3 Flux event ownership | PASS, offline only | Direct STTv2 factory; native session waits for provider EOT rather than VAD silence |
| Phase 3 adaptive handling | PASS, routing only | Scripted backchannels gated before LLM; injected failure falls back to native VAD; real Cloud service blocked |
| Phase 4 humanization | PASS, offline only | Typed opt-in controls, stable delivery prompt, bounded leading-filler/markup guards; neutral fallback and native cancellation verified |
| Direct Cartesia wire semantics | PASS, simulated peer | Actual plugin serializer, option snapshot, context IDs, connection pool and cancellation tested with in-memory WebSocket |
| Revised Phase 4 prompt | PASS contract only / live BLOCKED | Previous five live Groq checks used earlier prompt; no provider requests authorized for revision |
| Phase 4 expressive audio / A-B | BLOCKED | Voice audition, acoustic prosody/emotion/pause/filler quality and live interruption comparison not run |
| Phase 5 offline instrumentation / benchmark | PASS | Bounded correlated summaries; 12 synthetic sessions / 156 fake generations, zero surviving tasks; no provider/caller-heard claim |
| Phase 5 prompt / native speculation | PASS, offline only | Ten serialized bounded-history requests; adoption/stale cancellation with humanization on/off and no early TTS |
| Phase 5 native pool / fallback startup | PASS, offline only | Fake-wire Cartesia prewarm/reuse; model-load fallback verified outside event-loop thread |
| Phase 5 live latency / cost acceptance | BLOCKED | Five cold / 20 warm voice trials and 30 warm speculation trials per condition not approved; real token/cache/spend and acoustic quality unmeasured |
| Indexed source secret check | PASS, limited scope | 87 indexed files checked against five configured values; only .env.example indexed; not a general unknown-secret scan |
| Phase 6 native stream fault handling | PASS, offline only | STT/LLM/TTS × 401/403/429/503/timeout/network × before/after partial output; one attempt, no replay or surviving tasks |
| Phase 6 session management | PASS, offline only | Startup/connect deadlines, room/participant close, idle/duration, cancellation, first-cause latch, bounded drain/cleanup and repeated callbacks |
| Phase 6 concurrency / resource checks | PASS, local only | Three simultaneous native sessions with separate facts and failures, humanization on/off; task/generator closure verified |
| Phase 6 security boundaries | PASS, deterministic only | Credential/PII/exception omission, TLS URLs, known-secret prompt guard, retry rejection, input/request/tool bounds; injection cannot register tools/change policy |
| Phase 6 real transport / security acceptance | BLOCKED | Account errors, real reconnection/socket/RSS soak, quota/live concurrency and actual model injection refusal not run |
| Phase 7 SDK conversation runs | PASS, offline only | Public AgentSession.run/RunResult assertions, predetermined replies, correction history and interrupted output; no LLM judge |
| Phase 7 signal fixtures / local Silero | PASS, processing only | Six reproducible in-memory non-speech recipes; finite actual local Silero predictions on silence/noise; no speech accuracy claim |
| Phase 7 humanization control A/B | PASS, text/control only | Identical twelve-generation streams preserve facts/punctuation; filler guard and every style policy checked; no listening score |
| Phase 7 grouped evaluation / benchmark | PASS, synthetic only | 196 selected JUnit case reports in six categories; 18 benchmark groups / 234 fake generations / zero surviving tasks; full suite remains separate gate |
| Phase 7 live audio / hosted simulations | BLOCKED | CLI unavailable, Cloud/provider access unapproved and SessionHost disabled; YAML only shape-checked; first-live-audio checklist prepared |
| Real worker registration / room lifecycle | BLOCKED | No live registration/room session; help/discovery are not connectivity proof |
| Voice selection / expressiveness | BLOCKED | Cartesia voice access/licensing and listening tests unverified |
| Acoustic interruption / turn detection | BLOCKED | Native SDK configured; no audio-to-stop or false-interruption measurements |
| Latency / prompt caching | BLOCKED | No voice timing samples or observed cache hit counts |
| Provider fault / concurrency acceptance | BLOCKED, live scope | Phase 6 native fake-provider checks pass; actual transport/quota/concurrency acceptance needs approval |
| Cloud startup URL compatibility | PASS, offline only | HTTP(S) alias mismatch reproduced and fixed against installed SDK; remote TLS/userinfo/query/fragment guards retained, 44 regression cases added |
| Existing Cloud CrashLoop recovery | BLOCKED, unverified | Owner reports an existing agent failure; injected runtime URL unobserved. Temporary two-label diagnostic prepared; project-list wss/non-loopback alone does not explain the error. No Cloud action performed here |

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
Phase 3's requested offline implementation is complete; its acoustic/real-coherence gates remain
BLOCKED. Default Nova/VAD behavior is preserved. Phase 4 is implemented offline with humanization
off by default; automated gate PASS and live acceptance BLOCKED. Phase 5's requested offline
instrumentation/performance work is complete and verified; overall live acceptance remains BLOCKED.
Native preemptive LLM is explicit opt-in and defaults off; speculative TTS stays constrained off.
No frontend, RAG, application-specific tools, package publication, extra emotion-classifier model
or deployment was added. See HUMANIZATION.md and evals/humanization_ab.md for speech controls/
unexecuted listening protocol; PERFORMANCE.md defines timing boundaries, actual synthetic on/off
measurements, retained outliers and future real-audio/cost procedure. Phase 6's authorized offline
implementation and verification pass; live reliability/security acceptance remains BLOCKED. See
RELIABILITY_SECURITY.md for the failure policy, tightened retry/TLS validation, host responsibilities
and cooperative-cancellation/resource limits. Phase 7's offline implementation/verification passes;
real-audio/hosted/LLM-judge acceptance remains BLOCKED. EVALUATION.md and evals/scenarios.md map
evidence levels and coverage; evals/first_live_audio.md provides actionable approval, room/voice,
five-turn, cleanup and measurement steps. Runtime, prompt, dependencies and defaults were not
changed in Phase 7. Phase 8 now prepares a pinned non-root Dockerfile, Compose configuration,
inert Cloud template and local/Cloud runbooks. Native loopback HTTP/pool lifecycle with fake
registration/job state is covered offline; this is not real worker registration, a container,
an OS signal or an active call. Image build/layer inspection, Linux/native models, hardened runtime,
Cloud deploy/update/rollback and all live voice acceptance remain BLOCKED (Docker/CLI unavailable,
provider/Cloud usage and deployment unapproved). See SELF_HOST.md, DEPLOY_LIVEKIT.md and PHASE_REPORT.md.
Phase 9 onward remain unstarted.

Post-Phase-8 startup fix: the old application guard rejected HTTPS and loopback HTTP before the
SDK could normalize them. The validator now accepts those supported aliases under the existing
transport security policy; environment values are unchanged. A temporary startup line contains
only whitelisted scheme/host-category labels. The actual Cloud-injected URL, deployment-specific
cause and recovery remain unverified. See the latest PHASE_REPORT.md section for red/green tests,
source evidence and required manual runtime confirmation; no deployment or provider test occurred.
