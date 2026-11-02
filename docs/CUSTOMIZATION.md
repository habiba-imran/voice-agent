# Customization without changing the voice pipeline

This extension is implemented and source-reviewed for the reusable handoff. It has not been deployed. Existing
Cloud behavior and provider credentials are unchanged. Earlier release blockers in RELEASE.md
still apply; deterministic tests do not establish new live latency or audio-quality results.
Portfolio-specific integration and any Upstash adapter are deferred to the consuming application.

## Start with the three developer files

```text
customization/
  agent.yaml       # Identity, models, voice, greetings, ending, turns and operational limits
  prompt.md        # System instructions/personality
  .env.example     # Template only; copy privately to .env.local
```

From your cloned voiceagent folder:

```powershell
uv sync --locked
if (-not (Test-Path customization/.env.local)) {
  Copy-Item customization/.env.example customization/.env.local
}
# Fill your own credentials/authorized voice locally, then:
uv run agent.py validate --mode room
uv run agent.py start --help
```

Do not overwrite an existing private file. The template selects customization/agent.yaml and
customization/prompt.md. Merely checking out the customization directory does **not** switch
existing installations away from their legacy configuration. Without private opt-in or explicit
path variables, config.example.yaml and root prompt.md remain the defaults.

Precedence is constructor overrides > process environment > customization/.env.local > root
.env.local > selected YAML > typed defaults. Blank env values remain absent; they do not erase
legacy credentials. Explicit constructor config_path wins over env path selection. Relative paths
resolve from the copied project root, not the host CWD. No parent/project env discovery is added.

On Cloud, select the two customization paths explicitly as nonsecret environment settings when
you approve a source update. Cloud injects LIVEKIT_*; never upload those values from the local
template as additional Cloud secrets. Docker includes only the customization YAML/prompt, not its
private env file. Self-hosted Compose can use VOICEAGENT_ENV_FILE to choose a private literal env
file as documented in SELF_HOST.md. No deployment is performed by configuration validation.

## Settings and supported combinations

| Setting | Purpose |
| --- | --- |
| runtime.agent_name | Explicit dispatch name; must match the backend gateway's agent name |
| identity.name / identity.role | Optional spoken identity/role; default null preserves old instructions |
| prompt.md | Personality and task instructions, snapshotted for each session |
| stt.model / listening.turn_detection | nova-3 with vad or semantic; flux-general-en requires stt detection and matching Flux settings |
| llm.model | Only openai/gpt-oss-20b through the existing Groq client |
| tts | sonic-3, authorized voice UUID, en, supported emotion, speed and volume |
| listening / interruption | Existing endpointing, local VAD and SDK interruption/recovery settings |
| humanization / latency | Existing opt-in controls and instrumentation; defaults remain unchanged/off where previously off |
| runtime / limits | Duration, idle/startup/shutdown deadlines, bounded input/history/request/tool limits |
| greeting / ending | Optional opening and end-session behavior below |

This does not add providers, arbitrary models, languages, unsupported pitch/SSML controls or a
second emotion LLM. Existing advanced constraints remain validated; see TUNING.md, HUMANIZATION.md
and RELIABILITY_SECURITY.md. Restart workers for settings changes; new sessions snapshot prompts.

## Three greeting modes

- `user_first` (default): no automatic speech or greeting LLM request.
- `custom`: set greeting.text; exactly that text is passed to SDK say(), with no LLM request.
- `dynamic`: set greeting.instructions and leave text null. One opening uses the existing LLM,
  common prompt/identity and optional SessionExtensions.metadata. Tool choice is disabled for it.

Each session latches its greeting once. It waits for the participant within the existing startup
deadline, yields if the user already started, and relies on native interruption/cancellation.
Transient reconnection does not replay it. Legacy runtime.greeting maps to custom mode; combining
a nonempty legacy greeting with new greeting settings is rejected rather than silently choosing.

## Ending and explicit host actions

ending.enabled defaults false, preserving existing behavior. When enabled it registers a real
LLM-callable end_session tool. The main model must confirm explicit current-user intent, and a
conservative whole-utterance policy independently rejects casual/quoted/negated mentions of bye.
Ambiguous or unsupported phrasing should prompt clarification; this is not a universal intent
classifier or proof of model robustness. The built-in policy is English, matching supported STT.

farewell_mode is custom, generated or none. Custom uses SDK say() without an extra LLM call;
generated explicitly requests one reply from the existing LLM, with tools disabled. Both greeting
and generated farewell opt-ins consume requests when actually used. A bounded farewell timeout
prevents indefinite waiting. Duplicate operations share one result. SDK tool context is retained
inline, using RunContext.wait_for_playout() before the separate farewell speech handle.

New user activity aborts pending hangup even on a playout exception/timeout. A cancelled tool
ending raises the SDK's StopResponse to suppress a follow-up from the stale end intent. The user
can continue; no extra classifier or custom interruption engine is introduced. Cancellation and
disconnect cleanup remain owned by the existing session lifecycle and SDK.

An embedding Python host can call `await agent.end_session(speak=True)` explicitly even when the
LLM tool is disabled. Trusted host code may supply a synchronous boolean ending_policy through
SessionExtensions; it is never imported from YAML. Context uses the existing bounded metadata
hook and remains marked untrusted in instructions. See COPY_INTEGRATION.md for explicit hooks.

Ending the worker session does not delete an arbitrary host room. The web gateway owns its
single-caller rooms and revokes/removes the caller and deletes the room on explicit application
end or deadline. Its frontend also ends the reservation when the agent leaves. See
[the integration guide](../integrations/README.md).

## Existing worker versus your own worker

To connect a website to an already deployed worker, use the integration gateway with that
project's server-side credentials and matching dispatch name; no worker redeployment is needed.
That worker retains its deployed prompt/settings/features. To activate these new customization,
greeting or ending controls, customize your own copy, validate it and separately approve deployment
or update of that source. No customer or portfolio code belongs in src/voiceagent.

Before real traffic, confirm your chosen voice permissions, host authentication/abuse protection,
gateway persistence and deployed worker duration/idle caps. Live browser/audio acceptance,
quantitative metrics, image/rollout/drain/rollback and licensing gates remain pending.

See [optional public host profiles, playback-ready greetings and deterministic ending](CLIENT_PROFILE.md) for the opt-in RTC host contract and deployment packaging boundary.
