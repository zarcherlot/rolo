from __future__ import annotations

from pathlib import Path

import pytest

from rolo.user_identity import current_user_session_fingerprint, current_user_session_id


def test_session_id_is_durable_and_fingerprint_is_stable(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("ROLO_SESSION_ID", raising=False)
    first = current_user_session_id(tmp_path)
    second = current_user_session_id(tmp_path)
    assert first == second
    assert first.startswith("session-")
    assert current_user_session_fingerprint(tmp_path) == current_user_session_fingerprint(tmp_path)


def test_invalid_configured_session_is_rejected(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ROLO_SESSION_ID", "forged-session")
    with pytest.raises(ValueError, match="session-<32 hex characters"):
        current_user_session_id(tmp_path)
