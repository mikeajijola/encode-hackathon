"""Runtime-secret connectivity probe, without task or benchmark information."""
import json
import os
from pathlib import Path
import urllib.request

model = "gemini-3.7-flash"
version = "3.7-flash-08-2026"
request = urllib.request.Request(
    f"https://generativelanguage.googleapis.com/v1beta/models/{model}",
    headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]})
with urllib.request.urlopen(request, timeout=120) as response:
    metadata = json.loads(response.read())
reported_version = metadata.get("version")
report = {"requested_model": model, "pinned_version": version,
          "reported_name": metadata.get("name"), "reported_version": reported_version,
          "version_verified": reported_version == version}
Path("/out/connectivity.json").write_text(json.dumps(report, indent=2) + "\n")
if not report["version_verified"]:
    raise SystemExit("provider model version does not match frozen protocol")
from backends.spreadsheetbench import GeminiProvider
reply = GeminiProvider().complete("Reply OK", model=model, temperature=0)
report.update({"generation_succeeded": bool(reply.text), "input_tokens": reply.input_tokens,
               "output_tokens": reply.output_tokens})
Path("/out/connectivity.json").write_text(json.dumps(report, indent=2) + "\n")
print("Connectivity and pinned version verified")
