# Reliability, security and session contract

Phase 6 implements and tests an offline failure policy on locked LiveKit Agents 1.8.10. It does
not certify real provider recovery, remote socket closure, room reconnection, production capacity
or acoustic behavior. Phases 2–5 live acceptance remain BLOCKED. No additional provider, model,
classifier, persistent store, deployment or dependency is introduced.

## Failure policy

| Condition | Behavior |
| --- | --- |
| Missing/malformed configuration or credentials | Offline validation fails before provider requests; known credential values are rejected in the prompt/session metadata |
| Provider 401/403, 429, 5xx, network drop, timeout | Log fixed component/category/status/recoverable fields; first nonrecoverable event ends the session through native shutdown |
| Failure after text/audio starts | Cancel remaining generation and clear pending output through LiveKit; no replay, resume of failed output or provider switch |
| Recoverable SDK notification | Count/log it; let the SDK manage its own state. Do not create another response or an application retry |
| Idle/session duration | Request graceful native drain, then force native interruption when the drain allowance expires |
| Terminal room disconnection | Request immediate native shutdown; remove the application room listener during cleanup |
| Linked participant leaves | Explicit RoomOptions.close_on_disconnect uses SDK disconnect-reason routing; no automatic room deletion |
| Transient reconnect | SDK retains control; application does not generate another greeting or recreate clients |
| Startup exceeds its deadline | Cancel the cooperative startup await, close session/clients, report startup_timeout |
| Cleanup timeout/error | Attempt remaining clients, report a fixed failure code; never report a confirmed successful resource close |

Safe fallback means ending an unavailable session predictably. The core does not call another
provider or send a speculative apology through failing TTS. An audible failure announcement is
not guaranteed when a speech service fails. The consuming host should present a generic service
unavailable state based on the job/session end, without exposing provider diagnostics or creating
an automatic reconnect loop. No frontend is supplied here.

`limits.max_retries` is now constrained to **0**. Previously accepted nonzero values fail
validation, rather than silently changing behavior. Both SDK stream retries and Groq HTTP retries
remain zero. The installed SDK uses a 0.1-second first retry and does not supply a configurable
jitter/Retry-After policy here. Blind 429 retries would be unsafe. Zero retries are a bounded
policy; no custom retry scheduler is added. Future safe retries need explicit provider guidance,
budget/jitter tests and proof that partial output cannot replay. SDK stream tests also retain
its actual error/cancellation paths rather than replacing the stream loop with mocks.

## Session limits and cleanup

| Setting | Default | Meaning |
| --- | --- | --- |
| runtime.startup_timeout_seconds | 30 s | Shared deadline across prompt/hook/model bootstrap and session.start/connect |
| runtime.max_session_seconds | 1800 s | Active-session limit; startup has its separate deadline |
| runtime.idle_timeout_seconds | 120 s | Native SDK user-away timer; active speech does not count as idle |
| runtime.drain_timeout_seconds | 5 s | Graceful shutdown allowance before public session.interrupt(force=True) |
| runtime.shutdown_timeout_seconds | 10 s | Bounded session close await and each individual provider close |
| runtime.hook_timeout_seconds | 2 s | Optional setup hook deadline; failure disables the hook |
| limits.request_timeout_seconds | 10 s | Native provider request/connect timeout; not a guarantee of total response duration |
| llm.max_output_tokens | 256 | Completion-token cap per request |
| limits.max_llm_requests | 100 | Per-agent LLM-node starts per session, including tool continuations/speculation; not a count of confirmed billed HTTP requests |
| limits.max_input_bytes | 8192 | UTF-8 size of latest user text checked before LLM chat; exceeding it ends the session |
| limits.max_tool_steps | 3 | Explicit native tool-chain bound, configurable 0–5; each LLM start also consumes the session request allowance |

The input byte cap applies before model invocation, including text-driven replies. It does not
bound an incoming network frame before the SDK receives it. Hosts must also limit participant
message/audio ingress and authenticated room admission. Request count is in-memory per agent and
resets for a new session. It is a coarse safety budget, not a currency limit. Provider token usage
is reported only when emitted by the SDK, including the cache-provenance limits in PERFORMANCE.md.

One SessionLifecycle instance owns the local stop cause, closed/finished signals and at most one
stop watchdog. First close/stop reason is latched; cleanup-generated close events cannot overwrite
it. A later hard stop during drain forces native interruption. Timer/watchdog tasks are cancelled
and awaited, the session closes, and an AsyncExitStack attempts TTS, LLM, STT cleanup in reverse
order. The job shutdown callback waits for the same entrypoint cleanup rather than closing twice.
Numeric session duration/reason logs and existing token/latency summaries support resource review.

Each provider close has its own timeout so a failed close cannot prevent the remaining close
attempts. In the worst cooperative timeout path, shutdown can take the drain allowance, a watchdog
close wait, a separate session-close wait and three provider-close waits (55 seconds at defaults).
Configure the host supervisor's termination grace accordingly. Python
timeouts depend on cooperative cancellation. Native model initialization in a worker thread,
blocking host code or a coroutine that suppresses cancellation cannot be forcibly killed safely
by this module. Process termination/supervision is the host's final boundary; no private SDK task
manipulation, process kill or unverified guarantee is added. Real socket/long-duration RSS soak
tests remain blocked; local task counters do not prove arbitrary production memory is leak-free.

## Logging and data handling

Configured credential values are filtered from messages and nested fields, longest match first.
Prompt/transcript/request/response/body/header/token and SDK PII fields are omitted. Exception
payloads and stack source lines are suppressed, retaining the exception class. Unknown objects
become type names rather than using repr/str. Recursive metadata is depth/item bounded. Normal
core diagnostics use fixed reason/category/status fields; provider/SDK message bodies become
sdk_event and nonnumeric SDK extras are omitted. This deliberately sacrifices raw SDK diagnostics
to keep unknown transcripts and response bodies out of default logs.

`protect_logging` reuses a filter on each current root handler and merges up to 64 credential/URL
values atomically, so concurrent session setup cannot remove another session's protections.
This bounded process-level redaction registry is not conversation state. One worker serves one
deployment's settings; restart on credential rotation/capacity exhaustion. A host adding custom
handlers after configuration must apply protect_logging again and must not log raw user content.
This is structured-data omission and configured-value matching, not an arbitrary PII detector or
unknown-secret scanner. No LLM-based redaction service is enabled.

Effective config printing also redacts known values accidentally placed in noncredential fields;
unknown config field names are omitted from diagnostics. Room URLs require TLS remotely: wss and
the SDK-supported https alias are accepted. Plaintext ws/http is limited to localhost, 127.0.0.1
and ::1. Agents 1.8.10 performs the actual http->ws / https->wss conversion; settings/environment
values are not rewritten. Embedded userinfo (including empty userinfo), query and fragment are
rejected without echoing input; invalid/zero ports and missing hosts remain rejected. Cloud marker
variables do not bypass validation. Independently hosted secure endpoints remain supported.

A temporary startup diagnostic, requested to investigate a Cloud CrashLoop, prints one JSON line
to stderr before room-mode startup validation/SDK logging setup. It contains exactly
`livekit_url_scheme` and `livekit_url_host_category`. Scheme is restricted to wss/https/ws/http,
unsupported or unparseable; host category is loopback/non-loopback/unknown, classified without DNS.
The line contains no hostname, port, path, userinfo, query/fragment, credential or parser exception.
It is omitted for config/validate/help/console. Remove this temporary diagnostic after the owner
confirms the runtime-injected URL shape. A project-list URL does not establish that runtime value.

Every worker start passes record=False and session_host=False. In installed 1.8.10, record=False
resolves audio, transcripts, trace and log recording flags to false; the module provides no raw
transcript/audio persistence sink. Session history in process and provider request content still
exist to conduct a conversation. Provider retention/account settings and host-installed exporters
are separate responsibilities; don't infer their policies from local recording flags. SDK Cloud
PII redaction is a separate service/configuration and is not silently activated.

## Threat surface and host responsibilities

- Prompt injection: external speech, text, tool results and session metadata are untrusted data.
  Static policy precedes metadata; metadata cannot register tools or change settings. These
  boundaries are tested offline. A real model's refusal behavior remains a live test; prompt
  wording cannot guarantee resistance to all injections.
- Unauthorized tools: no core business tools, shell, arbitrary module loader or implicit plugin
  discovery exists. Only a trusted host registers decorated functions. The host must authorize
  each tool invocation, scope tenants, validate arguments and make writes idempotent. Never treat
  LLM output as authorization, including after interruption/retry.
- Credential leakage/replay: secrets stay server-side, outside source/build context. Hosts issue
  short-lived, room-scoped LiveKit tokens with minimum publish/subscribe grants and authenticated
  admission. Do not expose provider keys or long-lived signing secrets in clients. Token issuance
  is documented here, not implemented.
- Expensive session floods: explicit named dispatch is not authentication. Hosts own tenant/user
  rate limits, room admission, worker capacity, provider account budgets and cost alerts. Do not
  assume free tiers or fixed provider concurrency limits. Start capacity tests on a designated
  project only after approval. Three synthetic concurrent sessions are isolation evidence, not
  a production concurrency recommendation.
- Consent/licensing: identify the agent as AI, use an authorized voice and obtain required consent
  for cloning, microphone use and recording. Recording/export features need explicit disclosure,
  retention/access controls and separate implementation/testing. Existing flags do not opt in.

## Verification boundary

Deterministic checks run actual native STT/LLM/TTS stream error handling for 401/403/429/503,
timeouts and connection errors, each before and after one partial output. They assert one attempt,
one terminal error and no remaining tasks. Native-session tests run three simultaneous independent
sessions, STT/LLM/TTS errors, humanization on/off, partial output, graceful drain expiry and no
stale/duplicate continuation. Entrypoint tests cover startup/connect failures and timeouts, idle,
duration, room/participant close, cancellation and repeated job callbacks. Security tests cover
redaction, accidental prompt/metadata credentials, injection boundaries, URLs and retry rejection.
Existing full tests retain streaming, interruption, preemptive adoption, prompt and portability
coverage. See PHASE_REPORT.md for exact commands/results/failures.

Live provider error translation, quota/Retry-After headers, reconnection under real network loss,
socket/OS-resource soak, caller-heard partial-audio behavior, actual injection refusal and load
capacity remain BLOCKED. Obtain explicit provider/room test approval, a designated project and
authorized voice before these checks. Recording and deployment each require separate approval.

Official sources checked 2026-11-02: [session lifecycle](https://docs.livekit.io/agents/logic/sessions/),
[events/errors](https://docs.livekit.io/reference/agents/events/),
[fallback choices](https://docs.livekit.io/agents/logic/fallback-strategies/),
[PII scope](https://docs.livekit.io/testing/observability/pii-redaction/).
Installed 1.8.10 source and refreshed SDK_SIGNATURES.txt establish the options used here.
