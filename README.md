# Synthetic Data DIY — Home Repair Q&A Generator (P1)

Automated pipeline that generates, validates, evaluates, and iteratively improves synthetic Q&A training data for a Home DIY Repair assistant.

Spec: [synthetic_data_diy.md](synthetic_data_diy.md)

*Companion post: [docs/blog_post.md](docs/blog_post.md) — the agreement gate that stops you from trusting a judge that disagrees with humans 30% of the time.*

*See [docs/tradeoffs.md](docs/tradeoffs.md) for design decisions and [docs/failures.md](docs/failures.md) for known failure modes.*

---

## Key Concepts

**Trace ID** — UUID assigned at generation time and carried through all 7 phases. Enables joining records across `generation_results.json`, `failure_labeled_data.json`, `quality_eval_data.json`, and Logfire/Langfuse traces without a database.

**6 quality dimensions (D1–D6)** — binary pass/fail scored independently by human and LLM judge on the same item: Answer Completeness, Safety Specificity, Tool Realism, Scope Appropriateness, Context Clarity, Tip Usefulness. The per-dimension disagrement rate drives the calibration loop.

**Agreement gate (80%)** — before trusting the LLM judge at scale, Phase A computes human/judge agreement per dimension. Any dimension below 80% blocks Phase 5 and triggers prompt revision. Uses TP/TN/FP/FN counts, not just overall accuracy, to distinguish "judge too strict" from "judge too lenient."

**Instructor** — wraps the OpenAI API to enforce a Pydantic schema at output time, retrying on parse failures internally. Prevents schema validation failures from reaching Phase 2 (validation phase handles semantic failures, not structural ones).

**Correction loop** — Phase 7 targets the single (segment × dimension) combination with the worst failure rate, rewrites the generator prompt for that failure mode, re-runs generation on that segment, and compares pass rates before and after. One targeted fix per iteration — avoids prompt drift from over-correcting.

---

## Objective

**Problem:** Training a reliable DIY repair assistant requires large volumes of accurate, safe, and practical Q&A data. Manual authoring is expensive and slow. LLM-generated data is fast but unreliable — models produce dangerously incomplete electrical guidance, recommend exotic tools, or give vague advice that doesn't actually help.

**Solution:** A 7-phase pipeline that generates data at scale and proves it improved through a measurable before/after ratio — mirroring a real-world MLOps workflow (generate → evaluate → diagnose → fix).

**Core challenge:** LLMs don't self-correct without feedback. The system must compare human judgments against an independent LLM-as-Judge on the same 6 quality dimensions, use that disagreement to calibrate the judge, and then use the calibrated judge to drive generator prompt correction.

**Seven pipeline phases:**

| Phase | What happens |
|---|---|
| **1. Generate** | Structured prompt → LLM (Instructor) → Q&A items across 5 repair categories |
| **2. Validate** | Schema checks + per-dimension heuristic gates + dedup + category distribution |
| **3. Human Label** | CLI reviewer scores each item on 6 quality dimensions (binary pass/fail) |
| **4. LLM Judge** | Independent LLM scores the same 6 dimensions (different prompt, lower temp) |
| **5. Analyze** | Aggregate labels, compute human/LLM agreement per dimension, produce charts |
| **6a. Calibrate** | If agreement < 80% on any dim, iterate judge prompt until calibrated |
| **6b. Correct** | Once judge is trusted, identify worst segment × dimension, fix generator prompt, re-run |

**6 quality dimensions:** Accuracy (D1), Safety (D2), Specificity (D3), Completeness (D4), Clarity (D5), Context (D6)

**Success signal:** Measurable pass-rate improvement on the corrected segment vs. baseline.

---

## Setup

```bash
cd src
pip install -r requirements.txt
cp .env.example .env   # set LLM_API_KEY / LLM_BASE_URL
```

---

## Run

```bash
cd src

# Run full pipeline (baseline batch)
python main.py run --batch-label baseline

# Human labeling step
python human_labeler.py --batch-label baseline

# Analysis + charts
python main.py analysis --batch-label baseline

# Correction phase (Phase 6b)
python main.py correction --batch-label baseline
```

---

## Project Layout

```
synthetic_data_diy/
├── src/
│   ├── main.py                  # CLI entry point (run / questions / analysis / correction)
│   ├── phase1_generation.py     # LLM Q&A generation (Instructor + structured output)
│   ├── phase2_validation.py     # Schema + heuristic gates + dedup + distribution check
│   ├── phase3_human_labeling.py # CLI labeler (6-dim binary pass/fail)
│   ├── phase4_llm_judge.py      # LLM-as-Judge (6-dim, batch via instructor)
│   ├── phase5_analysis.py       # Aggregation, agreement metrics, charts
│   ├── phase6_iteration.py      # Judge calibration loop
│   ├── phase7_correction.py     # Generator correction + before/after comparison
│   ├── llm_client.py            # Shared LLM client adapter (wraps llm_utils)
│   └── models.py                # Pydantic schemas (RepairQA, JudgeLabel, etc.)
├── data/                        # Generated batches, labels, iteration logs
├── synthetic_data_diy.md        # Full project spec
└── blog_Synthetic_Data_DIY.md
```
