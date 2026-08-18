from collections.abc import Iterator
from pathlib import Path

import pytest

from rolo.core.config import get_settings


@pytest.fixture(autouse=True)
def repository_demo_config(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Keep engineering tests explicit about their checked-in demo robot registry."""
    monkeypatch.setenv("ROLO_CONFIG_DIR", str(Path("tests/fixtures")))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
