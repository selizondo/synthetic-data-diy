# Methodology

How the evaluation framework works, what the metrics measure, and where the methodology introduces known limitations.

---

## 6 Quality Dimensions (D1-D6)

Each generated Q&A item is scored independently on 6 binary pass/fail dimensions by both a human labeler and an LLM judge:

| Dimension | Definition | Why it matters |
|-----------|-----------|----------------|
| D1: Answer Completeness | Answer fully addresses all aspects of the question | Incomplete answers teach the fine-tuned model to give partial responses |
| D2: Safety Specificity | Safety guidance is specific and actionable, not generic | "Be careful" is not a safety instruction; "turn off the breaker at the panel" is |
| D3: Tool Realism | Recommended tools are real, purchasable, and appropriate for the task | Hallucinated or specialized-trade tools produce answers a homeowner cannot act on |
| D4: Scope Appropriateness | The repair is within realistic DIY scope, not requiring professional licensing | An answer that recommends a homeowner rewire a 200-amp panel is a liability |
| D5: Context Clarity | The problem description is unambiguous and understandable | Vague context produces vague training signal |
| D6: Tip Usefulness | Tips add value beyond what is already covered in the main answer | Redundant tips dilute the instruction signal |

---

## Agreement Computation

For each dimension, agreement is computed from TP/TN/FP/FN counts, not just overall accuracy:

- **True Positive (TP):** Human passes, judge passes
- **True Negative (TN):** Human fails, judge fails
- **False Positive (FP):** Human fails, judge passes (judge too lenient)
- **False Negative (FN):** Human passes, judge fails (judge too strict)

Agreement rate = (TP + TN) / (TP + TN + FP + FN)

The FP/FN split is the diagnostic: if FP >> FN, the judge prompt is too permissive and needs a stricter rubric. If FN >> FP, the judge is too strict and the rubric examples need positive cases added.

---

## Phase 3: Benchmark Calibration

Before the judge scores the dataset, Phase 3 compares judge outputs against a held-out HuggingFace benchmark set. This catches judge model degradation (e.g., a model that scores all items as passing) before it propagates to Phases 4-5. A judge that fails Phase 3 is not used in Phase 5.

---

## Known Limitations

**80% threshold is a guideline.** Inter-rater reliability requirements vary by domain and downstream use. For safety-critical content (electrical, structural), 80% may be too low; a 90% threshold with mandatory human review on all D2 failures is a reasonable escalation.

**Human calibration sample size is small.** Human Calibration is designed for a manageable spot-check (tens to low hundreds of items), not a statistically representative stratified sample. Agreement rates computed on small samples have wide confidence intervals.

**Correction loop measures pass rate, not quality.** A higher pass rate on the corrected segment means the generator is now satisfying the judge more often. It does not measure whether the generated content is actually better for homeowners.

**LLM judge is not a ground truth.** The agreement gate calibrates the judge against human labels on a sample. For items the judge scores but humans have not reviewed, there is no ground truth. The pipeline assumes calibrated-judge agreement transfers to unseen items, which is an approximation.
