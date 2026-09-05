# Container validation status

Validation performed on 2026-09-05:

- Static Docker contract tests pass against the sole repository-root `Dockerfile`:
  locked dependency install, LibreOffice Calc, non-root runtime, healthcheck,
  `/data` → `/out` defaults, and no second divergent Dockerfile.
- The original host preflight reported `missing_soffice`; the Termux-specific
  installation below now supplies a verified recalculation engine.
- All repository unit and integration tests pass.

Docker CLI 29.1.3 and Buildx were installed inside Ubuntu proot and exposed through
`/data/data/com.termux/files/usr/bin/docker`. A VFS-backed daemon reached its API,
but the canonical image build failed while registering a downloaded layer:

```text
failed to register layer: open .../image/vfs/layerdb/tmp/write-set-.../diff:
no such file or directory
```

This is an Android/PRoot filesystem incompatibility. The installed CLI must not be
mistaken for a functioning build environment. An actual canonical image build and
container smoke run remain validation blockers. Resolve them on a Docker-capable host:

```sh
docker build --pull -t fulfilment-experiment -f Dockerfile .
docker run --rm --mount type=bind,src="$PWD/run-input",dst=/data,readonly \
  --mount type=bind,src="$PWD/run-output",dst=/out \
  fulfilment-experiment preflight --json
```

Do not claim container validation until both commands succeed and the second
command reports Python/package/LibreOffice versions with `"status": "ok"`.

## Termux prerequisite installation

LibreOffice Calc 26.2.5.2 was installed inside the existing Ubuntu 26.04 proot and
exposed through `/data/data/com.termux/files/usr/bin/soffice`. This is a local
environment wrapper, not a repository dependency. Two execution checks pass:

- a workbook containing `=SUM(A1:A2)` recalculated to cached value `5`;
- the official evaluator recalculated and graded task `31011`'s initial workbook
  without an infrastructure error (the expected task score was zero).

Termux `udocker` 1.3.17 with udockertools 1.2.11 was also installed. An ARM64
`hello-world:latest` image pulled and executed successfully. This proves rootless
OCI image execution, but **does not satisfy the registered Docker build gate**: udocker
cannot build the repository Dockerfile and is not a Docker daemon. It must not be
recorded as the pinned canonical image or used to claim the Docker smoke passed.

The experiment now defaults to direct Gemini. `GEMINI_API_KEY` is account-scoped
secret material and cannot be installed or generated locally. It remains required
for live model runs; OpenRouter is retained as an optional provider.
