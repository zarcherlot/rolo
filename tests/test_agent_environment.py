from __future__ import annotations

from pathlib import Path

from rolo.stages.adapt.agent_environment import codex_helper_environment


def test_codex_helper_environment_is_allowlisted_and_case_deterministic(
    monkeypatch, tmp_path: Path
) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.delenv("HOME", raising=False)
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.setenv("HTTPS_PROXY", "http://upper.example")
    monkeypatch.setenv("https_proxy", "http://lower.example")
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-leak")

    environment = codex_helper_environment(api_key="explicit-key")

    assert environment["HOME"] == str(tmp_path)
    assert environment["CODEX_HOME"] == str(codex_home)
    assert environment["HTTPS_PROXY"] == "http://lower.example"
    assert environment["CODEX_API_KEY"] == "explicit-key"
    assert "OPENAI_API_KEY" not in environment


def test_codex_helper_environment_returns_stable_key_order(monkeypatch) -> None:
    monkeypatch.setenv("PATH", "fixture-path")
    monkeypatch.setenv("TEMP", "fixture-temp")

    environment = codex_helper_environment()

    assert list(environment) == sorted(environment)
