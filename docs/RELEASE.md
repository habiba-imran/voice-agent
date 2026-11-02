# Phase 9 preparation: source handoff and release acceptance

Status as of 2026-11-02: **Reusable source handoff complete; production release acceptance PENDING**. The owner confirmed a
working Cloud deployment and at least one real audible microphone conversation at revision
`1fe4b9f`. No raw live metric export/build/status log was available for this review. The deployed
revision was resolved locally during that evidence review. This is a qualitative smoke result, not a performance,
security, naturalness or full Phase 8 certification. No further live testing/deployment is approved.

Post-roadmap note: the previous .tools/release/ source candidate predates the customization and
integration extension and must not be treated as its release. The reviewed source includes the
final cleanup fixes; production acceptance retains the blockers below. See [customization](CUSTOMIZATION.md) and
[integration limits/setup](../integrations/README.md); no new deployment or public release is made.

Portfolio integration is future consuming-application work, including host authentication and any
Upstash/shared-store adapter. The current SQLite gateway requires persistent single-host storage
and must not run as a Vercel serverless function. Only the Next.js proxy may be hosted separately
on Vercel while calling the durable gateway. No portfolio or Upstash code is part of this handoff.

## Runtime and ownership contract

Copy the entire `voiceagent/` source folder; `src/voiceagent/` alone is not the runtime distribution.
Use its isolated editable environment, external prompt, example YAML and unchanged uv.lock.
Paths resolve from the copied folder, not the host CWD. Runtime/provider code contains no portfolio
or customer project integration. A host supplies authentication, short-lived room tokens, dispatch,
authorized tools and any UI/storage through the documented boundary; none is a core dependency.

Version 0.1.0 already exists in pyproject.toml and voiceagent.__version__; CHANGELOG.md now labels it
an unreleased source candidate. Do not bump versions, tag, publish a package or push automatically.
Python 3.12.10 on Windows and Agents/providers 1.8.10 are locally tested. Metadata also allows Python
3.13, but that version is unverified. The Dockerfile pins Linux Python 3.12.16; the owner reports a
working Cloud deployment, while independent build/image/native-model inspection is still pending.
Do not turn declared version ranges into additional compatibility claims.

Supported configuration and limits are in [README](../README.md), [copy integration](COPY_INTEGRATION.md),
[turn tuning](TUNING.md), [humanization](HUMANIZATION.md), [performance](PERFORMANCE.md) and
[reliability/security](RELIABILITY_SECURITY.md). Use documented fields only. Keep retries/disabled
experiments unchanged. Account quotas, scale-to-zero cold starts, warm-worker availability and
charges depend on the actual hosting plan; verify current account limits rather than promising
a free-tier capacity or latency. Voice access and commercial/redistribution permissions require
the owner's confirmation; a successful speech response alone is not a licensing audit.

## Portable source candidate

Distribute reviewed tracked source, not a recursive filesystem copy. Include README/CHANGELOG,
AGENTS, pyproject/lock/Python version, agent.py, src, prompt, example YAML and `.env.example`,
Docker/Compose/ignore files, inert deploy template, docs, scripts, tests and prepared generic evals.
Do not include `.git`, virtualenvs, caches/wheels, `.env.local`, `.env.cloud.local`, active
`livekit.toml`, local settings, provider keys, deployment identities, recordings, transcripts,
local numeric result artifacts or a previous project's binding. Git tracking alone is not a secret
guarantee: scan and review the exact candidate before copying it elsewhere.

The earlier Phase 9 preparation made an ignored `.tools/release/voiceagent-core-0.1.0-candidate.zip`
from its historical **staged index**, predating customization and the final cleanup fixes. Its separate
manifest records source revision, index content digest, per-file SHA-256, archive SHA-256 and exclusions.
It is not the current handoff, a signed/tagged release or a substitute for the finalized Git source.
No fresh archive is generated or committed for this handoff. Historical packaging evidence is in
PHASE_REPORT.md; clone the final reviewed commit for the complete current source.

After an approved clean source commit, a repeatable source export can use Git without credentials:

```powershell
git status --short
git archive --format=zip --prefix=voiceagent/ --output=.tools/release/voiceagent-source.zip HEAD
Get-FileHash .tools/release/voiceagent-source.zip -Algorithm SHA256
```

Create the ignored output directory first. `git archive HEAD` omits uncommitted changes, even
when staged. Confirm that the committed revision includes all final fixes before exporting it.
Review the archive listing/manifest and known-secret scan, extract under an unrelated empty host,
then follow setup below. Keep per-customer credentials and deployment files local to each new copy.
Never overwrite existing secret files on upgrade. A Python wheel alone omits the project's external
prompt/config contract; it is not the supported reusable distribution.

## Recipient walkthrough and verification

1. Extract/copy to an unrelated host directory, enter its voiceagent folder and run
   `uv sync --locked`. Network access or a verified platform-compatible wheelhouse/cache is
   required. Do not copy the developer's environment or Windows wheels to a Linux machine.
2. Run `uv run agent.py config` and `uv run agent.py start --help`. The config output is redacted;
   no provider is contacted. Copy `.env.example` to `.env.local` **only if the private file does
   not already exist**, and fill it locally. Never paste values into chat or commit them.
3. Select an authorized voice, set credentials per local/Cloud mode, and run
   `uv run agent.py validate --mode room`. Validation checks presence/shape/prompt loading, not
   account authentication. Cloud-injected LIVEKIT values must not be uploaded as extra secrets.
4. Edit prompt.md and the selected YAML/environment settings without changing runtime.py or
   provider code. New sessions snapshot prompts; restart workers for configuration changes.
   Starting a real worker is a separate authorized/billable action; do not run it during offline
   handoff checks. Console requires a LiveKit CLI TCP driver, not a bare console invocation.
5. Run locked lint/format/compile, `uv pip check`, SDK inspection, full pytest and indexed secret
   checks. The existing clean-copy test creates a second environment, reruns its unit suite,
   changes prompt/config and tests foreign CWD, a shadowing host import, parent env and stale
   parent LiveKit TOML isolation. No Cloud CLI target selection or real voice is inferred.

Canonical local/production startup, logs, health, updates and rollback are in
[SELF_HOST.md](SELF_HOST.md) and [DEPLOY_LIVEKIT.md](DEPLOY_LIVEKIT.md). A new copy requires its own
project/agent, private secrets, approved budget and explicit target review. No deployment is
authorized by receiving this archive. Do not reuse an existing project's binding.

## Cleanup and upgrade boundaries

- Keep caches, venvs, private env/TOML, recordings and numeric artifacts outside the export. There
  is no need to delete the owner's working files to produce a clean archive. No global caches,
  credentials or user-managed workers are removed by this preparation.
- Temporary startup URL diagnostics still exist. Confirm only the runtime scheme/host labels,
  then review their removal with regression checks. Successful speech does not establish the old
  CrashLoop trigger; preserve the secure URL fix and do not expose full environment/URL values.
- Preserve project-owned prompt/config/secrets and known-good source/image references during
  upgrades. Never overwrite `.env*`, copy deployment IDs, or reset a dirty host repository.
- Use native graceful shutdown and the documented supervisor budget. Actual active-call draining,
  disconnect cleanup, rolling update and rollback need consented tests. Do not simulate their
  success from passing offline lifecycle tests.
- No release license is present yet. Confirm source ownership and choose an explicit distribution
  license before external redistribution; review third-party notices/model/voice rights. Do not
  automatically assign a license or claim public-release readiness.

## Acceptance checklist and blockers

| Gate | Evidence now | Before final acceptance |
| --- | --- | --- |
| First Cloud voice smoke | Owner confirms running deployment and audible direct-provider microphone conversation on 1fe4b9f; at least one session | Preserve qualitative provenance; do not infer turn counts or timings |
| Source portability | Fresh-copy locked editable test and independent copied unit suite; stale parent TOML isolation included | Review candidate manifest and recipient walkthrough on intended target OS |
| Source packaging | Private source candidate plus external checksum manifest prepared by this review | Approve exact source/version; no package publication/tag/signature implied |
| Documentation/version | Existing 0.1.0, unreleased changelog, runbooks and explicit host boundary | Second-person walkthrough and license/ownership sign-off |
| Baseline conversations | Audible first conversation reported; exact turn count unavailable | Five-turn baseline and required Cloud three-turn evidence with consent |
| Live timing/cost | No reviewed samples, cache evidence, usage or spend | Quantitative protocol in PERFORMANCE.md: cold/warm counts, per-stage samples, units/outliers, actual playback boundary and account usage |
| Acoustic quality/turns | No formal interruption, hesitation/noise/overlap or humanization A/B evidence | Approved scenario matrix, listening and audio-to-stop/false-resume measurements |
| Reliability/security | Deterministic fault/concurrency/cleanup tests only | Approved real disconnect/timeout/quota, cleanup, soak/resource and admission/security checks |
| Image/self-host | Owner reports Cloud runtime success; no reviewed build/image export | Local/CI Linux build, context/layer/private-file inspection, hardened non-root startup, actual SIGTERM/drain and independent self-host room job |
| Operations | Update/log/rollback procedures prepared | Approved rolling update/in-flight-call drain and same-agent rollback evidence |
| Diagnostic cleanup | Temporary two-label URL line retained | Confirm safe runtime shape and remove diagnostic with tests before final cleanup sign-off |
| Licensing/support | Source license absent; Python 3.13 and voice redistribution rights unverified | Choose license/third-party notices, confirm voice rights and tested platform support claims |

Missing live measurements are **unavailable**, not zero. Do not average percentile summaries or
mix synthetic, cold/warm, completed/interrupted outcomes, provider timing and caller-heard timing.
Use [the live acceptance checklist](../evals/first_live_audio.md) only after fresh approval. The
owner's successful call does not authorize extra tests, recordings, Cloud changes or deployment.
The reusable source handoff is complete; final production release acceptance remains BLOCKED
by the gates above. Portfolio integration and Upstash support are separate future application work.
