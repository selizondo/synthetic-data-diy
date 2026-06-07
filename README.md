# Synthetic Data DIY

![Tests](https://github.com/selizondo/synthetic-data-diy/actions/workflows/ci.yml/badge.svg)

LLM-generated training data is fast to produce and difficult to trust. A model generating DIY repair advice will produce dangerously incomplete electrical guidance, recommend exotic tools, and give vague instructions that sound correct but aren't. Without a calibration step, you're trusting a judge that may disagree with humans 30% of the time.

This pipeline generates, validates, evaluates, and iteratively corrects synthetic Q&A training data for a Home DIY Repair assistant. The key gate: an LLM judge must pass 80% agreement with human labels on each of 6 quality dimensions before it's allowed to score the full dataset. If it doesn't pass, the judge prompt is revised, not the threshold.

**Stack:** Python · OpenAI · instructor · Pydantic · Logfire

## Related Projects

1. [llm-eval-harness](https://github.com/selizondo/llm-eval-harness) — LLM-as-judge for RAG evaluation; same judgment pattern, different domain
2. [finetune-case-study](https://github.com/selizondo/finetune-case-study) — this pipeline produces the dataset for fine-tuning

*Companion post: [The Agreement Gate: Why You Can't Skip Judge Calibration](docs/blog_post.md) — data generation and validation*

---

## Results

7-phase pipeline on Home DIY Q&A (plumbing, electrical, carpentry, painting, flooring):

| Signal | Value |
|--------|-------|
| Agreement gate threshold | 80% per-dimension human/judge agreement |
| Quality dimensions | 6 (D1-D6): completeness, safety, tool realism, scope, clarity, tip usefulness |
| Correction loop | One targeted fix per iteration: worst segment x dimension |
| Scale boundary | ~5,000 items per run (single-process, JSONL checkpointing) |
| Phase 3 benchmark | Must pass before the judge scores the dataset |

## How It Works

### The agreement gate blocks the pipeline

Phase A computes human/judge agreement per dimension using TP/TN/FP/FN counts, not just overall accuracy. This distinguishes "judge too strict" from "judge too lenient": both fail at 80% but need opposite fixes. Any dimension below 80% blocks Phase 5 and triggers prompt revision. This is the gate that prevents trusting a miscalibrated judge at scale.

### Heuristics first, LLM judge second

Phase 2 applies deterministic rule checks (safety length, generic phrase detection, tool blocklist, tip length) before routing items to the LLM judge. Rules are fast, free, and reproducible. The LLM judge handles cases rules can't catch: plausible-sounding but wrong safety advice, hallucinated but realistic tool names. This ordering keeps API costs bounded and makes early-stage failures auditable without parsing model outputs.

### Correction loop targets one failure at a time

Phase 7 identifies the single worst segment x dimension combination, rewrites the generator prompt for that failure mode, re-runs generation on that segment, and compares pass rates before and after. One fix per iteration. Over-correcting by patching multiple dimensions simultaneously produces prompt drift where it's unclear which change caused which improvement.

## Go Deeper

| Audience | Doc |
|----------|-----|
| Running the code | [Setup and Usage](docs/setup.md) |
| Engineering decisions | [Design and Tradeoffs](docs/engineering.md) |
| Evaluation methodology | [Methodology](docs/methodology.md) |
| What breaks and why | [Failure Modes](docs/failures.md) |
