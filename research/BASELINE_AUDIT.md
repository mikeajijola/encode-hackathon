# Arm A baseline and evaluator audit

## Scope and experimental identity

This audit characterizes the repository at the start of the controlled experiment. It does not use benchmark goldens to drive a run and does not propose changes to registered outcomes or thresholds.

Arm A is implemented by `baseline/llm_predict.py` plus `baseline/common.py`:

1. Load every selected task and serialize cached workbook **values** (not formula text), capped at 120 rows and 30 columns per sheet.
2. Supply the natural-language instruction, serialized values, `answer_sheet`, and `answer_position` to one temperature-zero model call.
3. Ask for plain values in a JSON cell list. There are no tools, observations after the initial serialization, executable evals, or retries.
4. Copy the initial workbook and write only returned coordinates that also fall within the declared answer range. Missing returned coordinates retain their initial value; returned coordinates outside the range are silently ignored.
5. On any model, parsing, or writing exception, copy the initial workbook as the output and record an error.
6. Emit one trace event and one prediction row. The baseline itself does not claim `FULFILLED`; official scoring determines pass/fail later.

This is consequently a benchmark-targeted, one-shot answer-range value predictor. It cannot add sheets, preserve formulas as formulas in target cells, perform arbitrary workbook operations, inspect truncation omissions, or repair its output. All experimental arms must receive equivalent answer-range metadata and mutation authority, or this baseline definition must be versioned as a deviation.

## Evaluator behavior

`evaluate.py` loads golden and predicted cached values from only the benchmark answer cells. Unless disabled, LibreOffice first recalculates predicted workbooks. Equality follows repository normalization: numeric values are rounded to two decimals, datetimes become Excel serials, numeric strings compare as numbers, and empty strings equal empty cells. A task passes only if every compared answer cell matches.

`--all` makes absent task predictions failures. Without it, task selection is inferred from prediction IDs and is unsuitable for headline comparisons because omitted tasks disappear. Duplicate prediction IDs use the last row silently. Unknown prediction IDs do not become scored tasks. Oracle mode does not recalculate goldens.

## Experimental-validity risks

| Risk | Consequence | Required control |
|---|---|---|
| Answer range and answer sheet are supplied at fulfilment time | This is benchmark metadata and narrows both reasoning and writes | Hold it fixed across arms and disclose it |
| Serialized workbook is value-only and truncated to 120x30 | Formula semantics and out-of-window evidence may be unavailable | Record truncation per task; stratify by observation size |
| No run manifest captures package lock hash, environment, budgets, or model-provider revision | Runs cannot be exactly reconstructed from traces | Add immutable run manifests in shared experiment infrastructure |
| Temperature zero is set, but provider nondeterminism/seed and exact hosted revision are uncontrolled | Repeated runs may vary | Record provider model identifier and replicate samples |
| Concurrency is configurable and no wall-clock/token/action budget is enforced | Arms may differ in resource constraints | Enforce budgets above all arms and record deviations |
| Parser accepts the first-to-last brace span and duplicate cell entries become last-value-wins | Malformed responses may fail or be interpreted ambiguously | Preserve raw response and report parse failures |
| Missing response cells preserve initial target values | A partial response can accidentally pass unchanged targets | Treat as documented Arm A behavior; external grader remains authoritative |
| Output schema cannot distinguish identical coordinates on multiple sheets | Multi-sheet duplicate coordinates cannot express different values | Quantify affected dataset tasks before comparing arms |
| `--all` is optional | Selective prediction files can inflate results | Require `--all` for registered comparisons |
| Duplicate task IDs/prediction IDs are not rejected | Last-write-wins can obscure corrupt manifests | Validate run manifests before registered scoring |
| Scoring exceptions historically omitted cells from cell-accuracy denominator | Corrupt outputs could inflate cell accuracy | Fixed and regression-tested in the validity-fix commit following this audit |
| Error strings and only five mismatches are retained | Failure analysis evidence is lossy | Preserve evaluator result artifacts and artifact hashes externally |

Goldens are necessarily read by the offline evaluator. They must remain inaccessible to contract compilation, prompting, action selection, internal evals, and reconciliation. Keeping the scorer in the same source tree is not process isolation.

## Fixture evidence

`python -m unittest discover -s tests -v` (from `research/`) covers:

- semantic parsing and authorized-scope mutation;
- structural missing-output and scoring behavior;
- trace emission, error recording, and fallback artifact behavior;
- the error-denominator regression.

Fixtures are generated locally and contain no SpreadsheetBench examples or goldens. Rendered/visual evaluation is **N/A for Arm A characterization**: Arm A predicts answer-cell values and has no visual assertion or rendering capability. LibreOffice availability is an environment blocker on this host and is inventoried below.

## Environment inventory

- `rg` is absent; repository inspection used `find`/standard tools.
- Dataset files are absent until `data/download.py` is run.
- `soffice`/LibreOffice must be checked before registered evaluator runs; without it, formula-cache recalculation cannot match judge conditions.
- Model baselines require external provider credentials and network access. No paid call was made by this audit.

## Baseline acceptance gate

A registered Arm A run must pin the repository commit and lockfile hash, dataset checksum, task IDs, model/provider identifier, temperature, budgets, concurrency, recalculation executable/version, and scorer command. It must retain predictions, outputs, raw traces, logs, scorer JSON, and hashes. Headline scoring must use `--all`; oracle must score 1.0 in the same environment. Any deviation shared by all arms remains a limitation; any arm-specific deviation must be recorded.
