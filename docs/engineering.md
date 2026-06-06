# Design and Tradeoffs

---

## Binary Labels over Likert Scale

Quality dimensions (D1-D6) are scored as binary pass/fail rather than a 1-5 Likert scale. The target use case is dataset filtering: an item is either suitable for fine-tuning or it is not. A Likert scale would require calibrating a passing threshold anyway, and inter-rater agreement on ordinal scales is consistently lower than on binary ones.

Tradeoff: binary labels lose granularity. A "barely passes D2" item looks identical to a "strongly passes D2" item. Acceptable because the pipeline's goal is dataset construction, not performance ranking.

---

## 80% Agreement Threshold

The Phase A agreement gate requires at least 80% per-dimension agreement between human labels and LLM judge before trusting the judge on the full dataset. This matches standard inter-rater reliability cutoffs in annotation research (Cohen's kappa approximately 0.6 maps to ~80% agreement on balanced binary data). Below 80%, the dimension prompt needs revision. Above 80%, human spot-checking is sampled rather than exhaustive.

Agreement is computed with TP/TN/FP/FN counts per dimension, not just overall accuracy. This distinguishes "judge too strict" from "judge too lenient": both fail at 80% but need opposite prompt changes.

Tradeoff: 80% is a guideline, not a calibrated empirical threshold for this specific domain.

---

## Heuristic Gates before LLM Judge

Phase 2 applies deterministic rule checks (safety length, generic phrase detection, tool blocklist, tip length) before routing items to the LLM judge. Rules are fast, free, and reproducible with no API cost. The LLM judge handles cases rules cannot catch: awkward phrasing, hallucinated but plausible tool names, safety advice that is specific but factually wrong.

Tradeoff: rule thresholds (e.g., `_MIN_SAFETY_INFO_LEN = 80` characters) are arbitrary and may reject valid edge cases.

---

## Trace ID Across All Phases

Every generated item carries a `trace_id` from Phase 1 through Phase 7. This enables joining records across pipeline output files (`generation_results.json`, `failure_labeled_data.json`, `quality_eval_data.json`) without a relational database. Positional joining by JSONL line number breaks when phases skip items (validation failures, rate-limit drops). Trace IDs also enable Langfuse/Logfire observability: all LLM calls for a single item share the same trace context.

---

## Incremental Checkpointing (Every 5 Items)

Completed items are flushed to `generation_results.json` every 5 items during Phase 1 generation, not batched at phase end. A crash or rate-limit exhaustion loses at most 5 items. On restart, `run_generation_phase()` re-reads the existing file, builds a set of completed `trace_id` values, and skips them. The 5-item cadence is a balance between safety and I/O cost at expected dataset sizes. Writing every 1 item (truly immediate) would add one disk write per LLM call.

---

## Correction Loop: One Fix Per Iteration

Phase 7 targets the single worst segment x dimension combination, rewrites the generator prompt for that failure mode, re-runs generation on that segment, and compares pass rates before and after. One fix per iteration prevents prompt drift from over-correction: if multiple dimensions are patched simultaneously, it's unclear which change caused which improvement.

Phase 7 re-validates corrected items against the schema before acceptance. This catches corrections that introduce new violations (e.g., replacing a short tip with an even shorter one).

---

## 7-Field Schema

`QAPair` requires all 7 fields (`question`, `answer`, `equipment_problem`, `tools_required`, `steps`, `safety_info`, `tips`). A minimal schema (question + answer) would be easier to generate but would not produce the structured, multi-section data needed for fine-tuning a DIY assistant. The constraint forces the LLM to produce grounded, tool-specific, step-by-step content. Schema validation becomes a meaningful quality gate rather than a structural check.

---

## Scale Boundary: ~5,000 Items Per Run

Single-process generation throughput is bounded by LLM API rate limits (~10 requests/second sustained). JSONL checkpoint files become slow to scan on restart at large sizes (O(n) trace_id dedup scan). The Phase A human calibration step assumes a manageable spot-check sample, not a statistically representative stratified sample.

Revisit triggers: dataset target above 5K items, need for parallel phase execution across multiple workers, or a downstream consumer that requires a query-able store rather than flat JSONL files.
