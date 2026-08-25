from __future__ import annotations

import math
import os
import signal
import subprocess
import tempfile
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from rolo.runtime_context import admitted_runtime_environment


@dataclass(frozen=True)
class AdapterProcessResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False
    output_limited: bool = False


class AdapterRunner(Protocol):
    """Deployment boundary used for every generated-adapter process."""

    def run(
        self,
        command: list[str],
        *,
        stdin: str = "",
        cwd: Path,
        timeout_s: float,
        max_stdout_bytes: int = 1_000_000,
        max_stderr_bytes: int = 1_000_000,
        runtime_environment: Mapping[str, str] | None = None,
    ) -> AdapterProcessResult: ...


_INHERITED_ENVIRONMENT = {
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "WINDIR",
}

# ML-backed robot CLIs commonly reserve multi-gigabyte virtual mappings while
# keeping a much smaller resident set.  Four GiB admits LeRobot's bounded
# camera inventory import path without relaxing CPU, process, file, output, or
# wall-clock limits.
_ADAPTER_MAX_ADDRESS_SPACE_BYTES = 4 * 1024 * 1024 * 1024
_ADAPTER_MAX_PROCESSES_AND_THREADS = 128

def sanitized_adapter_environment(
    private_home: Path,
    runtime_environment: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return the minimal non-secret environment visible to generated code."""
    environment = {
        name: value
        for name in _INHERITED_ENVIRONMENT
        if (value := os.environ.get(name)) is not None
    }
    private = str(private_home)
    environment.update(
        {
            "HOME": private,
            "USERPROFILE": private,
            "TMP": private,
            "TEMP": private,
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    admitted = admitted_runtime_environment(runtime_environment or {})
    target_path = admitted.pop("PATH", None)
    if target_path:
        inherited_path = environment.get("PATH")
        environment["PATH"] = (
            os.pathsep.join([target_path, inherited_path])
            if inherited_path
            else target_path
        )
    environment.update(admitted)
    return environment


class BoundedAdapterRunner:
    """Run generated adapters through a protected OS sandbox launcher.

    The launcher contract is ``launcher --cwd <release-root> -- <adapter argv...>``.
    Production defaults fail closed when no launcher is configured. The explicit
    development escape hatch exists for tests and offline demos only.
    """

    def __init__(
        self,
        *,
        sandbox_launcher: Path | None = None,
        allow_unsandboxed_development: bool | None = None,
    ) -> None:
        from rolo.core.config import get_settings

        settings = get_settings()
        self.sandbox_launcher = sandbox_launcher or settings.rolo_adapter_sandbox_launcher
        if allow_unsandboxed_development is None:
            allow_unsandboxed_development = settings.rolo_adapter_unsandboxed_dev
        self.allow_unsandboxed_development = allow_unsandboxed_development

    def run(
        self,
        command: list[str],
        *,
        stdin: str = "",
        cwd: Path,
        timeout_s: float,
        max_stdout_bytes: int = 1_000_000,
        max_stderr_bytes: int = 1_000_000,
        runtime_environment: Mapping[str, str] | None = None,
    ) -> AdapterProcessResult:
        if not command or not all(isinstance(item, str) and item for item in command):
            raise ValueError("adapter runner command must be a non-empty argv list")
        if timeout_s <= 0:
            raise ValueError("adapter runner timeout must be positive")
        if max_stdout_bytes < 1 or max_stderr_bytes < 1:
            raise ValueError("adapter runner output limits must be positive")
        root = cwd.resolve()
        if not root.is_dir():
            raise ValueError(f"adapter runner cwd is not a directory: {root}")
        launch_command = self._sandbox_command(command, root)

        with tempfile.TemporaryDirectory(prefix="rolo-adapter-home-") as temporary_home:
            process = subprocess.Popen(
                launch_command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=root,
                env=sanitized_adapter_environment(
                    Path(temporary_home), runtime_environment
                ),
                **self._platform_process_options(timeout_s),
            )
            assert process.stdin is not None
            assert process.stdout is not None
            assert process.stderr is not None
            stdout = bytearray()
            stderr = bytearray()
            exceeded = threading.Event()

            def read_bounded(stream: object, target: bytearray, limit: int) -> None:
                while True:
                    chunk = stream.read(65536)  # type: ignore[attr-defined]
                    if not chunk:
                        return
                    remaining = max(0, limit - len(target))
                    target.extend(chunk[:remaining])
                    if len(chunk) > remaining:
                        exceeded.set()

            readers = [
                threading.Thread(
                    target=read_bounded,
                    args=(process.stdout, stdout, max_stdout_bytes),
                    daemon=True,
                ),
                threading.Thread(
                    target=read_bounded,
                    args=(process.stderr, stderr, max_stderr_bytes),
                    daemon=True,
                ),
            ]
            for reader in readers:
                reader.start()
            try:
                process.stdin.write(stdin.encode("utf-8"))
                process.stdin.close()
            except (BrokenPipeError, OSError):
                pass

            deadline = time.monotonic() + timeout_s
            timed_out = False
            while process.poll() is None:
                if exceeded.is_set():
                    self._terminate_tree(process)
                    break
                if time.monotonic() >= deadline:
                    timed_out = True
                    self._terminate_tree(process)
                    break
                time.sleep(0.01)
            try:
                returncode = process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._terminate_tree(process)
                returncode = process.wait(timeout=2)
            for reader in readers:
                reader.join(timeout=2)
            return AdapterProcessResult(
                returncode=returncode,
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                timed_out=timed_out,
                output_limited=exceeded.is_set(),
            )

    def _sandbox_command(self, command: list[str], cwd: Path) -> list[str]:
        if self.sandbox_launcher is None:
            if self.allow_unsandboxed_development:
                return command
            raise RuntimeError(
                "generated adapter execution requires ROLO_ADAPTER_SANDBOX_LAUNCHER; "
                "ROLO_ADAPTER_UNSANDBOXED_DEV=1 is restricted to tests and offline demos"
            )
        from rolo.invocation_policy import validate_protected_file

        try:
            launcher = validate_protected_file(
                self.sandbox_launcher,
                label="adapter sandbox launcher",
            )
        except ValueError as exc:
            raise RuntimeError(str(exc)) from exc
        if os.name != "nt" and not os.access(launcher, os.X_OK):
            raise RuntimeError("adapter sandbox launcher must be executable")
        return [str(launcher), "--cwd", str(cwd), "--", *command]

    @staticmethod
    def _platform_process_options(timeout_s: float) -> dict[str, object]:
        if os.name == "nt":
            return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}

        def limits() -> None:
            os.setsid()
            try:
                import resource

                cpu = max(1, math.ceil(timeout_s) + 1)
                resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
                resource.setrlimit(resource.RLIMIT_FSIZE, (16 * 1024 * 1024,) * 2)
                resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
                if hasattr(resource, "RLIMIT_NPROC"):
                    resource.setrlimit(
                        resource.RLIMIT_NPROC,
                        (_ADAPTER_MAX_PROCESSES_AND_THREADS,) * 2,
                    )
                if hasattr(resource, "RLIMIT_AS"):
                    resource.setrlimit(
                        resource.RLIMIT_AS,
                        (_ADAPTER_MAX_ADDRESS_SPACE_BYTES,) * 2,
                    )
            except (ImportError, OSError, ValueError):
                pass

        return {"preexec_fn": limits}

    @staticmethod
    def _terminate_tree(process: subprocess.Popen[bytes]) -> None:
        if process.poll() is not None:
            return
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                check=False,
                env=sanitized_adapter_environment(Path(tempfile.gettempdir())),
            )
            if process.poll() is None:
                process.kill()
            return
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            process.kill()
