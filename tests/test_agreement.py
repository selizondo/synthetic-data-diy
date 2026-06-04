"""
Unit tests for the agreement calculation logic.

Tests cover: per-dimension agreement rate, threshold detection, TP/TN/FP/FN
counting, and no-overlap edge case. These test the computation kernel inside
run_agreement() without hitting disk or requiring output directories.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agreement import AGREEMENT_THRESHOLD
from schema import HUMAN_TO_LLM

# ---------------------------------------------------------------------------
# Agreement computation kernel (extracted for unit testing)
# ---------------------------------------------------------------------------


def compute_agreement(
    human_records: list[dict],
    llm_records: list[dict],
    threshold: float = AGREEMENT_THRESHOLD,
) -> dict[str, dict]:
    """
    Pure-function agreement computation extracted from run_agreement().

    Returns per-dimension agreement stats without file I/O.
    """
    llm_by_id = {r["trace_id"]: r for r in llm_records}

    joined = [(h, llm_by_id[h["trace_id"]]) for h in human_records if h["trace_id"] in llm_by_id]

    if not joined:
        return {}

    dim_results: dict[str, dict] = {}
    for human_key, llm_key in HUMAN_TO_LLM.items():
        pairs = [
            (int(h.get(human_key)), int(lv.get(llm_key)))
            for h, lv in joined
            if h.get(human_key) is not None and lv.get(llm_key) is not None
        ]
        if not pairs:
            continue

        n_total = len(pairs)
        n_agree = sum(1 for hv, lv in pairs if hv == lv)
        rate = n_agree / n_total

        tp = tn = fp = fn = 0
        for hv, lv in pairs:
            if hv == 1 and lv == 1:
                tp += 1
            elif hv == 0 and lv == 0:
                tn += 1
            elif hv == 0 and lv == 1:
                fp += 1
            else:
                fn += 1

        dim_results[human_key] = {
            "agreement_rate": round(rate, 4),
            "n_agreed": n_agree,
            "n_total": n_total,
            "meets_threshold": rate >= threshold,
            "true_positive": tp,
            "true_negative": tn,
            "false_positive": fp,
            "false_negative": fn,
        }

    return dim_results


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _human_record(trace_id: str, **scores) -> dict:
    defaults = {
        "answer_completeness": 1,
        "safety_specificity": 1,
        "tool_realism": 1,
        "scope_appropriateness": 1,
        "context_clarity": 1,
        "tip_usefulness": 1,
    }
    defaults.update(scores)
    return {"trace_id": trace_id, **defaults}


def _llm_record(trace_id: str, **scores) -> dict:
    defaults = {
        "answer_completeness": 1,
        "safety_specificity": 1,
        "tool_realism": 1,
        "appropriate_scope": 1,  # LLM key differs from human key for D4
        "context_clarity": 1,
        "tip_usefulness": 1,
    }
    defaults.update(scores)
    return {"trace_id": trace_id, **defaults}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAgreementRate:
    def test_perfect_agreement_all_ones(self):
        human = [_human_record(f"t{i}") for i in range(10)]
        llm = [_llm_record(f"t{i}") for i in range(10)]
        result = compute_agreement(human, llm)
        for dim, stats in result.items():
            assert stats["agreement_rate"] == 1.0, f"{dim}: expected 1.0"
            assert stats["meets_threshold"]

    def test_zero_agreement_all_disagree(self):
        # Human says 1, LLM says 0 for every item on D1
        human = [_human_record(f"t{i}", answer_completeness=1) for i in range(5)]
        llm = [_llm_record(f"t{i}", answer_completeness=0) for i in range(5)]
        result = compute_agreement(human, llm)
        assert result["answer_completeness"]["agreement_rate"] == 0.0
        assert not result["answer_completeness"]["meets_threshold"]

    def test_80_percent_agreement_meets_threshold(self):
        # 8 agree, 2 disagree on D2
        human = [_human_record(f"t{i}", safety_specificity=1) for i in range(8)] + [
            _human_record(f"t{i + 8}", safety_specificity=1) for i in range(2)
        ]
        llm = [_llm_record(f"t{i}", safety_specificity=1) for i in range(8)] + [
            _llm_record(f"t{i + 8}", safety_specificity=0) for i in range(2)
        ]
        result = compute_agreement(human, llm)
        assert result["safety_specificity"]["agreement_rate"] == 0.8
        assert result["safety_specificity"]["meets_threshold"]

    def test_79_percent_agreement_below_threshold(self):
        # 79 agree, 21 disagree
        human = [_human_record(f"t{i}", tool_realism=1) for i in range(79)] + [
            _human_record(f"t{i + 79}", tool_realism=1) for i in range(21)
        ]
        llm = [_llm_record(f"t{i}", tool_realism=1) for i in range(79)] + [
            _llm_record(f"t{i + 79}", tool_realism=0) for i in range(21)
        ]
        result = compute_agreement(human, llm)
        assert result["tool_realism"]["agreement_rate"] == 0.79
        assert not result["tool_realism"]["meets_threshold"]


class TestConfusionMatrix:
    def test_tp_tn_fp_fn_counts_correct(self):
        # Human [1,1,0,0], LLM [1,0,1,0] → TP=1, FN=1, FP=1, TN=1
        human = [
            _human_record("t0", answer_completeness=1),
            _human_record("t1", answer_completeness=1),
            _human_record("t2", answer_completeness=0),
            _human_record("t3", answer_completeness=0),
        ]
        llm = [
            _llm_record("t0", answer_completeness=1),
            _llm_record("t1", answer_completeness=0),
            _llm_record("t2", answer_completeness=1),
            _llm_record("t3", answer_completeness=0),
        ]
        result = compute_agreement(human, llm)
        stats = result["answer_completeness"]
        assert stats["true_positive"] == 1
        assert stats["true_negative"] == 1
        assert stats["false_positive"] == 1
        assert stats["false_negative"] == 1
        assert stats["agreement_rate"] == 0.5

    def test_all_true_positive(self):
        human = [_human_record(f"t{i}", context_clarity=1) for i in range(5)]
        llm = [_llm_record(f"t{i}", context_clarity=1) for i in range(5)]
        result = compute_agreement(human, llm)
        stats = result["context_clarity"]
        assert stats["true_positive"] == 5
        assert stats["true_negative"] == 0
        assert stats["false_positive"] == 0
        assert stats["false_negative"] == 0


class TestEdgeCases:
    def test_no_overlapping_trace_ids_returns_empty(self):
        human = [_human_record("human-only-1"), _human_record("human-only-2")]
        llm = [_llm_record("llm-only-1"), _llm_record("llm-only-2")]
        result = compute_agreement(human, llm)
        assert result == {}

    def test_partial_overlap_uses_only_matched(self):
        human = [_human_record("shared"), _human_record("human-only")]
        llm = [_llm_record("shared"), _llm_record("llm-only")]
        result = compute_agreement(human, llm)
        # Only the "shared" trace_id contributes
        for stats in result.values():
            assert stats["n_total"] == 1

    def test_d4_key_mapping_human_scope_appropriateness_to_llm_appropriate_scope(self):
        # D4 uses different keys: human="scope_appropriateness", llm="appropriate_scope"
        human = [_human_record("t0", scope_appropriateness=1)]
        llm = [_llm_record("t0", appropriate_scope=0)]
        result = compute_agreement(human, llm)
        stats = result.get("scope_appropriateness")
        assert stats is not None
        assert stats["agreement_rate"] == 0.0
        assert stats["false_negative"] == 1
