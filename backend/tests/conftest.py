import json
from pathlib import Path

import pytest

EXAMPLES_DIR = Path(__file__).resolve().parent / "example_htmls"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def examples_dir() -> Path:
    return EXAMPLES_DIR


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return FIXTURES_DIR


def example_html(glob: str) -> str:
    matches = [p for p in EXAMPLES_DIR.glob(glob) if p.is_file()]
    assert matches, f"no example html for pattern: {glob}"
    return matches[0].read_text(encoding="utf-8", errors="replace")


def fixture_json(name: str) -> dict:
    path = FIXTURES_DIR / name
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return json.loads((EXAMPLES_DIR / name).read_text(encoding="utf-8"))
