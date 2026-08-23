from collections.abc import Iterator
from pathlib import Path

import pytest

from rolo.core.config import get_settings


@pytest.fixture(autouse=True)
def repository_demo_config(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Keep engineering tests explicit about their checked-in demo robot registry."""
    monkeypatch.setenv("ROLO_CONFIG_DIR", str(Path("tests/fixtures")))
    # Unit tests opt into Agent orchestration explicitly; never launch a real provider by default.
    monkeypatch.setenv("ADAPT_HEURISTIC_AGENT_MODE", "disabled")
    # Generated adapter unit fixtures are intentionally executed without an OS sandbox. Production
    # defaults remain fail-closed and are covered by a dedicated runner test.
    monkeypatch.setenv("ROLO_ADAPTER_UNSANDBOXED_DEV", "1")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
