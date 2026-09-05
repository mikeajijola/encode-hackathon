# Container validation status

Validation performed on 2026-09-05:

- Static Docker contract tests pass against the sole repository-root `Dockerfile`:
  locked dependency install, LibreOffice Calc, non-root runtime, healthcheck,
  `/data` → `/out` defaults, and no second divergent Dockerfile.
- The host preflight exits `2` and reports `missing_soffice` explicitly. It also
  reports packages absent from the host interpreter; the container installs those
  packages from `uv.lock`.
- All repository unit and integration tests pass.

The Docker executable is unavailable in the current Termux environment, so an
actual image build and container smoke run remain unexecuted. This is a validation
blocker, not evidence that the image works. Resolve it on a Docker-capable host:

```sh
docker build --pull -t fulfilment-experiment -f Dockerfile .
docker run --rm --mount type=bind,src="$PWD/run-input",dst=/data,readonly \
  --mount type=bind,src="$PWD/run-output",dst=/out \
  fulfilment-experiment preflight --json
```

Do not claim container validation until both commands succeed and the second
command reports Python/package/LibreOffice versions with `"status": "ok"`.
