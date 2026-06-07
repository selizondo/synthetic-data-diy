"""Pytest fixtures for synthetic-data-diy tests."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_huggingface_dataset():
    """Mock HuggingFace dataset loading to avoid network calls in CI."""

    # Sample benchmark data: 3 categories, 3 items per category
    mock_data = [
        {"question": "How to fix a leaky tap?", "answer": "Turn off water supply and replace washer.", "category": 0},  # plumbing
        {"question": "How to patch drywall?", "answer": "Fill hole with spackling compound.", "category": 0},
        {"question": "How to caulk a window?", "answer": "Apply silicone caulk around frame edges.", "category": 0},
        {
            "question": "How to wire an outlet?",
            "answer": "Turn off power, connect wires to terminals.",
            "category": 1,
        },  # electrical
        {"question": "How to install a light switch?", "answer": "Turn off power, connect white/black wires.", "category": 1},
        {"question": "How to fix a tripped breaker?", "answer": "Identify overloaded circuit, reset breaker.", "category": 1},
        {"question": "How to stain wood?", "answer": "Sand surface, apply stain, let dry.", "category": 2},  # carpentry
        {"question": "How to build a shelf?", "answer": "Cut wood, drill holes, install brackets.", "category": 2},
        {"question": "How to fix a squeaky door?", "answer": "Apply lubricant to hinges.", "category": 2},
    ]

    # Create mock dataset object
    mock_dataset = MagicMock()
    mock_dataset.__iter__ = lambda self: iter(mock_data)
    mock_dataset.__len__ = lambda self: len(mock_data)
    mock_dataset.features = {"category": MagicMock(names=["plumbing", "electrical", "carpentry"])}
    mock_dataset.class_encode_column = MagicMock(return_value=mock_dataset)

    def mock_load_dataset(dataset_name, split=None):
        if dataset_name == "dipenbhuva/home-diy-repair-qa":
            return mock_dataset
        raise ValueError(f"Unknown dataset: {dataset_name}")

    with patch("datasets.load_dataset", side_effect=mock_load_dataset):
        yield
