import json
from pathlib import Path

import pytest

from src.models.vn import Script

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def locked_granary_data() -> dict:
    with open(FIXTURES_DIR / "locked_granary.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def locked_granary(locked_granary_data: dict) -> Script:
    return Script.model_validate(locked_granary_data)
