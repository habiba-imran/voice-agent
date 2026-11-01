# Copying the foundation

Copy this entire directory under any host repository, for example `host/voiceagent/`.
Do not copy .venv/, .env.local, recordings, caches, livekit.toml, or deployment IDs.
Copy the tracked source files, .env.example, prompt.md, example YAML, pyproject.toml, and uv.lock
once its generation is recorded as passed in PHASE_REPORT.md. Do not copy only src/voiceagent/.

Run `uv sync --locked` inside the copied directory. This installs the editable src package in
that copy's virtual environment. A host's Python environment is not a substitute for this setup.
Copy .env.example to .env.local only if that file does not already exist; fill it locally.
Never overwrite an existing secret file as part of an upgrade.

`uv run agent.py config` prints redacted effective values. `uv run agent.py validate --mode room`
checks LiveKit/provider credentials, voice UUID, and the prompt without contacting a provider.
For provider-only console validation use `--mode console`. This does not establish provider access.

Paths resolve from this directory even when the virtual environment's Python runs agent.py from
another working directory. An explicit constructor config_path wins over VOICEAGENT_CONFIG_PATH;
relative custom prompt/config paths also resolve from here, not from their enclosing YAML file.

Edit prompt.md without changing the provider/orchestration code. Each new session takes its own
immutable prompt snapshot; existing sessions retain the old text. Configuration is a startup
snapshot, so restart the worker after changing config. The baseline history policy is 24 recent
messages, to be enforced by the Phase 2 LiveKit integration rather than a separate LLM summarizer.

## Host extension boundary

The host may explicitly pass an async hook to the runtime once Phase 2 is implemented.
The setup contract is already testable independently:

```python
from voiceagent.hooks import SessionExtensions, prepare_extensions

async def setup():
    return SessionExtensions(metadata={"topic": "general assistance"})

# Await during session setup only. With no hook, the result is empty and no I/O occurs.
extensions = await prepare_extensions(setup, deadline_seconds=2)
```

The result has a tools tuple and bounded string metadata. Tools must be supported LiveKit tools;
runtime validation and startup fallback remain a Phase 2 task. HookError contains no payload or
exception details; the runtime should log a fixed warning and continue with no extensions.
Cancellation propagates. Hooks are never discovered from YAML, imported from arbitrary strings,
or called on every token. Registered tools own their authorization, side effects and cancellation
semantics. Do not put credentials or personal data in session metadata.

The host supplies its own authentication, short-lived participant tokens, frontend if any, and
application-specific tools/storage. None of those are dependencies of this folder's configuration
and prompt system. No host app is implemented here.

## Deployment boundary

One copy belongs to one deployment context. Provision separate provider secrets, LiveKit project,
agent deployment ID, named dispatch policy, voice permissions, and budget for each consuming app.
Do not copy another app's deployment identity. Cloud worker deployment and self-hosted Docker
execution are later phase gates; see PHASE_REPORT.md before treating the template as runnable.
