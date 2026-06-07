"""Pytest fixtures for synthetic-data-diy tests."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_huggingface_dataset():
    """Mock HuggingFace dataset loading to avoid network calls in CI."""

    # Sample benchmark data matching QAPair schema requirements
    mock_data = [
        {
            "question": "How do I fix a leaky kitchen faucet?",
            "answer": ("Turn off water supply under sink, remove faucet handle, replace the worn washer, and reassemble."),
            "equipment_problem": "Leaking faucet",
            "tools_required": ["wrench", "screwdriver", "washer"],
            "steps": [
                "Turn off water supply under sink",
                "Remove faucet handle with screwdriver",
                "Replace washer and reassemble",
            ],
            "safety_info": "Turn off water supply before starting to prevent damage.",
            "tips": ["Use an adjustable wrench for better grip"],
            "category": 0,
        },
        {
            "question": "What is the best way to patch drywall holes?",
            "answer": ("For small holes use spackling compound. Apply with putty knife, let dry, sand smooth, and paint."),
            "equipment_problem": "Drywall hole",
            "tools_required": ["putty knife", "sandpaper"],
            "steps": [
                "Clean hole edges and remove loose material",
                "Apply spackling compound with putty knife",
                "Sand smooth once dry and paint",
            ],
            "safety_info": "Wear dust mask when sanding to avoid inhaling dust.",
            "tips": ["Apply two thin coats rather than one thick coat"],
            "category": 0,
        },
        {
            "question": "How do I caulk around a window properly?",
            "answer": (
                "Clean the gap between window and frame. Apply painter tape. Use caulk gun to apply silicone in smooth bead."
            ),
            "equipment_problem": "Window seal",
            "tools_required": ["caulk gun", "caulk", "painter tape"],
            "steps": [
                "Clean gap and apply painter tape",
                "Load caulk into caulk gun",
                "Apply steady bead and smooth with wet finger",
            ],
            "safety_info": "Ensure good ventilation when using silicone caulk.",
            "tips": ["Use acrylic for paintable or silicone for waterproof"],
            "category": 0,
        },
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
