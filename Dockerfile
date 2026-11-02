# syntax=docker/dockerfile:1
# Public registry manifests verified 2026-11-02; see docs/CONTAINER_PINS.json.
FROM ghcr.io/astral-sh/uv:0.10.6@sha256:2f2ccd27bbf953ec7a9e3153a4563705e41c852a5e1912b438fc44d88d6cb52c AS uv
FROM python:3.12.16-slim-bookworm@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337 AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates libstdc++6 libgomp1 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app

FROM base AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_COMPILE_BYTECODE=1
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-dev --no-install-project --python /usr/local/bin/python
COPY src/ ./src/
COPY agent.py prompt.md config.example.yaml ./
# Only allowlisted public customization files enter the build context.
COPY customization/ ./customization/
# Editable source is intentional: prompt/config paths resolve from this copied project root.
RUN uv sync --locked --no-dev --python /usr/local/bin/python
COPY scripts/prepare_models.py ./scripts/prepare_models.py
# Fail the build if bundled models cannot initialize without network access.
RUN --network=none .venv/bin/python scripts/prepare_models.py

FROM base AS runtime
RUN groupadd --gid 10001 voiceagent \
    && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin voiceagent
COPY --from=build /app/.venv /app/.venv
COPY --from=build /app/src /app/src
COPY --from=build /app/agent.py /app/prompt.md /app/config.example.yaml /app/
COPY --from=build /app/customization /app/customization
ENV PATH="/app/.venv/bin:$PATH" HOME=/home/voiceagent
USER 10001:10001
EXPOSE 8081
STOPSIGNAL SIGTERM
HEALTHCHECK --interval=30s --timeout=3s --start-period=300s --retries=3 \
    CMD ["python", "-m", "voiceagent.healthcheck"]
CMD ["python", "agent.py", "start"]
