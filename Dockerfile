FROM python:3.11-slim
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.8.15 /uv /uvx /bin/
COPY research/pyproject.toml research/uv.lock /app/
RUN uv sync --frozen --no-install-project
COPY research /app/research
ENV PATH=/app/.venv/bin:$PATH PYTHONPATH=/app/research PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "-m", "experiment.cli"]
CMD ["--manifest", "/data/run.json", "--out-dir", "/out"]
