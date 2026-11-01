# Execution contract

Read the complete ../VOICEAGENT_IMPLEMENTATION_PLAN.md when present, and docs/PHASE_REPORT.md
before work. Follow phases in order and record exact commands, exit codes, and blockers.
Use current official documentation and verify installed signatures before adding SDK options.
Use LiveKit streaming, turn-taking, and cancellation; do not add classifiers or business logic.
Run uv sync --locked, uv run ruff check ., uv run python -m compileall -q src agent.py,
and uv run pytest -q after each phase that changes code.
Mock checks do not prove provider access, audible quality, or caller-heard latency.
Ask before consuming provider credits, persisting audio, or deploying. Never ask for secrets in chat.
Keep secrets, recordings, transcripts, and deployment IDs outside source and build contexts.
No frontend, RAG, package publication, or project-specific integration. Keep experiments disabled
until their baseline and listening gates pass. Document incomplete phases honestly.
