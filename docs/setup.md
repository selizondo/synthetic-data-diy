# Setup and Usage

## Prerequisites

- Python 3.11+
- OpenAI API key (or compatible endpoint via `LLM_BASE_URL`)

## Installation

```bash
cd src
pip install -r requirements.txt
cp .env.example .env   # set LLM_API_KEY / LLM_BASE_URL
```

## Running the Pipeline

```bash
cd src

# Full pipeline (baseline batch)
python main.py --batch-label baseline

# Human labeling step (interactive CLI, run after Phase 2)
python human_labeler.py --batch-label baseline

# Phase A: compute human/LLM agreement per dimension
python main.py agreement --batch-label baseline

# Stats and analysis for a completed run
python main.py stats --batch-label baseline

# Correction phase (Phase 7 — requires phases 4-5 output)
python main.py --phase 7 --batch-label baseline
```

## Pipeline Phases

| Phase | Command | What happens |
|-------|---------|-------------|
| 1. Generate | `--phase 1` | Structured prompt → LLM (Instructor) → Q&A items across 5 repair categories |
| 2. Validate | `--phase 2` | Schema checks + heuristic gates + dedup + category distribution |
| 3. Benchmark | `--phase 3` | Calibrate judge against HuggingFace benchmark |
| 4. Failure Label | `--phase 4` | LLM-as-Judge scores each item on 6 binary failure modes |
| 5. Quality Eval | `--phase 5` | LLM-as-Judge scores on 6 quality dimensions D1-D6 |
| 6. Analyze | `--phase 6` | Aggregate labels, compute agreement per dimension, produce charts |
| 7. Correct | `--phase 7` | Identify worst segment x dimension, fix prompt, re-run phases 1-5 |
| A. Agreement | `agreement` | Compute human/LLM agreement (requires human labels from human_labeler.py) |

Human labeling is a separate optional step. Run `python human_labeler.py --batch-label <label>` after Phase 2 to collect binary pass/fail scores on all 6 dimensions.

## Quality Dimensions

| Dimension | What it measures |
|-----------|-----------------|
| D1: Answer Completeness | Does the answer fully address the question? |
| D2: Safety Specificity | Is safety guidance specific and actionable? |
| D3: Tool Realism | Are recommended tools real and appropriate? |
| D4: Scope Appropriateness | Is the repair scope realistic for a DIY context? |
| D5: Context Clarity | Is the problem description unambiguous? |
| D6: Tip Usefulness | Do the tips add value beyond the main answer? |

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_API_KEY` | (required) | OpenAI or compatible API key |
| `LLM_BASE_URL` | OpenAI | Generation endpoint |
| `LLM_MODEL` | `gpt-4o-mini` | Generation model |
| `LLM_JUDGE_MODEL` | inherits | Judge model (can be different from generator) |

See [docs/pipeline_reference.md](pipeline_reference.md) for full CLI reference, config vars, and cost analysis.

## Code Layout

```
synthetic_data_diy/
├── src/
│   ├── main.py                    # CLI entry point
│   ├── phase1_generation.py       # LLM Q&A generation (Instructor + structured output)
│   ├── phase2_validation.py       # Schema + heuristic gates + dedup + distribution
│   ├── phase3_benchmark.py        # Benchmark comparison + category distribution
│   ├── phase4_failure_labeling.py # LLM-as-Judge failure labeling (6-dim, batch)
│   ├── phase5_quality_eval.py     # Quality evaluation + agreement metrics
│   ├── phase6_analysis.py         # Aggregation, segment metrics, charts
│   ├── phase7_correction.py       # Generator correction + before/after comparison
│   ├── human_labeler.py           # Interactive CLI labeler (6-dim binary pass/fail)
│   ├── agreement.py               # Human/LLM agreement (TP/TN/FP/FN per dimension)
│   ├── llm_client.py              # LLM client adapter (wraps llm_utils)
│   └── schema.py                  # Pydantic schemas (RepairQA, JudgeLabel, etc.)
└── data/                          # Generated batches, labels, iteration logs
```
