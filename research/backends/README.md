# SpreadsheetBench backend

Use `backends.spreadsheetbench:factory` in an experiment CLI manifest. The factory reads `dataset.json`, selects task IDs from a frozen selection manifest, locates only `*init*.xlsx`, and constructs runtime tasks containing instruction, answer-location metadata, and a bounded canonical observation. Dataset golden fields are ignored and never copied into runtime context.

The observation includes values/formulas, data types, number formats/style IDs, inspected and omitted scope, and explicit cell/character truncation accounting. Identical context and six capability manifests are supplied in every arm. Arm A retains one model call and one write action. Contract and action generation in B/C/D see the same bounded source facts.

Production uses `OPENROUTER_API_KEY`; model, model version, temperature, and budgets remain pinned by `run_config`. The provider records actual prompt/completion tokens, reported cost, and provider request ID where returned. Missing credentials and malformed provider responses are typed failures.

For CLI plumbing only, `provider.type=scripted` consumes configured JSON replies. Its request ID is `scripted-not-benchmark-evidence`; those runs must never be reported as benchmark evidence.

Example backend fragment:

```json
{
  "backend": "backends.spreadsheetbench:factory",
  "backend_config": {
    "dataset_dir": "/data",
    "selection_manifest": "/data/selection.json",
    "context_limits": {"max_cells": 400, "max_chars": 30000},
    "provider": {"type": "openrouter", "timeout_seconds": 120}
  }
}
```

The selection file is `{"task_ids":["13-1","51-12"]}`. Temperature other than zero is rejected for this preregistered backend.
