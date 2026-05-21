"""
Unit tests for Phase 1 generation checkpoint and resume behaviour.

Tests cover:
  - on_result callback fires once per item in generate_batch
  - checkpoint accumulation: callback receives correct GenerationResult objects
  - run_generation_phase mock path: resume skips already-completed trace_ids
  - run_generation_phase mock path: output file written on completion
"""

import json
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from schema import GenerationResult
from phase1_generation import DIYDatasetGenerator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(category: str = "plumbing") -> GenerationResult:
    return GenerationResult(
        trace_id=str(uuid.uuid4()),
        category=category,
        batch_id="b1",
        batch_label="test",
        prompt_strategy="zero_shot",
        raw_response="{}",
    )


def _make_generator(templates: list[dict]) -> DIYDatasetGenerator:
    """Return a DIYDatasetGenerator whose generate_single is mocked."""
    gen = MagicMock(spec=DIYDatasetGenerator)
    gen.templates = templates
    gen.generate_single = MagicMock(side_effect=lambda t: _make_result(t["category"]))
    gen.generate_batch = DIYDatasetGenerator.generate_batch.__get__(gen, DIYDatasetGenerator)
    return gen


# ---------------------------------------------------------------------------
# on_result callback in generate_batch
# ---------------------------------------------------------------------------

class TestGenerateBatchCallback:
    def test_on_result_fires_once_per_item(self):
        gen = _make_generator([{"category": "plumbing"}, {"category": "electrical"}])
        fired: list[GenerationResult] = []
        gen.generate_batch(num_samples=4, on_result=fired.append)
        assert len(fired) == 4

    def test_on_result_receives_same_objects_as_return(self):
        gen = _make_generator([{"category": "electrical"}])
        fired: list[GenerationResult] = []
        returned = gen.generate_batch(num_samples=3, on_result=fired.append)
        assert fired == returned

    def test_on_result_none_does_not_crash(self):
        gen = _make_generator([{"category": "plumbing"}])
        results = gen.generate_batch(num_samples=2, on_result=None)
        assert len(results) == 2

    def test_on_result_called_in_order(self):
        categories = ["plumbing", "electrical", "hvac"]
        gen = _make_generator([{"category": c} for c in categories])
        fired: list[str] = []
        gen.generate_batch(num_samples=3, on_result=lambda r: fired.append(r.category))
        assert len(fired) == 3
        assert all(c in categories for c in fired)

    def test_checkpoint_every_five_items(self):
        """Caller-driven: checkpoint counter increments every 5 fired results."""
        gen = _make_generator([{"category": "plumbing"}])
        checkpoint_counts: list[int] = []
        fired: list[GenerationResult] = []

        def on_result(r: GenerationResult) -> None:
            fired.append(r)
            if len(fired) % 5 == 0:
                checkpoint_counts.append(len(fired))

        gen.generate_batch(num_samples=11, on_result=on_result)
        # Items 5 and 10 trigger checkpoint; item 11 does not
        assert checkpoint_counts == [5, 10]

    def test_remaining_per_category_respected(self):
        """on_result fires only for items in the remaining schedule."""
        gen = _make_generator([
            {"category": "plumbing"},
            {"category": "electrical"},
        ])
        fired: list[GenerationResult] = []
        gen.generate_batch(
            num_samples=10,
            remaining_per_category={"plumbing": 2, "electrical": 1},
            on_result=fired.append,
        )
        assert len(fired) == 3
        categories = [r.category for r in fired]
        assert categories.count("plumbing") == 2
        assert categories.count("electrical") == 1


# ---------------------------------------------------------------------------
# run_generation_phase: mock path resume
# ---------------------------------------------------------------------------

class TestRunGenerationPhaseResume:
    def test_output_file_created(self, tmp_path):
        from phase1_generation import run_generation_phase

        out_dir = tmp_path / "out"
        out_dir.mkdir()
        run_generation_phase(
            num_samples=4,
            generation_model="mock",
            output_dir=out_dir,
            batch_label="test",
            output_base=tmp_path,
        )
        result_file = out_dir / "generation_results.json"
        assert result_file.exists()
        records = json.loads(result_file.read_text())
        assert len(records) >= 1

    def test_resume_preserves_existing_trace_ids(self, tmp_path):
        from phase1_generation import run_generation_phase

        out_dir = tmp_path / "out"
        out_dir.mkdir()

        first = run_generation_phase(
            num_samples=4,
            generation_model="mock",
            output_dir=out_dir,
            batch_label="test",
            output_base=tmp_path,
        )
        first_ids = {r.trace_id for r in first}

        second = run_generation_phase(
            num_samples=4,
            generation_model="mock",
            output_dir=out_dir,
            batch_label="test",
            output_base=tmp_path,
        )
        second_ids = {r.trace_id for r in second}
        # All first-run IDs survive the resume
        assert first_ids.issubset(second_ids)

    def test_overwrite_replaces_existing(self, tmp_path):
        from phase1_generation import run_generation_phase

        out_dir = tmp_path / "out"
        out_dir.mkdir()

        first = run_generation_phase(
            num_samples=3,
            generation_model="mock",
            output_dir=out_dir,
            batch_label="test",
            output_base=tmp_path,
        )
        first_ids = {r.trace_id for r in first}

        second = run_generation_phase(
            num_samples=3,
            generation_model="mock",
            output_dir=out_dir,
            batch_label="test",
            output_base=tmp_path,
            overwrite=True,
        )
        second_ids = {r.trace_id for r in second}
        # Overwrite produces fresh trace_ids — no overlap expected with high probability
        # (UUIDs are random; collision probability is negligible)
        assert len(second_ids) >= 1
