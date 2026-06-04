# Failure Scenarios

Documented failure modes with detection and fallback behavior.

---

## Failure 1: Agreement Phase Returns Empty — No Overlapping Trace IDs

### What breaks
`run_agreement()` raises `ValueError` when no `trace_id` values overlap between human labels and LLM quality eval output. Typically caused by running the agreement phase against a different `--batch-label` than the one used for Phase 5.

### Detection mechanism
`ValueError` with message: "No trace_ids overlap between human labels (N items) and LLM quality eval (M items)."

### Fallback behavior
Ensure both `human_labels.json` and `quality_eval_data.json` exist in the same `output/{batch_label}/` directory and were produced from the same batch run. The batch label must match in `--batch-label` across all phases.

---

## Failure 2: mock_seeder Quality Eval Mismatch After Schema Change

### What breaks
`generate_quality_evals()` in `mock_seeder.py` constructs `QualityEvalResult` using dimension names from `QUALITY_DIMENSION_FIELDS`. If the schema adds or removes a dimension and `MOCK_DEFAULTS["quality_rates"]` is not updated to match, the draw keys diverge from the schema fields — causing a Pydantic `ValidationError` at construction time.

### Detection mechanism
`pydantic.ValidationError` on `QualityEvalResult(...)` with "unexpected field" or "missing field" messages during mock pipeline runs.

### Fallback behavior
Keep `MOCK_DEFAULTS["quality_rates"]` keys in sync with `QUALITY_DIMENSION_FIELDS` in `schema.py`. The two lists must be identical. When adding a dimension, update both in the same commit.

---

## Failure 3: LLM Judge Silently Scores All Items as 0

### What breaks
Phase 3's `_check_judge_endpoint()` is designed to catch a dead judge endpoint before calibration starts. If the endpoint is up but returning empty or malformed responses, the check passes but all items receive a score of 0. This inflates the apparent failure rate and invalidates calibration.

### Detection mechanism
`_check_judge_endpoint()` pings with a single "Reply with 1" prompt. If it returns `""` or a non-digit, a `RuntimeError` is raised immediately. If the judge returns `0` to the ping (correctly, since it's a wrong answer), the check passes — this edge case requires a calibration pass rate sanity check (e.g., >95% on known-good benchmark items).

### Fallback behavior
If `BenchmarkReport.calibration_passed` is `False`, abort Phase 4–6 and revise the judge prompt in `quality_dimensions/*.yaml` before rerunning Phase 3.

---

## Failure 4: Correction Loop Produces No Corrections on Real API Runs

### What breaks
Phase 7 only corrects items that `phase4_failure_labeling.py` labels as failed. When `instructor` is used for Phase 1 generation, schema validation failures are retried internally — so schema-level failures never reach Phase 4. The correction loop fires only on semantic failures (incomplete answer, safety issues, etc.) which the LLM judge must detect.

### Detection mechanism
`phase7_correction.py` logs `0 items requiring correction` if no failures were detected. This is expected on high-quality runs, not a bug. If the judge agreement is below 80% (Phase A), failure labels may be unreliable — the correction loop is only as good as the labeler.

### Fallback behavior
This is expected behavior on clean generation runs. To exercise the correction loop in testing, use `mock_seeder.py` with elevated `failure_rates` (e.g., `"incomplete_answer": 0.5`).
