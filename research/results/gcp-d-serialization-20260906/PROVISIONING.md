# Disposable canonical environment

Project: law-needs-fcfa7. Zone: europe-west2-b (region europe-west2).
VM: encode-serialization-20260906. Machine: e2-standard-4, 4 vCPU / 16 GB RAM.
Boot disk: 80 GB pd-balanced, automatic deletion enabled.
Image: ubuntu-2404-noble-amd64-v20260906 from ubuntu-os-cloud (Ubuntu 24.04 LTS).

Creation command:

```sh
gcloud compute instances create encode-serialization-20260906 \
  --project=law-needs-fcfa7 --zone=europe-west2-b \
  --machine-type=e2-standard-4 \
  --image=ubuntu-2404-noble-amd64-v20260906 --image-project=ubuntu-os-cloud \
  --boot-disk-size=80GB --boot-disk-type=pd-balanced --boot-disk-auto-delete \
  --labels=purpose=encode-serialization \
  --metadata-from-file=startup-script=research/protocol/serialization_startup.sh
```

Execution source: 38c262b, checked out detached on the VM. The canonical image is
built using the repository Dockerfile. Exact image inspection, runtime versions,
manifest, timestamps, test log and resource samples are in the retained archive.
Host Docker reports 29.1.3. The final canonical test suite passes 178 tests plus
29 subtests. Tests run in a disposable container with pytest installed into its
runtime virtual environment; the experiment image is not modified by testing.
Repository-layout fixtures and the 400 public initial workbooks are mounted only
for existing structural tests. No held-out outcomes are evaluated or inspected.

The fulfilment container receives only 20 initial workbooks and public metadata,
mounted read-only at /data, and a writable /out. Offline labels, retained outcomes,
golden workbooks, and rendered comparisons are not mounted. research/results is
excluded from the build context to keep offline evidence out of image layers.
The separate scorer receives only the development golden set after termination.

Gemini credentials enter over SSH stdin with terminal echo disabled, then pass
through an environment variable to Docker. No key is written to a file or image.
The provider metadata probe verifies gemini-3.7-flash version 3.7-flash-08-2026.

Operational deviations and failed trials are retained. Default HOME was
root-owned; arbitrary host UID plus a temporary HOME also failed LibreOffice
profile creation. The valid run retains the image's UID/GID 999 and uses writable
tmpfs mounts for /home/runner and /tmp. This configuration passes an actual broker
recalculation probe: A1's cached result becomes 4 while B1 and target style remain
preserved. A short default-home model trial was stopped on that independently
observed infrastructure failure and is excluded from the controlled comparison.
Its raw evidence and resource consumption remain available for audit.

The parent manifest does not fully record its runtime UID/profile permissions.
The paired rerun therefore supports an operational comparison, while the frozen
transition replays isolate the serializer intervention causally. Do not attribute
all stochastic task-level performance movement solely to the firewall.
