# The 7-Phase Synthetic Data Pipeline That Calibrates the Judge Before Trusting It

Most synthetic data pipelines are optimized in one direction: make the generator better. Iterate on prompts, switch models, add few-shot examples. The evaluation stays fixed. This pipeline inverts that assumption — it calibrates the judge against a known benchmark before it scores a single generated sample, because a miscalibrated judge silently invalidates every finding that follows it.

This post documents a 7-phase pipeline for generating and evaluating synthetic DIY repair Q&A data. The surprise: when you hold questions constant across prompt strategies, the one with the lowest failure rate had the *worst* quality pass rate. And the dimension everyone ignores — safety specificity — scored 36% against a 90% threshold.

One thing to take away: a framework for building evaluation loops that can tell the difference between "no failures detected" and "actually good data."

---

## The Evaluation Gap

```
LLM Generation
 └─ Structural Validation  (schema + heuristic gates)
     └─ Benchmark Calibration  (judge vs. known-good data)
         └─ Failure Labeling   (6 binary failure modes)
             └─ Quality Evaluation  (6 quality dimensions)
                 └─ Analysis & Visualization
                     └─ Data-Driven Prompt Correction
```

Each stage measures something different. Structural validation asks: *does the output conform to the schema?* Failure labeling asks: *what is wrong with this output?* Quality evaluation asks: *how good is it?* These are not the same question. A response can pass schema validation, have zero detected failure modes, and still score 48% on quality dimensions.

Most pipelines conflate these. This one separates them — and that separation is where the non-obvious findings live.

---

## The Dataset

**Source:** [dipenbhuva/home-diy-repair-qa](https://huggingface.co/datasets/dipenbhuva/home-diy-repair-qa) — 5,000 DIY repair Q&A items balanced across 5 categories (appliance, electrical, general, HVAC, plumbing), 1,000 each.

**Pipeline output:** 25 Q&A pairs per run, generated across all 5 categories (5 per category).

**Prompt strategies compared:** `zero_shot`, `few_shot`, `chain_of_thought` — evaluated on shared questions (Ph1a/Ph1b controlled mode) and independent random questions (default mode).

---

## Finding 1: The Question Confound — Why Random Questions Inflate Quality Scores

The default pipeline gives each strategy its own random question set. That conflates two variables: *question difficulty* and *strategy quality*. If zero_shot draws easier questions, it scores better — not because it writes better answers, but because it got luckier inputs.

The Ph1a/Ph1b controlled mode fixes this:

- **Ph1a**: generate one shared question set (25 questions, stable `trace_id`s)
- **Ph1b**: all three strategies answer the *same* questions

The effect is measurable. `baseline-cot` with random questions scored 56% overall quality pass rate. `shared-cot` with the same strategy but shared questions scored 48%. The 8-point difference is question difficulty, not strategy quality.

**The rule:** if you're comparing prompt strategies, hold the questions constant. Random question sets make strategy comparisons unreliable — the winner may have just drawn easier inputs.

---

## Finding 2: Zero Failure Modes ≠ Good Data

`baseline-cot` scored 0% on every failure mode. Every single flag — incomplete answer, safety violations, unrealistic tools, overcomplicated solution, missing context, poor tips — reported 0% failure rate.

The same run scored 56% overall quality pass rate.

These measurements aren't contradictory. Failure labeling and quality evaluation measure different things:

| Evaluation type | Question it answers | `baseline-cot` result |
|---|---|---|
| Failure labeling (Phase 4) | Is anything *wrong* with this data? | 0% failure rate |
| Quality evaluation (Phase 5) | How *good* is this data? | 56% pass rate |
| Benchmark calibration (Phase 3) | Does the judge work on known-good data? | 100% ✓ |

"No failures detected" does not mean "meets quality threshold." The failure labels catch defects; the quality dimensions measure positive attributes. You need both — and they'll tell you different things.

**The rule:** run failure labeling and quality evaluation separately. A 0% failure rate with a 50% quality pass rate is not a contradiction — it's a signal that your generator avoids obvious mistakes but still doesn't produce excellent output.

---

## Finding 3: Safety Specificity Is the Hardest Dimension — By Far

Across all three strategies and both question modes, safety specificity (D2) was the lowest-scoring dimension, and by a wide margin:

| Strategy | Safety Specificity (D2) | Target |
|---|---|---|
| `baseline-cot` (random Q) | 36% | ≥ 90% |
| `shared-cot` | 40% | ≥ 90% |

The benchmark scores 100% on D2. The gap is 60–64 percentage points.

**Why?** The benchmark's definition is specific: `safety_info` must name *the particular hazard of this repair* and *the particular precaution* to take. "Be careful" fails. "Turn off the circuit breaker at the main panel before touching any wiring" passes. LLMs default to generic safety language unless explicitly prompted otherwise — it's the path of least resistance in the training distribution.

This was the same across all three strategies. Adding few-shot examples didn't close the gap. Neither did chain-of-thought reasoning. The fix is prompt-level: explicitly instructing the model that generic phrases fail, with examples of passing and failing safety language.

**The rule:** evaluate safety separately from correctness. An answer can be technically accurate and still give useless safety guidance. Define "specific hazard + specific precaution" explicitly in the prompt — generic safety language is the default unless you tell the model it fails.

---

## Finding 4: CoT Had the Lowest Failure Rate but the Worst Quality Pass Rate

| Strategy | Failure Rate | Quality Pass Rate |
|---|---|---|
| `shared-cot` | **4%** | 48% |
| `shared-zero_shot` | 8% | **52%** |
| `shared-few_shot` | 12% | **52%** |

CoT produced the fewest detectable failures. It also produced the worst quality score.

This is the "no failures detected ≠ good data" finding in concrete form. Chain-of-thought reasoning helps the model avoid specific failure patterns. It doesn't necessarily help it produce high-quality tips, specific safety guidance, or context-rich answers.

Few-shot had the highest failure rate (12%) but tied for the best quality pass rate (52%). The examples in few-shot prompts may introduce surface-level patterns the failure detector catches while still producing better-quality content overall.

**The rule:** don't pick a prompt strategy based on failure rate alone. Quality pass rate is a separate signal. In this experiment, the strategy that best avoided failures produced the worst quality. Run both evaluations and compare.

---

## The Benchmark Calibration Design Decision

The judge is calibrated against 50 benchmark samples *before* it evaluates any generated data. The calibration requirement is 95%+ pass rate on benchmark items.

Why calibrate first? If the judge is systematically lenient or strict on a dimension, every downstream quality score is distorted — and you won't know it unless you check against a known-good reference. A judge that fails calibration at 80% on D2 makes all D2 scores 10-15 points too low or too high. Phase 7 would then correct the generator for a problem the generator doesn't have.

The benchmark scored 100% on all dimensions in these runs — judge is calibrated. This is a prerequisite, not a nice-to-have.

---

## Why Each Dimension Gets Its Own Judge Call

Phase 5 makes one `judge_binary` call per dimension, per sample — 6 calls per item, not 1 batched call for all 6. This is intentional and costs approximately 6× more.

The reason: attention interference. When a single prompt asks a judge to evaluate completeness, safety, tool realism, scope, context, and tip quality simultaneously, the model anchors on the most salient dimension — usually the longest, most detailed answer field. Isolated calls produce more reliable per-dimension scores.

This is the same principle behind multi-sample evaluation: don't batch things that need independent assessment.

---

## Cost Breakdown

| Role | Model | Cost per run |
|---|---|---|
| Generation (50 samples) | `llama-3.1-8b-instant` (Groq) | ~$0.003 |
| Judge (Phases 3–5) | `qwen2.5:3b` (local Ollama) | $0.000 |
| **Total** | | **~$0.003** |

The full 7-phase evaluation loop — generation, validation, calibration, failure labeling, quality evaluation, analysis, and correction — costs approximately $0.003 per run with the recommended setup. The practical implication: run the full loop, not just spot checks. At $0.003 per iteration, the cost of skipping evaluation is measured in quality gaps, not dollars.

---

## Takeaways

**1. Calibrate the judge before using it.** A miscalibrated judge distorts every downstream metric. Run it on benchmark data first. If it can't score known-good items correctly, don't trust it on generated data.

**2. Separate failure detection from quality evaluation.** Failure labeling catches defects. Quality evaluation measures positive attributes. Zero failures detected does not mean high-quality data. Run both.

**3. Hold questions constant when comparing strategies.** Random question sets conflate question difficulty with strategy quality. Ph1a/Ph1b controlled mode removes that confound — the 8-point quality gap between random and shared questions proves it's real.

**4. Safety specificity is the hardest dimension to get right.** All three strategies scored 36–40% on a 90% threshold. Generic phrases pass structural validation and fail quality evaluation. Define passing and failing safety language explicitly in the prompt.

**5. Prompt strategy choice is not a single-metric decision.** CoT minimizes failure rate. Zero-shot maximizes quality pass rate (tied). The best strategy depends on which evaluation signal matters more for your use case.

**6. Use separate judge calls per dimension.** Batching multiple quality criteria into one prompt degrades per-dimension reliability. One call per dimension costs more and produces more accurate scores.

---

## Run It Yourself

```bash
git clone git@github.com:selizondo/synthetic-data-diy.git
cd synthetic-data-diy

pip install -r requirements.txt
cp .env.example .env
# Set LLM_API_KEY (Groq) and LLM_JUDGE_BASE_URL (Ollama) in .env

# Full 7-phase run
python main.py --batch-label my-run-1

# Controlled strategy comparison (Ph1a + Ph1b)
python main.py questions --samples-per-category 5
python main.py --phase 1-6 --all-active --shared-questions

# View results across all runs
python main.py stats
python main.py compare
```

Results land in `output/<batch-label>/`. Each phase is independently re-runnable with the same `--batch-label`. Phase 7 correction is iterative — pass `--max-iterations 5` to allow more correction cycles.
