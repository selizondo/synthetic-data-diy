# Design Decisions and Tradeoffs

## Binary labels (0/1) over Likert scale

Quality dimensions (D1–D6) are scored as binary pass/fail rather than a 1–5 Likert scale. The target use case is dataset filtering: an item is either suitable for fine-tuning or it is not. A Likert scale would require calibrating a passing threshold anyway, and inter-rater agreement on ordinal scales is consistently lower than on binary ones. The tradeoff: binary labels lose granularity — a "barely passes D2" item looks identical to a "strongly passes D2" item. This is acceptable because the pipeline's goal is dataset construction, not performance ranking.

## 80% agreement threshold for judge calibration

The Phase A agreement gate requires ≥80% per-dimension agreement between human labels and LLM judge before trusting the judge on the full dataset. This threshold was chosen to match standard inter-rater reliability cutoffs in annotation research (Cohen's κ ≈ 0.6 maps to ~80% agreement on balanced binary data). Below 80%, the dimension prompt needs revision; above 80%, human spot-checking is sampled rather than exhaustive. The tradeoff: 80% is a guideline, not a calibrated empirical threshold for this specific domain.

## Heuristic gates before LLM judge

Phase 2 applies deterministic rule checks (safety length, generic phrase detection, tool blocklist, tip length) before routing items to the LLM judge. Rules are fast, free, and reproducible — they reject obvious failures in milliseconds with no API cost. The LLM judge handles the cases rules can't catch (awkward phrasing, hallucinated but plausible tool names, safety advice that's specific but wrong). The tradeoff: rule thresholds (e.g., `_MIN_SAFETY_INFO_LEN = 80` characters) are arbitrary and may reject valid edge cases.

## Trace ID across all phases

Every generated item carries a `trace_id` from Phase 1 through Phase 7 (correction loop). This enables joining records across pipeline output files without a relational database. The alternative — positional joining by JSONL line number — breaks when phases skip items (validation failures, rate-limit drops). Trace IDs also make Langfuse/Logfire observability possible: all LLM calls for a single item share the same trace context.

## JSONL append-only checkpointing

Completed items are written to JSONL immediately after generation, not batched at phase end. A crash or rate-limit exhaustion loses at most one item. The tradeoff: JSONL is append-only — `--resume` re-reads all existing records and skips already-completed `trace_id` values, adding O(n) startup cost for large runs. This is acceptable at expected dataset sizes (hundreds to low thousands of items).

## Correction loop re-validates after fixing (Phase 7)

After the LLM corrects an invalid item, it is put back through schema validation before acceptance. This catches corrections that introduce new violations (e.g., removing a short tip by replacing it with an even shorter one). The alternative — trusting the correction without re-checking — produces silent schema violations downstream. The cost is one extra validation pass per corrected item, which is negligible.

## 7-field schema (not minimal)

`QAPair` requires all 7 fields (`question`, `answer`, `equipment_problem`, `tools_required`, `steps`, `safety_info`, `tips`). A minimal schema (question + answer) would be easier to generate but wouldn't produce the structured, multi-section data needed for fine-tuning a DIY assistant. The constraint is a feature: it forces the LLM to produce grounded, tool-specific, step-by-step content and makes schema validation a meaningful quality gate.
