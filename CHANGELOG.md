# Changelog

## Unreleased — post-roadmap customization and integration

- Opt-in customization folder with backward-compatible legacy configuration and secret precedence.
- User-first, exact static and dynamic greetings; optional guarded end-session tool and host action.
- Native speech-handle farewell lifecycle with user-activity checks and SDK StopResponse after
  cancellation, preventing stale tool follow-up from ending an interrupted conversation.
- Independent React/Next.js references and a Cloud-only token/dispatch gateway with persisted
  single-host transactional quotas and deadline cleanup. Host authentication integration is required.
- Offline SDK/SQLite/HTTP/JWT/browser-controller tests. No deployment, paid/live acceptance,
  public release, licensing sign-off or universal multi-host gateway support is claimed.

## 0.1.0 — source candidate, unreleased

- Standalone editable Python source folder with external prompt, typed settings, optional host
  hooks and locked LiveKit Agents/plugins 1.8.10 dependencies.
- Direct streaming Deepgram → Groq GPT-OSS 20B → Cartesia pipeline, local Silero and selectable
  native turn/interruption handling. Optional humanization and speculation remain disabled by
  default; no general naturalness or latency claim is made.
- Bounded lifecycle/error handling, configuration validation, sensitive-log omission, numeric
  instrumentation and deterministic conversation/fault/signal simulations.
- Pinned non-root Docker preparation, private runtime secret injection, independent per-project
  deployment template and operational runbooks.
- SDK-compatible HTTPS / loopback HTTP URL validation and temporary sanitized startup diagnostics.
- Owner-confirmed Cloud deployment and at least one audible microphone conversation on source
  revision `1fe4b9f`, reported 2026-11-02. This is qualitative evidence; turn count, live timing,
  errors, cleanup and formal interruption measurements were not collected.

This is a private source-handoff candidate, not a published release. Quantitative/live acceptance,
image inspection, rollout/drain/rollback evidence, voice permissions and source/third-party license
review remain open. See [release acceptance](docs/RELEASE.md) and [phase evidence](docs/PHASE_REPORT.md).
