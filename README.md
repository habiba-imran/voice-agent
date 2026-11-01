# VoiceAgent Core

Reusable Python source folder for a direct Deepgram → Groq → Cartesia worker using LiveKit Agents.
**Work in progress:** see docs/PHASE_REPORT.md for actual phase gates. No live audio, quality,
latency, deployment, or production-readiness claim is made by the foundation tests.

Use Python 3.12 and uv. Operate from this directory, including when nested in another repository:

```powershell
uv sync --locked
uv run agent.py config
uv run agent.py validate --mode console
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

The generic prompt stays a stable prefix. Optional session metadata is bounded and appended
as untrusted data; it must contain no secrets. Host tools are explicit, async setup hooks only.
Hook timeout/error results in a session with no extensions, and a sanitized warning.
The host owns authentication, participant tokens, UI, storage, and business integrations.

No LiveKit Cloud deployment is authorized. Keep livekit.toml and deployment identities unique per
copied project; they are ignored. Cloud injects LIVEKIT_*; only provider keys are supplied as
additional cloud secrets. Local/self-hosted room workers require all six credentials/URL values.

See docs/DECISIONS.md for official source links and compatibility limits. Provider access and paid
testing, microphone use, recording, Docker execution, and cloud deployment require their own
verification and any necessary authorization. No recordings or transcripts are persisted by default.
