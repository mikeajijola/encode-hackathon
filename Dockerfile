FROM ghcr.io/astral-sh/uv:0.8.15 AS uv

FROM python:3.13-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/app/.venv/bin:$PATH \
    PYTHONPATH=/app/research \
    HOME=/home/runner

RUN apt-get update \
    && apt-get install --yes --no-install-recommends libreoffice-calc libreoffice-core \
    && rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
COPY research/pyproject.toml research/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY research ./research
RUN groupadd --system runner \
    && useradd --system --gid runner --create-home runner \
    && mkdir -p /data /out \
    && chown runner:runner /out

WORKDIR /app/research
USER runner

HEALTHCHECK --interval=30s --timeout=15s --retries=3 \
    CMD ["python", "-m", "container_preflight", "preflight", "--json"]

ENTRYPOINT ["python", "-m", "container_preflight"]
CMD ["run", "--manifest", "/data/manifest.json", "--out-dir", "/out"]
