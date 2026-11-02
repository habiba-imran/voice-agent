# Optional host profile and browser playback readiness

These controls are reusable and opt-in. Default user-first greeting, disabled ending tool,
direct provider chain, turn handling and experimental defaults remain unchanged. No host
identity, resume, brand, voice ID or deployment binding belongs in the reusable source.

## Public host configuration

A consuming project can prepare these two public build assets:

```text
customization/host/agent.yaml
customization/host/prompt.md
```

The optional YAML mapping overlays the selected base configuration, below private dotenv,
process environment and constructor overrides. Its `prompt_path` should point to
`customization/host/prompt.md`. Credentials are forbidden and reads are bounded to 64 KiB;
normal typed validation applies. Prompt bounds and configured-secret checks remain in force.
The existing immutable prompt snapshot reads this small prepared text at session initialization.
Extract any source documents offline in the consuming project, rather than parsing PDFs,
retrieving documents or calling a model per session/turn. Keep the stable prefix concise;
native bounded history supplies follow-up context. No retrieval service is introduced.

Example opt-in fields, with the host supplying its own exact phrases:

```yaml
prompt_path: customization/host/prompt.md
greeting:
  mode: custom
  text: Hello! How can I help?
  wait_for_playback_ready: true
ending:
  enabled: true
  detect_explicit: true
  farewell_mode: custom
  farewell: Goodbye!
  timeout_seconds: 10
```

Existing provider configuration, voice selection, tuning, secrets and deployment binding
are not replaced by this partial mapping. Environment overrides can supersede it; review
effective settings offline before rollout. A host overlay conflicting with a legacy
`runtime.greeting` is rejected rather than silently overriding it.

Host assets are Git-ignored to keep this source copy generic. The Docker allowlist includes
only these two public files and explicitly excludes unknown/nested/private host files.
The Dockerfile copies the allowlisted customization directory. **LiveKit CLI upload also
respects `.gitignore`**, so copying a profile into the reusable checkout alone is insufficient.
A host should assemble a separate reviewed public-only build context, with its own
`.gitignore` allowing the two public assets, the unchanged deny-default `.dockerignore`,
required source/build inputs and no private env/Git/deployment files. Deploy that context
to the existing approved agent only after separate authorization. Actual CLI/image/Cloud
packaging must be verified when those tools and approval are available.

## Browser readiness contract

`wait_for_playback_ready` requires a custom or dynamic opening and an RTC host implementing:

1. Unlock audio during the user's gesture; connect with the normal short-lived room token.
2. Attach/subscribe the agent's audio track and successfully await the audio element's
   `play()`. Also require the client's actual `Room.canPlaybackAudio` flag.
3. Once connected with microphone setup complete, set the local participant's own attribute
   `voiceagent.playback_ready` to the exact string `true` using the native SDK. The host-issued
   token needs only `canUpdateOwnMetadata` in addition to its existing microphone/subscription
   permissions. Arbitrary data publication, room administration and recording are unnecessary.
4. Retry a browser-blocked play only after a suitable user gesture. Do not claim readiness
   after a fixed timeout, before `play()` succeeds, or for a cancelled/stale room.

The worker binds readiness to the participant returned by `JobContext.wait_for_participant`.
Acknowledgements from other identities and all other attribute values are ignored. Registering
before binding and checking the current attributes avoids missing an early acknowledgement.
The existing startup deadline bounds the wait, and disconnect/cancellation detaches listeners
and joins helper tasks. No attribute text becomes an LLM instruction.

Input is held through preparation; native `session.say` then schedules the opening and normal
audio input resumes. A 300 ms silent PCM probe supplied directly to `session.say` permits
browsers to receive media before their `play()` promise resolves, avoiding a readiness/media
deadlock. This is in-memory zero-initialized audio, with no TTS/LLM request, file or recording.
The probe is omitted from chat history. Static custom speech uses the same TTS client/voice as
normal conversation. No prerecorded asset is generated or persisted by this feature.

The per-session controller latches the actual greeting once, before generation. Reconnects
and repeated readiness events cannot replay it. Audio-device audibility and mobile autoplay
still need real-device acceptance; an offline acknowledgement test cannot prove them.

## Deterministic ending before model generation

`ending.detect_explicit` requires the ending feature enabled and `latency.preemptive_llm=false`.
The whole-utterance guard accepts common explicit exits and short combinations of thanks,
okay and goodbye, including contractions with curly apostrophes. It rejects unrelated words,
quotes, negation, questions and trailing requests. It is a deliberately conservative English
grammar, not a universal semantic classifier. A synchronous trusted host ending policy can
extend it; only literal `True` authorizes ending and exceptions fail closed.

The real STT-completed-turn hook checks the original bounded input before any normal Groq
generation. A match calls the existing idempotent SessionControl, then raises native
`StopResponse` to suppress a normal reply. For zero farewell-model calls, use `farewell_mode:
custom` (or `none`). Generated farewell remains an explicit, separate host choice. Programmatic
`session.generate_reply(user_input=...)` is not an STT turn and intentionally does not run this
hook; such hosts should use `agent.end_session()` for deterministic application termination.

The controller awaits the farewell speech handle's `wait_for_playout`, then stops the native
session. Timeout/failure still closes within the configured bound; new user activity or genuine
barge-in cancels a pending farewell and preserves the conversation. Repeated requests share one
future and do not repeat speech/shutdown. The existing guarded tool remains available for the
normal model path, with its original confirmation, native tool-context playout and stale-reply
suppression. No extra model classifier or provider path is added.

The consuming app owns room deletion and its idempotent admission/resource release. It should
handle agent departure/disconnect, keep hard-duration/heartbeat/signed-cleanup fallbacks, and
not release uncertain resources until its existing cleanup policy confirms them. Worker room
deletion stays disabled. Server playout completion is not proof of device speaker output.

## Offline verification and rollout limits

`tests/unit/test_voice_experience.py` covers exact exit positives/negatives, actual native
turn-hook zero-model ending, farewell playout/timeout/barge-in, greeting/probe zero-model and
zero-probe-TTS paths, readiness identity/races/leak cleanup, entrypoint sequencing/timeout,
host merge/validation, image exclusions and stable prompt/follow-up request contexts.
Provider responses are scripted; no real-model grounding, microphone or audible quality is
claimed. The full suite still verifies an independent clean-copy locked install/unit rerun.

Run the existing locked sync, Ruff, compile and pytest gates in AGENTS.md. Host/browser tests
belong to the consuming project, not this reusable worker. No provider requests, recordings,
credential updates, image rollout or Cloud commands are authorized by these offline tests.

Official references checked against the installed Agents 1.8.10/RTC APIs:

- [Turn hook and StopResponse](https://docs.livekit.io/agents/logic/nodes/)
- [Fixed speech and native playout](https://docs.livekit.io/agents/multimodality/audio/)
- [Token own-metadata permission](https://docs.livekit.io/home/server/generating-tokens)
- [Build context exclusions](https://docs.livekit.io/deploy/agents/builds/)
