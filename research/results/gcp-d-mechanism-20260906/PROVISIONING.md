# Disposable mechanism-validation VM

- Project: `law-needs-fcfa7`
- Region/zone: `europe-west2` / `europe-west2-b`
- VM: `encode-d-mechanism-20260906`
- Machine: `e2-standard-4` (4 vCPU, 16 GB RAM)
- Image: `projects/ubuntu-os-cloud/global/images/ubuntu-2404-noble-amd64-v20260903`
- Boot disk: 80 GB `pd-balanced`, auto-delete enabled
- Created: `2026-09-06T07:46:54.519Z`
- Repository commit: `5c169b1b1ba8b2bd15e94eda36984d232e6a5b96`
- Canonical image ID: `sha256:ad0517ca92d670f0f4b7b53f7f41691b1cbd0d6ae4a74b1525d9b9c442de774a`
- Docker: `29.1.3`
- Python: `3.13.15`
- LibreOffice: `7.4.7.2 40(Build:2)`
- Provider/model/version: direct Gemini API / `gemini-3.7-flash` / `3.7-flash-08-2026`

Creation command:

```sh
gcloud compute instances create encode-d-mechanism-20260906 \
  --project=law-needs-fcfa7 \
  --zone=europe-west2-b \
  --machine-type=e2-standard-4 \
  --network-interface=network-tier=STANDARD,stack-type=IPV4_ONLY,subnet=default \
  --maintenance-policy=MIGRATE \
  --provisioning-model=STANDARD \
  --service-account=default \
  --scopes=https://www.googleapis.com/auth/cloud-platform \
  --create-disk=auto-delete=yes,boot=yes,device-name=encode-d-mechanism-20260906,image-family=ubuntu-2404-lts-amd64,image-project=ubuntu-os-cloud,mode=rw,size=80,type=pd-balanced \
  --labels=purpose=encode-research,disposable=true,experiment=d-mechanism \
  --metadata=enable-oslogin=TRUE \
  --shielded-secure-boot \
  --shielded-vtpm \
  --shielded-integrity-monitoring
```

The Gemini credential was read with terminal echo disabled, exported only in the active remote process, passed to Docker by environment name, and unset after execution. Secret scanning passed. The fulfilment container mounted the staged development dataset read-only; that staging tree contained only public metadata, prompts, and initial workbooks. Reference workbooks were mounted only into fresh post-termination scorer containers.
