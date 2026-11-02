# LiveKit Cloud deployment runbook

Prepared against official docs on 2026-11-02. The owner confirms a successful Cloud deployment and
at least one audible microphone conversation at revision 1fe4b9f. This review did not deploy,
authenticate or make billable requests. Live metrics/turn counts and raw build/status logs were
not supplied. Local Docker/CLI are unavailable; full Phase 8 operational acceptance remains pending.
See [release acceptance](RELEASE.md) and [container operations](SELF_HOST.md)
for the shared Dockerfile, environment contract, model preparation, health and drain limits.

Startup URL investigation: the application now accepts the installed SDK's secure https alias
and loopback-only http alias, preserving the remote-TLS and no-userinfo/query/fragment rules.
Temporarily, `start`/`dev` emits only `livekit_url_scheme` and `livekit_url_host_category` on stderr
before validation. Read those labels after an explicitly authorized update of the existing agent;
do not export its full environment/URL or create a replacement deployment to diagnose it. The
project-list URL alone cannot confirm the injected runtime value. The owner now reports successful
startup and voice; runtime URL labels and the original CrashLoop trigger remain unobserved here.
Remove the temporary diagnostic after that safe runtime confirmation and regression review.

## Review before authorization

Each copied folder must target its own approved LiveKit project/agent. The reusable template is
`deploy/livekit.toml.example`, with placeholders only. Actual `livekit.toml` and project-specific
overrides are gitignored and excluded from Docker contexts. Never copy a previous project's binding
or credentials. The template uses only the documented `[project].subdomain` and `[agent].id` fields;
it is not an active binding or a substitute for CLI-generated configuration.

Complete the offline checks and the Docker build/layer/non-root/model tests in SELF_HOST.md first.
Select an authorized Cartesia voice/language and obtain approval for the target, provider/Cloud
budget and any recording separately. Current defaults retain explicit dispatch to agent name
`voiceagent`; the host must use that name in an authorized job dispatch. Do not enable SessionHost,
recording, debug capture or humanization experiments to make deployment pass.

Prepare a private ignored Cloud secrets file locally. Include `DEEPGRAM_API_KEY`, `GROQ_API_KEY`,
`CARTESIA_API_KEY`, `VOICEAGENT_TTS__VOICE_ID` and reviewed nonsecret settings overrides as needed.
**Do not upload `.env.local` wholesale.** LiveKit Cloud injects `LIVEKIT_URL`, `LIVEKIT_API_KEY` and
`LIVEKIT_API_SECRET`; the official workflow forbids setting/overwriting them as agent secrets.
Never place provider credentials in the Dockerfile, TOML, build args, YAML, prompt or shell history.
Do not send secret values to chat. Use the current CLI's secrets-file parser requirements locally.

## Commands after explicit deployment approval

Install the official CLI using a reviewed installation method outside this task. Check each current
subcommand's `--help` before executing it. Authentication opens an account workflow; none of these
account/deployment commands has been executed here. Example project names/paths are placeholders:

```powershell
lk --version
lk cloud auth --help
lk cloud auth
lk project list
lk project set-default --help
lk project set-default '<approved-project-name>'
lk agent create --help
lk agent create --secrets-file '.env.cloud.local'
```

`lk agent create` **registers, builds and deploys immediately**. It is not a harmless configuration
generator. Run it only from the reviewed copy after approval; retain the generated ignored
`livekit.toml` privately. Review the resulting project/agent target locally before any subsequent
command. For an existing approved agent, use the current `lk agent config --help` workflow to
obtain its binding rather than inventing an agent ID or reusing a template placeholder.

The service builds this folder's Dockerfile. Cloud supplies runtime secrets; the build must never
require them. CLI defaults and Dockerfile/build-context behavior still require actual CLI review
and build evidence. Cloud uses Linux amd64; the public pinned manifests include that architecture.
Do not assume a successful upload proves native model initialization or room connectivity.

## Acceptance and operations

After an approved deployment, verify the intended target/version and startup without printing
runtime environment values:

```powershell
lk agent status --help
lk agent status
lk agent logs --help
lk agent logs
lk agent secrets --help
lk agent secrets
```

The documented health deadline is five minutes. Confirm native worker registration and matching
explicit dispatch, then run at least three successful real voice turns for Cloud acceptance and
the five-turn local/onboarding and broader acoustic gates in the plan. Check interruptions,
disconnect cleanup and idle/maximum-session handling with consent. Distinguish process/registration
health from caller-heard speech, quota and voice authorization. Capture numeric timing using the
existing instrumentation; do not invent cold/warm latency or naturalness scores. Keep all untested
Phases 2–7 live gates BLOCKED even if deployment itself becomes healthy.

Logs may include operational SDK metadata. Existing filters protect configured credentials and
omit session payloads, but access/retention policies remain the operator's responsibility. Do not
export transcripts/audio without separate recording/retention approval. Verify cost/account usage
against the approved budget; automatic prompt caching is not a free-usage guarantee.

For a reviewed source update, check `lk agent deploy --help`, then `lk agent deploy` after approval.
For secrets changes, check `lk agent update-secrets --help`, then use
`lk agent update-secrets --secrets-file '.env.cloud.local'`. The documented operation merges secrets
and triggers a rolling restart. Avoid `--overwrite` unless intentionally replacing the complete
secret set with explicit authorization. Do not set the Cloud-injected LIVEKIT variables.

Cloud rolling updates allow existing sessions to drain for up to one hour. Observe new-job
admission and a consented in-flight call during a safe update; native SDK shutdown and the session
cleanup budget still apply, and a platform deadline can force termination. Confirm status/version,
logs, approved voice turns and no stale jobs/resources after the update. No rollout, secret update
or draining call has been tested in Cloud.

## Rollback and project independence

Keep known-good source revisions, image/build identifiers and nonsecret settings for the same
project. LiveKit's managed rollback is a paid-plan feature: check `lk agent rollback --help`,
review the intended version/target, and execute only with approval. On plans without that feature,
use a clean copy of the reviewed previous source revision and rebuild/redeploy it to the same
approved agent; this is not instant image rollback. Preserve current uncommitted work and never
reset the working tree as an operational shortcut. Secret compatibility must be checked separately.

Treat rollback as a deployment: verify target, new version, registration, dispatch, active-call
drain and successful voice turns. If a release leaks a credential, stop further rollout and follow
the owner's rotation process; removing a file from a later image does not remove earlier layers.
Account actions, costs, actual rollout and rollback remain unverified and require authorization.

## Official references

- [Cloud quickstart](https://docs.livekit.io/deploy/agents/quickstart/)
- [Builds and Dockerfiles](https://docs.livekit.io/deploy/agents/builds/)
- [Secret injection and updates](https://docs.livekit.io/deploy/agents/secrets/)
- [Deployments, draining and rollback](https://docs.livekit.io/deploy/agents/managing-deployments/)
- [Agent server options and health](https://docs.livekit.io/agents/server/options/)
- [uv Docker integration](https://docs.astral.sh/uv/guides/integration/docker/)
- [Compose env-file formats](https://docs.docker.com/reference/compose-file/services/#env_file)
