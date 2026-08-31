from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from rolo.stages.adapt.agent_environment import (
    codex_helper_environment,
    preflight_codex_helper,
)
from rolo.stages.network_preflight import AgentNetworkPreflight


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


def test_codex_helper_preflight_checks_same_environment_and_login(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}
    environment = {"PATH": "/fixture/bin", "HTTPS_PROXY": "http://proxy.test:7897"}
    monkeypatch.setattr(
        "rolo.stages.adapt.agent_environment.shutil.which",
        lambda executable, path: "/fixture/bin/codex",
    )
    monkeypatch.setattr(
        "rolo.stages.adapt.agent_environment.preflight_agent_network",
        lambda url, *, timeout_s, environment: observed.update(
            {"url": url, "timeout_s": timeout_s, "environment": environment}
        )
        or AgentNetworkPreflight("proxy.test", 7897, True),
    )
    monkeypatch.setattr(
        "rolo.stages.adapt.agent_environment.subprocess.run",
        lambda command, **kwargs: observed.update(
            {"command": command, "login_environment": kwargs["env"]}
        )
        or subprocess.CompletedProcess(command, 0),
    )

    result = preflight_codex_helper(
        executable="codex",
        provider="codex",
        base_url=None,
        api_key=None,
        environment=environment,
        timeout_s=3,
    )

    assert result.auth_mode == "chatgpt_login"
    assert result.via_proxy is True
    assert observed["environment"] is environment
    assert observed["login_environment"] == environment
    assert observed["command"] == ["/fixture/bin/codex", "login", "status"]


def test_codex_helper_preflight_classifies_network_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "rolo.stages.adapt.agent_environment.shutil.which",
        lambda executable, path: "/fixture/bin/codex",
    )
    monkeypatch.setattr(
        "rolo.stages.adapt.agent_environment.preflight_agent_network",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            ValueError("Agent network endpoint preflight failed: TimeoutError")
        ),
    )

    with pytest.raises(ValueError, match="readiness failed.*network endpoint"):
        preflight_codex_helper(
            executable="codex",
            provider="codex",
            base_url=None,
            api_key=None,
            environment={"PATH": "/fixture/bin"},
            timeout_s=3,
        )
