# Disposable completion-calibration VM

- Project: `law-needs-fcfa7`
- Region/zone: `europe-west2` / `europe-west2-b`
- VM: `encode-d-calibration-20260906`
- Machine: `e2-standard-4` (4 vCPU, 16 GB RAM)
- Image family: `ubuntu-2404-lts-amd64`
- Boot disk: 80 GB `pd-balanced`, auto-delete enabled
- Created: `2026-09-06T08:43:28.676Z`
- Canonical repository commit: `d50d93fee405c6e816af12ab564e53b62ff13c39`
- Focused policy commit: `f9acdcf4d96ecb858652d50b505eeda6912bb66b`
- Canonical image ID: `sha256:6b67fb026647ea6bbcc3f812f809b6ba68fde318e1d8e7421aad4b5d55bf2645`
- Docker: 29.1.3
- Python: 3.13.15
- LibreOffice: 7.4.7.2 40(Build:2)
- Provider/model/version: direct Gemini API / `gemini-3.7-flash` / `3.7-flash-08-2026`
- Canonical run: `2026-09-06T09:11:16Z` to `2026-09-06T09:19:31Z`

Creation command:

```sh
gcloud compute instances create encode-d-calibration-20260906 \
  --project=law-needs-fcfa7 --zone=europe-west2-b \
  --machine-type=e2-standard-4 \
  --network-interface=network-tier=STANDARD,stack-type=IPV4_ONLY,subnet=default \
  --maintenance-policy=MIGRATE --provisioning-model=STANDARD \
  --service-account=default --scopes=https://www.googleapis.com/auth/cloud-platform \
  --create-disk=auto-delete=yes,boot=yes,device-name=encode-d-calibration-20260906,image-family=ubuntu-2404-lts-amd64,image-project=ubuntu-os-cloud,mode=rw,size=80,type=pd-balanced \
  --labels=purpose=encode-research,disposable=true,experiment=d-calibration \
  --metadata=enable-oslogin=TRUE --shielded-secure-boot --shielded-vtpm \
  --shielded-integrity-monitoring
```

The benchmark dataset was mounted read-only during fulfilment; a separate scorer
container received reference artifacts only after all tasks terminated. The key
was entered with terminal echo disabled, passed by environment-variable name,
unset after the run, and the retained tree passed a credential-value scan.

Canonical tests: 158 passed, 24 subtests passed. Sixteen broker evidence chains
were present and verified; four contract-compilation failures occurred before a
broker evidence chain was created. The initial output-permission preflight failure
and two invalid policy-translation pilots are retained in the evidence archive.
