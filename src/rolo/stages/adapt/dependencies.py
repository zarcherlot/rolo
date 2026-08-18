from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

from rolo.core.artifacts import ArtifactStore
from rolo.stages.adapt.models import (
    AdapterAgentConfig,
    AdapterAgentDependencyReport,
    AdapterAgentDependencyStatus,
)

CODEX_INSTALL_URL = "https://chatgpt.com/codex/install.sh"
MAX_INSTALLER_BYTES = 4 * 1024 * 1024


class CodexDependencyAdapter:
    """Install and verify the allowlisted official Codex CLI dependency."""

    name = "codex"
    install_source = CODEX_INSTALL_URL

    def resolve(self, configured: str, home: Path) -> Path | None:
        configured_path = Path(configured).expanduser()
        if configured_path.is_absolute() and configured_path.is_file():
            return configured_path.resolve()
        discovered = shutil.which(configured)
        if discovered:
            return Path(discovered).resolve()
        conventional = home / ".local" / "bin" / "codex"
        return conventional.resolve() if conventional.is_file() else None

    def install(self, *, home: Path, codex_home: Path, timeout_s: int) -> None:
        if platform.system() != "Linux":
            raise RuntimeError("Automatic Codex installation is supported only on Linux")
        home.mkdir(parents=True, exist_ok=True)
        codex_home.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(
            CODEX_INSTALL_URL,
            headers={"User-Agent": "rolo-coding-agent-installer/1"},
        )
        with urllib.request.urlopen(request, timeout=min(timeout_s, 60)) as response:
            installer = response.read(MAX_INSTALLER_BYTES + 1)
        if not installer or len(installer) > MAX_INSTALLER_BYTES:
            raise RuntimeError("Official Codex installer was empty or exceeded the size limit")
        if b"#!/" not in installer[:128]:
            raise RuntimeError("Official Codex installer did not look like an executable script")
        allowed_environment = {
            "PATH",
            "SHELL",
            "USER",
            "LOGNAME",
            "TMPDIR",
            "TMP",
            "TEMP",
            "LANG",
            "LC_ALL",
            "SSL_CERT_FILE",
            "CODEX_CA_CERTIFICATE",
            "HTTPS_PROXY",
            "HTTP_PROXY",
            "NO_PROXY",
        }
        environment = {
            key: value for key, value in os.environ.items() if key in allowed_environment
        }
        environment["HOME"] = str(home)
        environment["CODEX_HOME"] = str(codex_home)
        with tempfile.TemporaryDirectory(prefix="rolo-codex-install-") as temporary:
            script = Path(temporary) / "install.sh"
            script.write_bytes(installer)
            script.chmod(0o700)
            completed = subprocess.run(
                ["sh", str(script)],
                capture_output=True,
                check=False,
                env=environment,
                timeout=timeout_s,
            )
        if completed.returncode != 0:
            raise RuntimeError(f"Official Codex installer exited with code {completed.returncode}")

    def version(self, executable: Path, *, environment: dict[str, str]) -> str | None:
        completed = subprocess.run(
            [str(executable), "--version"],
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
            timeout=15,
        )
        if completed.returncode != 0:
            return None
        value = completed.stdout.strip().splitlines()
        return value[0][:200] if value else None

    def authenticated(self, executable: Path, *, environment: dict[str, str]) -> bool:
        completed = subprocess.run(
            [str(executable), "login", "status"],
            capture_output=True,
            check=False,
            env=environment,
            timeout=30,
        )
        return completed.returncode == 0


class AdapterAgentDependencyManager:
    """Resolve, install, verify, and audit the configured Adapter Agent dependency."""

    def __init__(
        self,
        artifacts: ArtifactStore,
        *,
        adapter: CodexDependencyAdapter | None = None,
    ) -> None:
        self.artifacts = artifacts
        self.adapter = adapter or CodexDependencyAdapter()

    def prepare(
        self,
        *,
        config: AdapterAgentConfig,
        executable: str,
        auto_install: bool,
        require_auth: bool,
        install_timeout_s: int,
        install_home: Path | None = None,
        codex_home: Path | None = None,
    ) -> tuple[AdapterAgentDependencyReport, Path]:
        system = platform.system()
        architecture = platform.machine()
        home = (
            install_home or Path(os.environ.get("HOME") or Path.home())
        ).expanduser().resolve()
        resolved_codex_home = (codex_home or home / ".codex").expanduser().resolve()
        install_attempted = False
        messages: list[str] = []

        if install_timeout_s < 1:
            report = self._report(
                config=config,
                status=AdapterAgentDependencyStatus.FAILED,
                system=system,
                architecture=architecture,
                messages=["Adapter Agent install timeout must be at least one second"],
            )
            return report, self._write(report)

        if config.executor.strip().lower() != self.adapter.name:
            report = self._report(
                config=config,
                status=AdapterAgentDependencyStatus.UNSUPPORTED,
                system=system,
                architecture=architecture,
                messages=[f"No allowlisted installer for executor {config.executor}"],
            )
            return report, self._write(report)

        resolved = self.adapter.resolve(executable, home)
        if resolved is None and auto_install:
            install_attempted = True
            try:
                self.adapter.install(
                    home=home,
                    codex_home=resolved_codex_home,
                    timeout_s=install_timeout_s,
                )
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
                report = self._report(
                    config=config,
                    status=AdapterAgentDependencyStatus.FAILED,
                    system=system,
                    architecture=architecture,
                    install_attempted=True,
                    messages=[str(exc)],
                )
                return report, self._write(report)
            resolved = self.adapter.resolve(executable, home)

        if resolved is None:
            status = (
                AdapterAgentDependencyStatus.FAILED
                if install_attempted
                else AdapterAgentDependencyStatus.INSTALL_REQUIRED
            )
            messages.append("Configured Adapter Agent executable is not installed")
            report = self._report(
                config=config,
                status=status,
                system=system,
                architecture=architecture,
                install_attempted=install_attempted,
                messages=messages,
            )
            return report, self._write(report)

        environment = os.environ.copy()
        for name in ("CODING_AGENT_API_KEY", "CODEX_API_KEY", "OPENAI_API_KEY"):
            environment.pop(name, None)
        environment["CODEX_HOME"] = str(resolved_codex_home)
        version = self.adapter.version(resolved, environment=environment)
        if version is None:
            report = self._report(
                config=config,
                status=AdapterAgentDependencyStatus.FAILED,
                system=system,
                architecture=architecture,
                executable=str(resolved),
                installed=True,
                install_attempted=install_attempted,
                messages=["Adapter Agent executable did not return a valid version"],
            )
            return report, self._write(report)

        if not require_auth:
            report = self._report(
                config=config,
                status=(
                    AdapterAgentDependencyStatus.INSTALLED
                    if install_attempted
                    else AdapterAgentDependencyStatus.READY
                ),
                system=system,
                architecture=architecture,
                executable=str(resolved),
                version=version,
                installed=True,
                install_attempted=install_attempted,
                authentication="NOT_CHECKED",
            )
            return report, self._write(report)

        if config.api_key_configured:
            report = self._report(
                config=config,
                status=AdapterAgentDependencyStatus.READY,
                system=system,
                architecture=architecture,
                executable=str(resolved),
                version=version,
                installed=True,
                install_attempted=install_attempted,
                authentication="API_KEY_CONFIGURED",
            )
            return report, self._write(report)

        authenticated = self.adapter.authenticated(resolved, environment=environment)
        report = self._report(
            config=config,
            status=(
                AdapterAgentDependencyStatus.READY
                if authenticated
                else AdapterAgentDependencyStatus.AUTH_REQUIRED
            ),
            system=system,
            architecture=architecture,
            executable=str(resolved),
            version=version,
            installed=True,
            install_attempted=install_attempted,
            authentication="AUTHENTICATED" if authenticated else "REQUIRED",
            messages=(
                []
                if authenticated
                else ["Run codex login --device-auth as the same operating-system user"]
            ),
        )
        return report, self._write(report)

    def _report(
        self,
        *,
        config: AdapterAgentConfig,
        status: AdapterAgentDependencyStatus,
        system: str,
        architecture: str,
        executable: str | None = None,
        version: str | None = None,
        installed: bool = False,
        install_attempted: bool = False,
        authentication: str = "NOT_CHECKED",
        messages: list[str] | None = None,
    ) -> AdapterAgentDependencyReport:
        return AdapterAgentDependencyReport(
            executor=config.executor,
            provider=config.provider,
            status=status,
            platform=system,
            architecture=architecture,
            executable=executable,
            version=version,
            installed=installed,
            install_attempted=install_attempted,
            install_source=(self.adapter.install_source if install_attempted else None),
            authentication=authentication,
            messages=messages or [],
        )

    def _write(self, report: AdapterAgentDependencyReport) -> Path:
        return self.artifacts.write_json(
            "coding-agent/dependency/latest.json", report.model_dump(mode="json")
        )
