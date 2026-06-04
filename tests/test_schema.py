"""
Unit tests for the QAPair schema and field validators.

Tests cover: required 7 fields, min-length constraints (steps ≥ 3,
tools_required ≥ 1, tips ≥ 1), and the strip_whitespace / strip_list_items
validators.
"""

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from schema import QAPair


def _valid_qa(**overrides) -> dict:
    base = {
        "question": "How do I fix a dripping faucet in my kitchen?",
        "answer": "Turn off the water supply valve under the sink. Remove the faucet handle by unscrewing the set screw. Replace the worn cartridge or washer. Reassemble and test. Safety: water will spray if supply is not off.",
        "equipment_problem": "Dripping kitchen faucet",
        "tools_required": ["adjustable wrench", "screwdriver"],
        "steps": [
            "Turn off the water supply valve under the sink",
            "Remove the faucet handle by unscrewing the set screw",
            "Replace the worn cartridge or washer",
        ],
        "safety_info": "Turn off the main water supply before starting — water will spray if the valve is not fully closed.",
        "tips": ["Photograph the disassembly order so you can reassemble correctly"],
    }
    base.update(overrides)
    return base


class TestQAPairHappyPath:
    def test_valid_item_creates_without_error(self):
        qa = QAPair(**_valid_qa())
        assert qa.question.startswith("How do I fix")
        assert len(qa.steps) == 3
        assert len(qa.tools_required) == 2

    def test_strip_whitespace_applied_to_question(self):
        qa = QAPair(**_valid_qa(question="  How do I fix a dripping faucet?  "))
        assert not qa.question.startswith(" ")
        assert not qa.question.endswith(" ")

    def test_strip_whitespace_applied_to_safety_info(self):
        qa = QAPair(**_valid_qa(safety_info="  Always turn off the water supply before starting repairs to avoid flooding.  "))
        assert not qa.safety_info.startswith(" ")

    def test_strip_list_items_removes_whitespace_from_steps(self):
        qa = QAPair(
            **_valid_qa(
                steps=[
                    "  Step one  ",
                    "Step two",
                    "  Step three  ",
                ]
            )
        )
        assert qa.steps[0] == "Step one"
        assert qa.steps[2] == "Step three"


class TestQAPairFieldConstraints:
    def test_question_too_short_raises(self):
        with pytest.raises(ValidationError):
            QAPair(**_valid_qa(question="Short?"))

    def test_answer_too_short_raises(self):
        with pytest.raises(ValidationError):
            QAPair(**_valid_qa(answer="Too short"))

    def test_equipment_problem_too_short_raises(self):
        with pytest.raises(ValidationError):
            QAPair(**_valid_qa(equipment_problem="Tap"))

    def test_safety_info_too_short_raises(self):
        with pytest.raises(ValidationError):
            QAPair(**_valid_qa(safety_info="Be safe"))

    def test_tools_required_empty_list_raises(self):
        with pytest.raises(ValidationError):
            QAPair(**_valid_qa(tools_required=[]))

    def test_steps_fewer_than_three_raises(self):
        with pytest.raises(ValidationError):
            QAPair(**_valid_qa(steps=["Step 1", "Step 2"]))

    def test_tips_empty_list_raises(self):
        with pytest.raises(ValidationError):
            QAPair(**_valid_qa(tips=[]))

    def test_steps_exactly_three_passes(self):
        qa = QAPair(**_valid_qa())
        assert len(qa.steps) == 3

    def test_tools_single_item_passes(self):
        qa = QAPair(**_valid_qa(tools_required=["adjustable wrench"]))
        assert len(qa.tools_required) == 1

    def test_tips_single_item_passes(self):
        qa = QAPair(**_valid_qa(tips=["Wrap pipe threads with Teflon tape to prevent leaks"]))
        assert len(qa.tips) == 1


class TestQAPairNonEmptyValidator:
    def test_blank_question_raises(self):
        with pytest.raises(ValidationError):
            QAPair(**_valid_qa(question="          "))

    def test_blank_answer_raises(self):
        with pytest.raises(ValidationError):
            QAPair(**_valid_qa(answer="          "))
