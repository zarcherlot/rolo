"""Small target-side providers used by the v2 signed Probe bundle.

Provider IDs are implementation details. The public contract is a bounded
``ProbeResult`` for hardware, OS, and Middleware observations; Agents do not
depend on this module's provider names.
"""

from __future__ import annotations

import os
import platform
import re
import shlex
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from rolo.core.models import DiscoveryStatus, ProbeResult
from rolo.runtime_context import admitted_runtime_environment

MAX_OUTPUT_CHARS = 200_000
MAX_ITEMS = 512
MAX_MIDDLEWARE_SAMPLES = 2


def _read_text(path: Path, limit: int = 4096) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return None


def _run(
    argv: Sequence[str],
    *,
    timeout_s: float = 10.0,
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            list(argv),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
            env=dict(environment) if environment is not None else None,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "available": True,
            "returncode": None,
            "stdout": (exc.stdout or "")[:MAX_OUTPUT_CHARS],
            "stderr": (exc.stderr or "")[:MAX_OUTPUT_CHARS],
            "error": "command timed out",
        }
    except OSError as exc:
        return {
            "available": False,
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "error": str(exc),
        }
    return {
        "available": True,
        "returncode": completed.returncode,
        "stdout": (completed.stdout or "")[:MAX_OUTPUT_CHARS],
        "stderr": (completed.stderr or "")[:MAX_OUTPUT_CHARS],
        "error": None,
    }


def _failure(result: Mapping[str, Any]) -> str:
    return str(
        result.get("error")
        or result.get("stderr")
        or result.get("stdout")
        or "command failed"
    )[:1000]


def _os_release() -> dict[str, str]:
    path = Path("/etc/os-release")
    text = _read_text(path, 16_000) or ""
    values: dict[str, str] = {}
    for line in text.splitlines():
        key, separator, value = line.partition("=")
        if separator and key and re.fullmatch(r"[A-Z0-9_]+", key):
            values[key] = value.strip().strip('"')
    return values


def _device_tree_model() -> str | None:
    for path in (
        Path("/sys/firmware/devicetree/base/model"),
        Path("/sys/devices/virtual/dmi/id/product_name"),
    ):
        value = _read_text(path, 512)
        if value:
            return value.strip().rstrip("\x00")
    return None


def _driver_name(path: Path) -> str | None:
    try:
        return path.resolve().name if path.exists() else None
    except OSError:
        return None


def _resource_id(component: Mapping[str, Any]) -> str:
    if component.get("path"):
        return f"hardware_path:{component['path']}"
    return f"hardware_component:{component.get('kind')}:{component.get('name')}"


class HardwareProbe:
    """Collect bounded device-presence evidence without changing the target."""

    def run(
        self,
        *,
        robot_id: str = "unregistered",
        provider_path: Path | None = None,
    ) -> ProbeResult:
        data: dict[str, Any] = {
            "architecture": platform.machine().lower(),
            "processor": platform.processor() or None,
            "device_tree_model": _device_tree_model(),
            "devices": [],
            "components": [],
            "buses": {},
            "thermal_zones": [],
        }
        warnings: list[str] = []
        if platform.system() != "Linux":
            warnings.append("the current hardware provider has no /sys and /dev adapter")
        else:
            patterns = {
                "camera": ("video*",),
                "serial": ("ttyUSB*", "ttyACM*", "ttyTHS*"),
                "input": ("input/event*",),
                "i2c": ("i2c-*",),
            }
            for modality, values in patterns.items():
                for pattern in values:
                    for path in sorted(Path("/dev").glob(pattern))[:MAX_ITEMS]:
                        component = {
                            "kind": "sensor" if modality in {"camera", "input"} else "interface",
                            "name": path.name,
                            "modality": modality,
                            "path": str(path),
                            "source": "device-presence",
                        }
                        if modality == "camera":
                            component["model"] = (
                                _read_text(
                                    Path("/sys/class/video4linux") / path.name / "name", 256
                                )
                                or ""
                            ).strip() or None
                        component["driver"] = _driver_name(
                            Path("/sys/class")
                            / modality
                            / path.name
                            / "device/driver"
                        )
                        data["devices"].append(
                            {
                                "path": str(path),
                                "category": modality,
                                **{
                                    k: v
                                    for k, v in component.items()
                                    if k in {"model", "driver"} and v
                                },
                            }
                        )
                        component["resource_id"] = _resource_id(component)
                        data["components"].append(component)
            for bus, command in {
                "usb": ["lsusb"],
                "pci": ["lspci", "-nn"],
                "network": ["ip", "-json", "link", "show"],
            }.items():
                result = _run(command, timeout_s=5)
                if result.get("returncode") == 0:
                    data["buses"][bus] = result["stdout"].splitlines()[:MAX_ITEMS]
                else:
                    data["buses"][bus] = {"status": "UNAVAILABLE", "detail": _failure(result)}
                    warnings.append(f"{bus} hardware observation is unavailable")
            for zone in sorted(Path("/sys/class/thermal").glob("thermal_zone*")):
                name = _read_text(zone / "type", 256)
                raw = _read_text(zone / "temp", 256)
                try:
                    temperature = float((raw or "").strip()) / 1000
                except ValueError:
                    continue
                if name:
                    data["thermal_zones"].append(
                        {"name": name.strip(), "temperature_c": temperature}
                    )
        if provider_path is not None:
            data["provider"] = {"robot_id": robot_id, "path": str(provider_path)}
        return ProbeResult(
            layer="hw",
            status=DiscoveryStatus.PARTIAL if warnings else DiscoveryStatus.SUCCEEDED,
            data=data,
            warnings=warnings,
        )


class LinuxProbe:
    """Current MVP OS provider; the result contract is platform-neutral."""

    def __init__(self, *, environment: Mapping[str, str] | None = None) -> None:
        self.environment = dict(os.environ if environment is None else environment)

    def run(self) -> ProbeResult:
        data: dict[str, Any] = {
            "host": {
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "architecture": platform.machine().lower(),
                "hostname": platform.node(),
                "os_release": _os_release(),
            },
            "environment": admitted_runtime_environment(self.environment),
            "executables": {},
            "processes": [],
        }
        warnings: list[str] = []
        checks = {
            "python": ["python", "--version"],
            "git": ["git", "--version"],
            "cmake": ["cmake", "--version"],
            "docker": ["docker", "--version"],
            "middleware-cli": ["ros2", "--help"],
        }
        for name, command in checks.items():
            result = _run(command, timeout_s=5, environment=self.environment)
            output = (result.get("stdout") or result.get("stderr") or "").splitlines()
            data["executables"][name] = {
                "path": shutil.which(command[0], path=self.environment.get("PATH")),
                "installed": bool(result.get("available")),
                "available": result.get("returncode") == 0,
                "returncode": result.get("returncode"),
                "version_output": output[:1],
                "error": result.get("error"),
            }
            if result.get("available") and result.get("returncode") != 0:
                warnings.append(f"{name} self-description failed: {_failure(result)}")
        if platform.system() == "Linux":
            result = _run(["ps", "-eo", "pid=,ppid=,stat=,comm="], environment=self.environment)
            if result.get("returncode") == 0:
                data["processes"] = result["stdout"].splitlines()[:MAX_ITEMS]
            else:
                warnings.append(f"process observation unavailable: {_failure(result)}")
        else:
            warnings.append("the current OS provider has no process adapter for this platform")
        return ProbeResult(
            layer="linux",
            status=DiscoveryStatus.PARTIAL if warnings else DiscoveryStatus.SUCCEEDED,
            data=data,
            warnings=warnings,
        )


class RosProbe:
    """Current MVP Middleware provider with bounded graph snapshots."""

    def __init__(
        self,
        *,
        ros_root: Path = Path("/opt/ros"),
        environment: Mapping[str, str] | None = None,
        enrich_routes: bool = False,
        stabilize: bool = False,
    ) -> None:
        self.ros_root = ros_root
        self.environment = dict(os.environ if environment is None else environment)
        self.enrich_routes = enrich_routes
        self.stabilize = stabilize

    def _setup(self) -> Path | None:
        preferred = [self.environment.get("ROS_DISTRO")]
        if self.ros_root.is_dir():
            preferred.extend(sorted(path.name for path in self.ros_root.iterdir() if path.is_dir()))
        for distro in dict.fromkeys(item for item in preferred if item):
            setup = self.ros_root / distro / "setup.bash"
            if setup.is_file():
                return setup
        return None

    def _run_cli(self, args: Sequence[str]) -> dict[str, Any]:
        direct = _run(["ros2", *args], timeout_s=10, environment=self.environment)
        if direct.get("available") and direct.get("returncode") == 0:
            return direct
        setup = self._setup()
        if setup is None or shutil.which("bash", path=self.environment.get("PATH")) is None:
            return direct
        command = f". {shlex.quote(str(setup))} && exec ros2 {shlex.join(list(args))}"
        fallback = _run(
            ["bash", "--noprofile", "--norc", "-c", command],
            timeout_s=10,
            environment=self.environment,
        )
        fallback["execution_context"] = "pinned_middleware_setup"
        return fallback

    @staticmethod
    def _snapshot(text: str) -> list[str]:
        return sorted({line.strip() for line in text.splitlines() if line.strip()})[:MAX_ITEMS]

    def _sample(self) -> tuple[dict[str, list[str]], dict[str, Any], list[str]]:
        fields = {
            "nodes": ["node", "list", "--no-daemon"],
            "topics": ["topic", "list", "-t", "--no-daemon"],
            "services": ["service", "list", "-t", "--no-daemon"],
            "actions": ["action", "list", "-t"],
        }
        snapshots: dict[str, list[str]] = {key: [] for key in fields}
        diagnostics: dict[str, Any] = {}
        warnings: list[str] = []
        successes = 0
        for key, args in fields.items():
            result = self._run_cli(args)
            diagnostics[key] = {
                "returncode": result.get("returncode"),
                "error": result.get("error"),
                "stderr_excerpt": str(result.get("stderr") or "")[:4000] or None,
            }
            if result.get("returncode") == 0:
                snapshots[key] = self._snapshot(str(result.get("stdout") or ""))
                successes += 1
            else:
                warnings.append(
                    f"Middleware graph query {' '.join(args)} unavailable: {_failure(result)}"
                )
        diagnostics["successes"] = successes
        return snapshots, diagnostics, warnings

    def run(self) -> ProbeResult:
        snapshots, diagnostics, warnings = self._sample()
        data: dict[str, Any] = {
            "runtime_environment": admitted_runtime_environment(self.environment),
            **snapshots,
            "command_diagnostics": diagnostics,
        }
        if self.stabilize and diagnostics.get("successes", 0):
            previous = snapshots
            stable = False
            attempts = 1
            while attempts < MAX_MIDDLEWARE_SAMPLES:
                current, _, current_warnings = self._sample()
                attempts += 1
                if not current_warnings and current == previous:
                    stable = True
                    data.update(current)
                    break
                previous = current
            data["stability"] = {"attempts": attempts, "stable": stable}
            if not stable:
                warnings.append("Middleware graph did not stabilize across bounded samples")
        if self.enrich_routes:
            data["route_enrichment"] = {
                "provider_ids": {},
                "interface_schema_sha256": {},
                "provider_evidence_source": "Middleware provider",
                "schema_evidence_source": "Middleware provider",
                "truncated": False,
            }
        successes = diagnostics.get("successes", 0)
        status = (
            DiscoveryStatus.SUCCEEDED
            if successes == 4 and not warnings
            else DiscoveryStatus.PARTIAL
            if successes
            else DiscoveryStatus.UNAVAILABLE
        )
        return ProbeResult(layer="ros", status=status, data=data, warnings=warnings)


# Generic aliases make the extension point explicit while retaining the
# current provider implementations used by the physical MVP target.
OSProbe = LinuxProbe
MiddlewareProbe = RosProbe
