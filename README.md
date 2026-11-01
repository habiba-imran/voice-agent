# VoiceAgent Core

Reusable Python source folder for a direct Deepgram → Groq → Cartesia worker using LiveKit Agents.
Phase 0 and Phase 1 are verified. The Phase 2 baseline is implemented and tested offline;
real Deepgram/Cartesia audio and LiveKit room acceptance remain blocked on approval.
No voice quality, latency, deployment, or production-readiness claim is made.

Use Python 3.12 and uv. Operate from this directory, including when nested in another repository:

```powershell
uv sync --locked
uv run agent.py config
uv run agent.py validate --mode console
uv run agent.py start --help
uv run ruff check .
uv run python -m compileall -q src agent.py
uv run pytest -q
```

Fill the existing ignored `.env.local` locally; `.env.example` lists the variable names. Never put
secrets in YAML or prompt.md. Select an authorized Cartesia voice via VOICEAGENT_TTS__VOICE_ID.
`config` prints redacted effective settings; `validate` requires credentials and reads the prompt
without making network calls. Missing values produce exit code 2 with exact missing key names.

Precedence: constructor overrides > process environment > project .env.local > selected YAML >
typed defaults. Override nested values with VOICEAGENT_TTS__SPEED=1.1, for example. Config/prompt
paths use VOICEAGENT_CONFIG_PATH and VOICEAGENT_PROMPT_PATH; relative paths resolve here.
Blank environment values are treated as absent. Settings load once per worker; restart after
editing config. Prompt.md is read once for each new session; existing sessions retain a snapshot.

The generic prompt provides a stable prefix. Bounded session metadata is appended as untrusted
data; it must contain no secrets. The SDK truncates each LLM request to recent conversation items
while preserving leading instructions. No summary/classifier LLM is used. Groq reasoning is
excluded through the verified chat API. Cache hits are automatic when supported, not guaranteed.
Host tools use explicit async setup hooks. `resolve_extensions` disables failed or malformed
optional hooks with a sanitized warning and validates registered LiveKit function tools.
The host owns authentication, participant tokens, UI, storage, and business integrations.

After approving provider/LiveKit usage, the worker command is `uv run agent.py start`.
`dev` delegates to `start --dev` without hot reload. The installed 1.8.10 SDK deprecates its
rich Python CLI; this module uses the current `python -m livekit.agents` entry instead and
exports `agent.py:server` for discovery. Interactive console mode requires a LiveKit CLI TCP
driver (`--connect-addr`), not a bare standalone `agent.py console` command. LiveKit CLI is
unavailable here; actual console, registration and room audio have not been tested.

The runtime uses direct provider instances and explicit local Silero VAD. Constructing a real
AgentSession starts SDK provider prewarming, so offline tests mock the session and clients.
Clients are reused within a session and closed on exit. Default session/idle limits are 1800/120
seconds; SDK request retries default to zero. The SDK owns turn detection and cancellation.
Recording and session-host capture are explicitly disabled; transcript persistence has no sink.
Error logging omits payloads and redacts configured credentials. Full provider-fault, reconnect,
acoustic interruption, quota and concurrency acceptance belong to later phases.

On this Windows machine, installation needed a hash-verified offline wheelhouse because large
official PyPI downloads stalled. The final locked sync and dependency check pass. Recovery tools
and artifacts are ignored under `.tools/`; no global Python, uv, DNS, or antivirus settings changed.
See docs/PHASE_REPORT.md for exact recovery/verification commands and offline test environment.

No LiveKit Cloud deployment is authorized. Keep livekit.toml and deployment identities unique per
copied project; they are ignored. Cloud injects LIVEKIT_*; only provider keys are supplied as
additional cloud secrets. Local/self-hosted room workers require all six credentials/URL values.

See docs/DECISIONS.md for official source links and compatibility limits. Provider access and paid
testing, microphone use, recording, Docker execution, and cloud deployment require their own
verification and any necessary authorization. No recordings or transcripts are persisted by default.
