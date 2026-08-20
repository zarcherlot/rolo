from __future__ import annotations

import math
import os
import signal
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


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


def sanitized_adapter_environment(private_home: Path) -> dict[str, str]:
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
    return environment


class BoundedAdapterRunner:
    """Portable baseline runner with bounded I/O and a sanitized environment."""

    def run(
        self,
        command: list[str],
        *,
        stdin: str = "",
        cwd: Path,
        timeout_s: float,
        max_stdout_bytes: int = 1_000_000,
        max_stderr_bytes: int = 1_000_000,
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

        with tempfile.TemporaryDirectory(prefix="rolo-adapter-home-") as temporary_home:
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=root,
                env=sanitized_adapter_environment(Path(temporary_home)),
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
                    resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
                if hasattr(resource, "RLIMIT_AS"):
                    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
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
