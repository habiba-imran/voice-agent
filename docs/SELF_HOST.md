# Local execution and Docker operations

Phase 8 prepares deployment artifacts. Docker and LiveKit CLI are unavailable on the verification
machine. The owner reports a working Cloud deployment and audible microphone conversation at
revision 1fe4b9f; independent image inspection, Linux self-hosting and OS signal/drain verification
remain pending. See [phase evidence](PHASE_REPORT.md) for commands actually executed. All commands below
run from the copied `voiceagent/` folder; each copy has its own private configuration and deployment.

## Local setup

Use Python 3.12 and uv 0.10.6. Run `uv sync --locked`, populate the ignored `.env.local` from
`.env.example` locally, select an authorized `VOICEAGENT_TTS__VOICE_ID`, then run:

```powershell
uv run agent.py validate --mode room
uv run agent.py start --help
```

Validation checks configuration, required credential presence and prompt loading offline. It does
not authenticate accounts or check quota/voice access. Process environment overrides project
`.env.local`, then YAML and typed defaults. Parent env files are never searched. Use
`VOICEAGENT_CONFIG_PATH` and `VOICEAGENT_PROMPT_PATH` for reviewed custom files; YAML cannot contain
credentials. Restart workers after settings changes. New sessions load a prompt snapshot.

After approval for provider and LiveKit usage, `uv run agent.py start` is the canonical production
worker command. `uv run agent.py dev` uses the installed SDK's development mode; it has no hot reload
and different drain/health-port behavior. Console requires a LiveKit CLI TCP driver and verified
`--connect-addr`; a bare `uv run agent.py console` is not the local voice test recipe. No unverified
`lk agent console/dev/start` alternatives are prescribed. The first five-turn local acceptance
test follows [the live-audio checklist](../evals/first_live_audio.md).

## Image build and inspection

The Dockerfile pins the Python 3.12.16 Debian Bookworm and uv 0.10.6 image manifests by digest;
[the pin record](CONTAINER_PINS.json) records actual public-registry manifest checks. This does not
prove image-layer contents. Host tests use Python 3.12.10; Linux/Python 3.12.16 compatibility remains
an image-build gate. Debian security packages are fetched at build time; the whole image is not
claimed bit-for-bit reproducible. Review vulnerability reports before a release; no CVE scan was run.

The builder installs `uv.lock` with `--locked --no-dev`. The final image has the editable package,
its source, prompt and example config at `/app`, preserving the copyable project-root path contract.
It includes CA certificates and native C++/OpenMP libraries, excludes uv and development tools,
and runs as UID/GID 10001. Python is launched directly with an exec-form command, without a shell.

The locked wheels bundle Silero and local `v1-mini` models. A `RUN --network=none` build step
initializes them without credentials. Do not use the SDK's all-plugin `download-files` command:
the installed legacy turn-detector plugin may fetch unrelated Hugging Face models. No extra
provider clients or emotion/classifier calls are introduced. The image build must prove the Linux
model/native-library path; successful Windows initialization alone is insufficient.

When Docker with Linux BuildKit is available, the following build/inspection commands use no
provider keys and must succeed before attempting runtime acceptance:

```powershell
docker version
docker compose version
docker build --platform linux/amd64 --target runtime -t voiceagent-core:local .
docker image inspect voiceagent-core:local --format '{{.Id}} {{.Config.User}} {{json .Config.Cmd}}'
docker image inspect voiceagent-core:local --format '{{json .Config.Healthcheck}}'
docker history --no-trunc voiceagent-core:local
docker run --rm --network none voiceagent-core:local python agent.py start --help
docker run --rm --network none voiceagent-core:local python -c "from livekit.plugins import silero; from livekit.local_inference import init_eot; silero.VAD.load(force_cpu=True); init_eot()"
```

Review the sent build context and every stage/layer, including an exported filesystem, for `.env*`,
deployment bindings, credentials, recordings, transcripts, caches and private files. No secret
build arguments, secret ENV values or root-directory COPY are permitted. `.dockerignore` denies
everything except the explicit build inputs; deterministic tests exercise that glob policy and
indexed-source checks search known credential values. These checks cannot certify unbuilt layers
or detect all unknown secrets. If a private file is added to an allowed Python source file or
prompt, exclusion rules cannot protect it: review source and run the secret check before builds.
Never print `docker inspect` of a running container's environment; it contains runtime secrets.

## Runtime configuration and supervision

Keep credentials outside the image. Supply project-owned `LIVEKIT_URL`, `LIVEKIT_API_KEY`,
`LIVEKIT_API_SECRET`, three provider keys and the voice selection at runtime. Never commit the
private file. For Docker/Compose, use UTF-8 `KEY=value` lines with literal **unquoted** values and
no BOM. Existing dotenv files may contain quotes/BOM: prepare a dedicated ignored runtime env file
locally when necessary, without pasting its contents into chat. Compose requires >=2.30 for
`env_file.format: raw`, preserving `$` and other literal key characters. Avoid `docker compose
config` output because resolved configuration may expose secrets.

Only after usage approval and a reviewed target project:

```powershell
# Optional: choose a dedicated ignored literal env file instead of .env.local.
$env:VOICEAGENT_ENV_FILE = '.env.container.local'
docker compose up --build -d
docker compose ps
docker compose logs --tail 100 voiceagent
docker compose exec -T voiceagent python -m voiceagent.healthcheck
docker compose stop
docker compose down
```

Compose adds an init process, read-only root filesystem, writable bounded tmpfs paths, dropped
capabilities, no-new-privileges and bounded log rotation. No port or Docker socket is published.
These settings still need a real container check. No automatic restart loop is configured;
an operator should distinguish permanent credential/configuration errors from recoverable faults
before restarting. Use the same image with `python agent.py start` on an always-on container host;
the worker makes outbound connections and requires no application frontend/proxy here. If using
`docker run`, supply `--init --env-file <private-file> --stop-timeout 3720` and equivalent hardening.

The SDK health endpoint is `GET /` on port 8081 in production. The image probes loopback and
requires HTTP 200 with `OK`. This tests worker connection/inference health, not STT/LLM/TTS access
or audible readiness. The SDK returns 503 before first registration, on connection failure, or
after its 30-second reconnect grace. Explicit unregistered test workers return liveness instead.
Health can remain 200 while draining; use SDK admission/worker status for capacity. Keep health and
`/worker` metadata private. `EXPOSE` alone does not publish a port. The probe allows 300 seconds
for startup, aligning with Cloud's documented readiness window; actual cold-start time is unmeasured.

Production SIGTERM/SIGINT is handled by the SDK: stop admitting jobs, drain, close resources and
exit. Do not implement parallel signal handlers or use SIGKILL for normal updates. Default native
worker drain is 3600 seconds; the configured per-job shutdown budget is 60 seconds, covering the
existing 55-second cooperative cleanup bound. Compose's 62-minute grace includes both and margin.
If cleanup settings change, recalculate the supervisor grace. A second signal or grace exhaustion
can force termination. Tests exercise native drain waiting/HTTP cleanup with fake registration and
job state; OS-level delivery, child-process teardown and active real calls remain unverified.

LiveKit registration retains its native bounded reconnection policy (default max_retry=16).
Provider request retries remain zero. Do not infer provider recovery from SDK worker reconnection.
Review [reliability limits](RELIABILITY_SECURITY.md), including cooperative cancellation boundaries.
Measure memory, CPU, sockets, maximum concurrent jobs and actual cleanup before choosing resource
limits. No production capacity number is inferred from three synthetic sessions. Always-on hosting
avoids scale-to-zero cold starts but has ongoing cost; no external host integration is implemented.

## Updates, logs and rollback

Keep immutable image digests and reviewed source revisions for each release. Run the full offline
suite, secret checks, build/layer inspection and approved staging/live gates before replacing a
worker. Preserve in-flight calls with SIGTERM/graceful drain, and confirm the replacement registers
and accepts explicitly dispatched jobs. A healthy port and successful process launch do not prove
voice acceptance. Provider keys and transcripts must stay out of logs; existing runtime filters
omit sensitive payloads, but do not treat logs as a PII-free archive without operational review.

For self-host rollback, select the prior reviewed image digest/configuration, drain the failed
version and start that known image with runtime secrets. Do not overwrite local work or reuse a
different project's deployment identity. Dependency/base-image updates require reviewed pins and
fresh Linux builds; never remove `--locked` to get around an install failure. Actual restart,
update, drain and rollback evidence remains BLOCKED on Docker and approved LiveKit usage.
