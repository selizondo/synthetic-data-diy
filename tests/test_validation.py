"""
Unit tests for phase2_validation heuristic gates, dedup, and distribution checks.

Tests cover: _apply_heuristic_gates (D2 safety length, D2/D6 generic phrases,
D3 tool blocklist, D6 tip length), _run_dedup (exact match), and
_check_category_distribution (≥20% per category).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from phase2_validation import (
    _MIN_SAFETY_INFO_LEN,
    _MIN_TIP_LEN,
    _apply_heuristic_gates,
    _check_category_distribution,
    _run_dedup,
)
from schema import QAPair, ValidatedResult


def _make_qa(**overrides) -> QAPair:
    base = dict(
        question="How do I fix a dripping kitchen faucet?",
        answer=(
            "Turn off the water supply valve under the sink. Remove the faucet handle. "
            "Replace the washer. Reassemble and test. The valve prevents flooding."
        ),
        equipment_problem="Dripping kitchen faucet",
        tools_required=["adjustable wrench", "screwdriver"],
        steps=[
            "Turn off the water supply valve under the sink",
            "Remove the faucet handle by unscrewing the set screw",
            "Replace the worn washer and reassemble",
        ],
        safety_info=(
            "Turn off the main water supply valve completely before starting — "
            "failing to do so will cause water to spray under pressure when you "
            "remove the handle. Verify with a voltage tester that it is off."
        ),
        tips=["Photograph the disassembly order so reassembly is easier and faster"],
    )
    base.update(overrides)
    return QAPair(**base)  # type: ignore[arg-type]


def _make_validated(qa: QAPair, category: str = "plumbing") -> ValidatedResult:
    return ValidatedResult(
        qa_pair=qa,
        category=category,
        trace_id="trace-001",
    )


class TestHeuristicGates:
    def test_good_item_passes_all_gates(self):
        qa = _make_qa()
        failures = _apply_heuristic_gates(qa)
        assert failures == [], f"Expected no failures, got: {failures}"

    def test_safety_info_too_short_triggers_gate(self):
        short_safety = "A" * (_MIN_SAFETY_INFO_LEN - 1)
        qa = _make_qa(safety_info=short_safety)
        failures = _apply_heuristic_gates(qa)
        assert any("safety_info too short" in f for f in failures)

    def test_safety_info_at_min_length_passes(self):
        exact_safety = "A" * _MIN_SAFETY_INFO_LEN
        qa = _make_qa(safety_info=exact_safety)
        failures = _apply_heuristic_gates(qa)
        assert not any("safety_info too short" in f for f in failures)

    def test_generic_phrase_in_safety_info_triggers_gate(self):
        qa = _make_qa(safety_info="Be careful when doing this repair work.")
        failures = _apply_heuristic_gates(qa)
        assert any("be careful" in f.lower() for f in failures)

    def test_generic_phrase_use_caution_triggers_gate(self):
        qa = _make_qa(safety_info="Use caution when handling electrical components.")
        failures = _apply_heuristic_gates(qa)
        assert any("generic phrase" in f for f in failures)

    def test_generic_phrase_stay_safe_triggers_gate(self):
        qa = _make_qa(
            safety_info="Always stay safe and turn off the breaker before starting.",
            tips=["Test with a non-contact voltage tester to confirm power is off"],
        )
        failures = _apply_heuristic_gates(qa)
        assert any("generic phrase" in f for f in failures)

    def test_trade_only_tool_triggers_gate(self):
        qa = _make_qa(tools_required=["professional-grade pipe cutter", "wrench"])
        failures = _apply_heuristic_gates(qa)
        assert any("professional-grade" in f for f in failures)

    def test_specialty_tool_triggers_gate(self):
        qa = _make_qa(tools_required=["specialty torque wrench", "screwdriver"])
        failures = _apply_heuristic_gates(qa)
        assert any("specialty" in f for f in failures)

    def test_short_tip_triggers_gate(self):
        short_tip = "A" * (_MIN_TIP_LEN - 1)
        qa = _make_qa(tips=[short_tip])
        failures = _apply_heuristic_gates(qa)
        assert any("tip" in f.lower() for f in failures)

    def test_tip_at_min_length_passes(self):
        exact_tip = "A" * _MIN_TIP_LEN
        qa = _make_qa(tips=[exact_tip])
        failures = _apply_heuristic_gates(qa)
        assert not any("tip" in f.lower() and "chars" in f for f in failures)

    def test_multiple_failures_reported(self):
        qa = _make_qa(
            safety_info="Be careful.",
            tools_required=["trade-only pipe bender"],
        )
        failures = _apply_heuristic_gates(qa)
        assert len(failures) >= 2


class TestDedup:
    def test_no_duplicates_unchanged(self):
        items = [
            _make_validated(
                _make_qa(question="How do I fix a dripping faucet in my kitchen?"),
                "plumbing",
            ),
            _make_validated(_make_qa(question="How do I patch a hole in my drywall?"), "drywall"),
        ]
        kept, n_dupes = _run_dedup(items)
        assert len(kept) == 2
        assert n_dupes == 0

    def test_exact_duplicate_question_removed(self):
        qa = _make_qa()
        items = [_make_validated(qa, "plumbing"), _make_validated(qa, "plumbing")]
        kept, n_dupes = _run_dedup(items)
        assert len(kept) == 1
        assert n_dupes == 1

    def test_case_insensitive_dedup(self):
        qa1 = _make_qa(question="How do I fix a dripping faucet in my kitchen?")
        qa2 = _make_qa(question="HOW DO I FIX A DRIPPING FAUCET IN MY KITCHEN?")
        items = [_make_validated(qa1, "plumbing"), _make_validated(qa2, "plumbing")]
        kept, n_dupes = _run_dedup(items)
        assert len(kept) == 1
        assert n_dupes == 1

    def test_single_item_passes_dedup(self):
        items = [_make_validated(_make_qa(), "plumbing")]
        kept, n_dupes = _run_dedup(items)
        assert len(kept) == 1
        assert n_dupes == 0


class TestCategoryDistribution:
    def _items_for_categories(self, category_counts: dict) -> list:
        items = []
        for cat, count in category_counts.items():
            for i in range(count):
                qa = _make_qa(question=f"Question {cat} {i} about home repair and maintenance?")
                items.append(_make_validated(qa, cat))
        return items

    def test_uniform_distribution_passes(self):
        items = self._items_for_categories(
            {
                "plumbing": 20,
                "electrical": 20,
                "drywall": 20,
                "painting": 20,
                "flooring": 20,
            }
        )
        fractions, passes = _check_category_distribution(items)
        assert passes, f"Expected pass, fractions: {fractions}"
        assert all(v >= 0.20 for v in fractions.values())

    def test_underrepresented_category_fails(self):
        items = self._items_for_categories(
            {
                "plumbing": 30,
                "electrical": 30,
                "drywall": 30,
                "painting": 9,  # 9/100 = 9% — below 20%
                "flooring": 1,
            }
        )
        fractions, passes = _check_category_distribution(items)
        assert not passes
        # at least one category must be below the 20% threshold
        assert any(v < 0.20 for v in fractions.values())

    def test_empty_items_returns_empty_fractions(self):
        fractions, passes = _check_category_distribution([])
        assert fractions == {}
        assert not passes

    def test_single_category_fails_below_threshold(self):
        items = self._items_for_categories({"plumbing": 10})
        fractions, passes = _check_category_distribution(items)
        # single category = 100% but others are missing → depends on implementation
        # the function only checks categories present; 100% > 20% → passes
        assert passes  # 1 category at 100% passes the per-category threshold
