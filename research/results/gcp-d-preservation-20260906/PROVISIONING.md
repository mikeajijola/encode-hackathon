# Disposable preservation experiment VM

- Project: `law-needs-fcfa7`
- Region/zone: `europe-west2` / `europe-west2-b`
- VM: `encode-preservation-20260906`
- Machine: `e2-standard-4` (4 vCPU, 16 GB RAM)
- Image: Ubuntu 24.04 LTS amd64 (`ubuntu-2404-lts-amd64`)
- Boot disk: 80 GB `pd-balanced`, auto-delete enabled
- Repository commit: `a63b5b10ef8eb5bf30a501a2d051faf9a6c0e94c`
- Container image ID: `sha256:200cbff57b50387c17e6c7d589a8ff05453411299ba5cd4b7f3cd63bb49f1af1`
- Docker: 29.1.3
- Runtime: Python 3.13.15; LibreOffice 7.4.7.2
- Provider/model/version: direct Gemini API / `gemini-3.7-flash` / `3.7-flash-08-2026`

Creation used the same command shape as the prior calibration VM, changing only
the instance name and experiment label. The exact instance description is in
`vm_description.json`. The key entered over SSH standard input and existed only
as a runtime environment variable. The retained corpus has zero credential
literal matches.

The fulfilment container mounted the staged blind dataset read-only and the
result directory read/write. The blind dataset contained only public metadata,
prompts, and initial artifacts. The full dataset was first mounted in a separate
scorer container after all runtime decisions terminated.
