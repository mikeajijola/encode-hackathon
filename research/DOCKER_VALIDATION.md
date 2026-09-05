# Container validation status

Validation performed on 2026-09-05:

- Static Docker contract tests pass: locked dependency install, LibreOffice Calc,
  non-root runtime, healthcheck, and `/data` → `/out` defaults.
- The host preflight exits `2` and reports `missing_soffice` explicitly. It also
  reports packages absent from the host interpreter; the container installs those
  packages from `uv.lock`.
- All repository unit and integration tests pass.

The Docker executable is unavailable in the current Termux environment, so an
actual image build and container smoke run remain unexecuted. This is a validation
blocker, not evidence that the image works. Resolve it on a Docker-capable host:

```sh
docker build --pull -t fulfilment-experiment research
docker run --rm -v "$PWD/run-input:/data:ro" -v "$PWD/run-output:/out" \
  fulfilment-experiment preflight --json
```

Do not claim container validation until both commands succeed and the second
command reports Python/package/LibreOffice versions with `"status": "ok"`.
