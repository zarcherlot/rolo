import subprocess
from pathlib import Path

import pytest

from rolo.core.artifacts import ArtifactStore
from rolo.stages.adapt.dependencies import (
    CODEX_INSTALL_URL,
    AdapterAgentDependencyManager,
    CodexDependencyAdapter,
)
from rolo.stages.adapt.models import AdapterAgentConfig


class FakeCodexAdapter:
    name = "codex"
    install_source = "https://example.invalid/allowlisted-installer"

    def __init__(self, executable: Path, *, installed: bool, authenticated: bool) -> None:
        self.executable = executable
        self.installed = installed
        self.is_authenticated = authenticated
        self.install_calls = 0

    def resolve(self, configured: str, home: Path) -> Path | None:
        del configured, home
        return self.executable if self.installed else None

    def install(self, *, home: Path, codex_home: Path, timeout_s: int) -> None:
        del home, codex_home, timeout_s
        self.install_calls += 1
        self.installed = True

    def version(self, executable: Path, *, environment: dict[str, str]) -> str | None:
        del executable, environment
        return "codex-cli test-version"

    def authenticated(self, executable: Path, *, environment: dict[str, str]) -> bool:
        del executable, environment
        return self.is_authenticated


def test_prepare_auto_installs_and_writes_secret_free_audit(tmp_path: Path) -> None:
    adapter = FakeCodexAdapter(tmp_path / "codex", installed=False, authenticated=False)
    manager = AdapterAgentDependencyManager(
        ArtifactStore(tmp_path / "artifacts"), adapter=adapter  # type: ignore[arg-type]
    )

    report, artifact = manager.prepare(
        config=AdapterAgentConfig(),
        executable="codex",
        auto_install=True,
        require_auth=False,
        install_timeout_s=30,
        codex_home=tmp_path / "codex-home",
    )

    assert report.status == "INSTALLED"
    assert report.installed is True
    assert report.install_attempted is True
    assert report.authentication == "NOT_CHECKED"
    assert adapter.install_calls == 1
    assert artifact.is_file()


def test_prepare_blocks_execution_when_login_is_missing(tmp_path: Path) -> None:
    adapter = FakeCodexAdapter(tmp_path / "codex", installed=True, authenticated=False)
    manager = AdapterAgentDependencyManager(
        ArtifactStore(tmp_path / "artifacts"), adapter=adapter  # type: ignore[arg-type]
    )

    report, _ = manager.prepare(
        config=AdapterAgentConfig(),
        executable="codex",
        auto_install=True,
        require_auth=True,
        install_timeout_s=30,
    )

    assert report.status == "AUTH_REQUIRED"
    assert report.authentication == "REQUIRED"
    assert report.messages == [
        "Run codex login --device-auth as the same operating-system user"
    ]


def test_prepare_accepts_installed_and_authenticated_executor(tmp_path: Path) -> None:
    adapter = FakeCodexAdapter(tmp_path / "codex", installed=True, authenticated=True)
    manager = AdapterAgentDependencyManager(
        ArtifactStore(tmp_path / "artifacts"), adapter=adapter  # type: ignore[arg-type]
    )

    report, _ = manager.prepare(
        config=AdapterAgentConfig(),
        executable="codex",
        auto_install=True,
        require_auth=True,
        install_timeout_s=30,
    )

    assert report.status == "READY"
    assert report.version == "codex-cli test-version"
    assert report.authentication == "AUTHENTICATED"
    assert adapter.install_calls == 0


def test_prepare_accepts_explicit_key_without_persisting_it(tmp_path: Path) -> None:
    adapter = FakeCodexAdapter(tmp_path / "codex", installed=True, authenticated=False)
    manager = AdapterAgentDependencyManager(
        ArtifactStore(tmp_path / "artifacts"), adapter=adapter  # type: ignore[arg-type]
    )

    report, artifact = manager.prepare(
        config=AdapterAgentConfig(api_key_configured=True),
        executable="codex",
        auto_install=True,
        require_auth=True,
        install_timeout_s=30,
    )

    assert report.status == "READY"
    assert report.authentication == "API_KEY_CONFIGURED"
    assert "API_KEY_CONFIGURED" in artifact.read_text(encoding="utf-8")


def test_prepare_rejects_unregistered_executor(tmp_path: Path) -> None:
    adapter = FakeCodexAdapter(tmp_path / "codex", installed=True, authenticated=True)
    manager = AdapterAgentDependencyManager(
        ArtifactStore(tmp_path / "artifacts"), adapter=adapter  # type: ignore[arg-type]
    )

    report, _ = manager.prepare(
        config=AdapterAgentConfig(executor="unknown-agent"),
        executable="unknown-agent",
        auto_install=True,
        require_auth=True,
        install_timeout_s=30,
    )

    assert report.status == "UNSUPPORTED"
    assert report.install_attempted is False


def test_codex_install_uses_fixed_official_source_and_argv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    requested: list[str] = []
    commands: list[list[str]] = []

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> None:
            del args

        def read(self, limit: int) -> bytes:
            del limit
            return b"#!/bin/sh\nexit 0\n"

    def fake_urlopen(request: object, timeout: int) -> FakeResponse:
        del timeout
        requested.append(request.full_url)  # type: ignore[attr-defined]
        return FakeResponse()

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        del kwargs
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr("rolo.stages.adapt.dependencies.platform.system", lambda: "Linux")
    monkeypatch.setattr("rolo.stages.adapt.dependencies.urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("rolo.stages.adapt.dependencies.subprocess.run", fake_run)

    CodexDependencyAdapter().install(
        home=tmp_path / "home", codex_home=tmp_path / "codex", timeout_s=30
    )

    assert requested == [CODEX_INSTALL_URL]
    assert commands[0][0] == "sh"
    assert len(commands[0]) == 2


def test_codex_install_rejects_non_linux_before_downloading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("rolo.stages.adapt.dependencies.platform.system", lambda: "Windows")

    with pytest.raises(RuntimeError, match="supported only on Linux"):
        CodexDependencyAdapter().install(
            home=tmp_path / "home", codex_home=tmp_path / "codex", timeout_s=30
        )
