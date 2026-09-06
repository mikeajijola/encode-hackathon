# Disposable VM definition

Created with:

```sh
gcloud compute instances create encode-fulfilment-exp-v2-20260906 \
  --project=law-needs-fcfa7 \
  --zone=europe-west2-b \
  --machine-type=e2-standard-4 \
  --network-interface=network-tier=STANDARD,stack-type=IPV4_ONLY,subnet=default \
  --maintenance-policy=MIGRATE \
  --provisioning-model=STANDARD \
  --service-account=default \
  --scopes=https://www.googleapis.com/auth/cloud-platform \
  --create-disk=auto-delete=yes,boot=yes,device-name=encode-fulfilment-exp-v2-20260906,image=projects/ubuntu-os-cloud/global/images/ubuntu-2404-noble-amd64-v20260903,mode=rw,size=80,type=pd-balanced \
  --labels=purpose=encode-research,disposable=true \
  --metadata=enable-oslogin=TRUE \
  --shielded-secure-boot \
  --shielded-vtpm \
  --shielded-integrity-monitoring
```

Created at `2026-09-05T23:48:20.498-07:00` (2026-09-06T06:48:20.498Z). Secure Boot, vTPM, and integrity monitoring were enabled. Deletion protection was disabled and the boot disk was configured for automatic deletion with the instance.
