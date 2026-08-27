"""Stage 1 bounded hardware, software, ROS, and application discovery."""

from __future__ import annotations

import ast
import configparser
import io
import math
import os
import platform
import re
import shlex
import shutil
import subprocess
import tokenize
import xml.etree.ElementTree as ET
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml
from packaging.requirements import InvalidRequirement, Requirement

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

from rolo.core.artifacts import ArtifactStore
from rolo.core.config import get_settings
from rolo.core.hashing import sha256_bytes, sha256_file
from rolo.core.models import (
    DiscoveryLatestIndex,
    DiscoveryReport,
    DiscoveryStatus,
    OperationCandidate,
    ProbeResult,
    RobotCapability,
    RouteEvidence,
)
from rolo.runtime_context import admitted_runtime_environment
from rolo.stages.adapt.active_discovery import (
    ActiveDiscoveryAnalyzer,
    ActiveDiscoveryInputs,
    ActiveDiscoveryReport,
    ActiveProbeMode,
    CoverageStatus,
    ExecutableDiscovery,
    HelpProbeResult,
    InvocationAnalysis,
    render_active_discovery_markdown,
)
from rolo.stages.adapt.application_cli_mapping import (
    ApplicationCliRouteProvider,
    canonical_executable_name,
)
from rolo.stages.adapt.discovery_status import (
    aggregate_probe_status,
    derive_discovery_status,
)
from rolo.stages.adapt.enrollment import load_urdf_profile
from rolo.stages.adapt.evidence import (
    BASE_SKIP_DIRECTORIES,
    extract_protocols,
    read_text,
    walk_files,
)
from rolo.stages.adapt.hardware_provider import collect_hardware_provider_evidence
from rolo.stages.adapt.heuristic_discovery import (
    HeuristicDiscoveryOrchestrator,
    WhitelistedR0ProbeDispatcher,
    render_heuristic_summary_markdown,
)
from rolo.stages.adapt.inputs import (
    AdaptInputs,
    SemanticCandidate,
    SemanticContext,
    StageSemanticInputs,
)
from rolo.stages.adapt.operation_registry import validate_candidate_operations
from rolo.stages.adapt.review import render_discovery_review_markdown
from rolo.stages.adapt.routes import persist_route_evidence
from rolo.stages.adapt.semantic_mapping import matching_semantic_rules
from rolo.stages.adapt.software_relevance import (
    DirectDependencyResolver,
    ResolutionStatus,
    SoftwareDiscoveryPolicy,
    SoftwareSummary,
    build_software_summary,
    enrich_active_report,
)
from rolo.stages.adapt.wiki import WikiNarrativePolisher, generate_robot_wiki
from rolo.stages.adapt.wiki_diff import build_wiki_discovery_diff
from rolo.stages.adapt.wiki_insights import WikiInsightProvider, collect_wiki_insights
from rolo.stages.artifact_paths import ArtifactLayout, resolve_artifact_ref
from rolo.stages.discovery_manifest import (
    create_discovery_manifest,
    load_and_verify_discovery_manifest,
)

MAX_COMMAND_OUTPUT = 200_000
MAX_SOURCE_FILES = 10_000
MAX_DISCOVERED_ITEMS = 1_000
SKIP_DIRECTORIES = BASE_SKIP_DIRECTORIES | {
    "venv",
    "build",
    "dist",
    "install",
    "log",
    "artifacts",
    "third-party",
    "third_party",
    "vendor",
    "vendors",
}
UBUNTU_ROS_DEFAULTS = {"20.04": "foxy", "22.04": "humble", "24.04": "jazzy"}
SEMANTIC_PARAMETER_ALIASES = {
    "max_vel_x": ("geometry.hard_max_linear_velocity_mps", "m/s"),
    "max_linear_velocity": ("geometry.hard_max_linear_velocity_mps", "m/s"),
    "max_linear_speed": ("geometry.hard_max_linear_velocity_mps", "m/s"),
    "max_vel_theta": ("geometry.hard_max_angular_velocity_radps", "rad/s"),
    "max_angular_velocity": ("geometry.hard_max_angular_velocity_radps", "rad/s"),
    "max_angular_speed": ("geometry.hard_max_angular_velocity_radps", "rad/s"),
}


def _read_text(path: Path, limit: int = MAX_COMMAND_OUTPUT) -> str | None:
    return read_text(path, limit)


def _cached_read_text(path: Path, cache: dict[Path, str | None], limit: int) -> str | None:
    if path not in cache:
        cache[path] = _read_text(path, limit)
    return cache[path]


def _run(
    args: Sequence[str],
    *,
    timeout_s: float = 8.0,
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    executable = shutil.which(args[0], path=environment.get("PATH") if environment else None)
    if executable is None and not Path(args[0]).is_file():
        return {"available": False, "argv": list(args), "error": "executable not found"}
    try:
        completed = subprocess.run(
            [executable or args[0], *args[1:]],
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
            env=dict(environment) if environment is not None else None,
        )
    except subprocess.TimeoutExpired:
        return {"available": True, "argv": list(args), "error": "timeout"}
    except OSError as exc:
        return {"available": True, "argv": list(args), "error": str(exc)}
    return {
        "available": True,
        "argv": list(args),
        "returncode": completed.returncode,
        "stdout": completed.stdout[:MAX_COMMAND_OUTPUT],
        "stderr": completed.stderr[:20_000],
    }


def _command_diagnostic(result: Mapping[str, Any]) -> dict[str, Any]:
    """Retain bounded failure evidence without treating process launch as success."""
    stderr = str(result.get("stderr") or "")[:4_000]
    error = str(result.get("error") or "")[:1_000]
    diagnostic = {
        "argv": [str(item) for item in result.get("argv", [])],
        "installed": bool(result.get("available")),
        "succeeded": result.get("returncode") == 0,
        "returncode": result.get("returncode"),
        "error": error or None,
        "stderr_excerpt": stderr or None,
    }
    attempts = result.get("attempts")
    if isinstance(attempts, list):
        diagnostic["attempts"] = attempts
    return diagnostic


def _command_failure_summary(result: Mapping[str, Any]) -> str:
    if result.get("error"):
        return str(result["error"]).splitlines()[0][:300]
    stderr_lines = str(result.get("stderr") or "").splitlines()
    detail = stderr_lines[0][:300] if stderr_lines else "no diagnostic output"
    return f"exit {result.get('returncode', 'unknown')}: {detail}"


def _ros_failure_class(result: Mapping[str, Any], *, codex_network_sandboxed: bool) -> str:
    detail = "\n".join(
        str(result.get(key) or "") for key in ("error", "stderr", "stdout")
    ).casefold()
    if result.get("returncode") == 2 and any(
        marker in detail for marker in ("unrecognized arguments", "invalid choice", "usage:")
    ):
        return "CLI_ARGUMENT_UNSUPPORTED"
    if not result.get("available"):
        return "ROS_CLI_UNAVAILABLE"
    sandbox_markers = (
        "sandbox",
        "permissionerror",
        "operation not permitted",
        "localhost socket",
        "network is unreachable",
    )
    if codex_network_sandboxed and any(marker in detail for marker in sandbox_markers):
        return "EXECUTION_SANDBOX_RESTRICTED"
    return "ROS_CLI_FAILED"


def _parse_os_release() -> dict[str, str]:
    text = _read_text(Path("/etc/os-release"))
    if text is None:
        return {}
    values: dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        values[key.lower()] = value.strip().strip('"')
    return values


def _device_tree_model() -> str | None:
    for candidate in (Path("/proc/device-tree/model"), Path("/sys/firmware/devicetree/base/model")):
        text = _read_text(candidate, 512)
        if text:
            return text.rstrip("\x00\n")
    return None


def _driver_name(path: Path) -> str | None:
    try:
        return path.resolve(strict=True).name
    except OSError:
        return None


def detect_compute_platform(device_tree_model: str | None) -> str:
    if not device_tree_model:
        return "unknown"
    model = device_tree_model.lower()
    if "raspberry pi" in model:
        return "raspberry_pi"
    if "rk3588" in model or "rockchip" in model:
        return "rockchip_rk3588"
    if "jetson" in model or "orin" in model:
        return "nvidia_jetson_orin"
    return "unknown"


def _merge_hardware_provider(
    data: dict[str, Any],
    warnings: list[str],
    *,
    robot_id: str,
    provider_path: Path | None,
) -> None:
    provider = provider_path or get_settings().rolo_hardware_evidence_provider
    if provider is None:
        return
    try:
        evidence = collect_hardware_provider_evidence(provider, robot_id=robot_id)
    except ValueError as exc:
        warnings.append(str(exc))
        data["hardware_provider"] = {
            "path": str(provider.expanduser().resolve()),
            "status": "FAILED",
            "error": str(exc),
        }
        return
    merged = {(str(item.get("kind")), str(item.get("name"))): item for item in data["components"]}
    for component in evidence.components:
        merged[(component.kind, component.name)] = component.model_dump(mode="json")
    data["components"] = list(merged.values())
    data["devices"].extend(item.model_dump(mode="json") for item in evidence.devices)
    warnings.extend(evidence.warnings)
    data["hardware_provider"] = {
        "path": str(provider.expanduser().resolve()),
        "status": "SUCCEEDED",
    }


def _assign_hardware_resource_ids(data: dict[str, Any]) -> None:
    """Attach a stable identity without deriving it from mutable hardware attributes."""
    for component in data.get("components", []):
        if not isinstance(component, dict):
            continue
        if provider_id := component.get("provider_id"):
            identity = (
                f"hardware_provider:{provider_id}:{component.get('kind')}:{component.get('name')}"
            )
        elif path := component.get("path"):
            identity = f"hardware_path:{path}"
        else:
            identity = f"hardware_component:{component.get('kind')}:{component.get('name')}"
        component["resource_id"] = identity


class HardwareProbe:
    def run(
        self,
        *,
        robot_id: str = "unregistered",
        provider_path: Path | None = None,
    ) -> ProbeResult:
        device_tree_model = _device_tree_model()
        data: dict[str, Any] = {
            "architecture": platform.machine().lower(),
            "processor": platform.processor() or None,
            "device_tree_model": device_tree_model,
            "compute_platform": detect_compute_platform(device_tree_model),
            "devices": [],
            "components": [],
            "buses": {},
            "thermal_zones": [],
        }
        warnings: list[str] = []
        if platform.system() != "Linux":
            warnings.append("Linux /sys and /dev hardware enumeration is unavailable on this host")
            _merge_hardware_provider(
                data,
                warnings,
                robot_id=robot_id,
                provider_path=provider_path,
            )
            _assign_hardware_resource_ids(data)
            return ProbeResult(
                layer="hw", status=DiscoveryStatus.PARTIAL, data=data, warnings=warnings
            )

        if device_tree_model:
            data["components"].append(
                {
                    "kind": "board",
                    "name": "compute_platform",
                    "model": device_tree_model,
                    "source": "device_tree",
                }
            )

        device_patterns = {
            "camera": ("video*",),
            "serial": ("ttyUSB*", "ttyACM*", "ttyTHS*"),
            "i2c": ("i2c-*",),
            "input": ("input/event*",),
        }
        for modality, patterns in device_patterns.items():
            for pattern_value in patterns:
                for path in sorted(Path("/dev").glob(pattern_value))[:MAX_DISCOVERED_ITEMS]:
                    device = {
                        "path": str(path),
                        "category": modality,
                        "semantic_candidate": f"semantic://device/{modality}/{path.name}",
                    }
                    model = None
                    driver = None
                    if modality == "camera":
                        sysfs = Path("/sys/class/video4linux") / path.name
                        model = _read_text(sysfs / "name", 512)
                        driver = _driver_name(sysfs / "device/driver")
                    elif modality == "input":
                        sysfs = Path("/sys/class/input") / path.name
                        model = _read_text(sysfs / "device/name", 512)
                        driver = _driver_name(sysfs / "device/driver")
                    elif modality == "serial":
                        driver = _driver_name(Path("/sys/class/tty") / path.name / "device/driver")
                    if model:
                        device["model"] = model.strip()
                    if driver:
                        device["driver"] = driver
                    data["devices"].append(device)
                    data["components"].append(
                        {
                            "kind": "sensor" if modality in {"camera", "input"} else "interface",
                            "name": path.name,
                            "modality": modality,
                            "model": device.get("model"),
                            "driver": device.get("driver"),
                            "path": str(path),
                            "source": "sysfs_dev",
                        }
                    )

        for path in sorted(Path("/sys/bus/iio/devices").glob("iio:device*"))[:MAX_DISCOVERED_ITEMS]:
            model = _read_text(path / "name", 512)
            data["components"].append(
                {
                    "kind": "sensor",
                    "name": path.name,
                    "model": model.strip() if model else None,
                    "driver": _driver_name(path / "driver"),
                    "path": str(path),
                    "source": "iio_sysfs",
                }
            )

        for bus, command in {
            "usb": ["lsusb"],
            "pci": ["lspci", "-nn"],
            "network": ["ip", "-json", "link", "show"],
        }.items():
            result = _run(command)
            if result.get("returncode") == 0:
                data["buses"][bus] = result.get("stdout", "").splitlines()[:MAX_DISCOVERED_ITEMS]
            else:
                data["buses"][bus] = {"status": "UNAVAILABLE", "detail": result.get("error")}
                warnings.append(f"{bus} hardware enumeration is unavailable")

        for zone in sorted(Path("/sys/class/thermal").glob("thermal_zone*")):
            zone_type = _read_text(zone / "type", 256)
            temperature = _read_text(zone / "temp", 256)
            if zone_type and temperature:
                try:
                    value_c = float(temperature.strip()) / 1000.0
                except ValueError:
                    continue
                data["thermal_zones"].append({"name": zone_type.strip(), "temperature_c": value_c})

        _merge_hardware_provider(
            data,
            warnings,
            robot_id=robot_id,
            provider_path=provider_path,
        )
        _assign_hardware_resource_ids(data)
        return ProbeResult(
            layer="hw",
            status=DiscoveryStatus.PARTIAL if warnings else DiscoveryStatus.SUCCEEDED,
            data=data,
            warnings=warnings,
        )


class LinuxProbe:
    def __init__(self, *, environment: Mapping[str, str] | None = None) -> None:
        self.environment = dict(os.environ if environment is None else environment)

    def run(self) -> ProbeResult:
        os_release = _parse_os_release()
        data: dict[str, Any] = {
            "host": {
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "architecture": platform.machine().lower(),
                "hostname": platform.node(),
                "os_release": os_release,
            },
            "environment": admitted_runtime_environment(self.environment),
            "executables": {},
            "processes": [],
        }
        warnings: list[str] = []
        executable_checks = {
            "ros2": ["ros2", "--help"],
            "colcon": ["colcon", "version-check"],
            "python3": ["python3", "--version"],
            "cmake": ["cmake", "--version"],
            "git": ["git", "--version"],
            "docker": ["docker", "--version"],
            "gcc": ["gcc", "--version"],
        }
        for name, command in executable_checks.items():
            result = _run(command, timeout_s=5, environment=self.environment)
            succeeded = result.get("returncode") == 0
            data["executables"][name] = {
                "path": shutil.which(command[0]),
                "installed": bool(result.get("available")),
                "available": succeeded,
                "returncode": result.get("returncode"),
                "error": result.get("error"),
                "stderr_excerpt": str(result.get("stderr") or "")[:4_000] or None,
                "version_output": (result.get("stdout") or result.get("stderr") or "").splitlines()[
                    :1
                ],
            }
            if result.get("available") and not succeeded:
                warnings.append(
                    f"{name} self-description failed: {_command_failure_summary(result)}"
                )

        if platform.system() == "Linux":
            processes = _run(
                ["ps", "-eo", "pid=,ppid=,stat=,comm="],
                environment=self.environment,
            )
            if processes.get("returncode") == 0:
                data["processes"] = processes["stdout"].splitlines()[:MAX_DISCOVERED_ITEMS]
        else:
            warnings.append("Linux process probes were skipped on a non-Linux host")

        status = (
            DiscoveryStatus.PARTIAL
            if warnings or platform.system() != "Linux"
            else DiscoveryStatus.SUCCEEDED
        )
        return ProbeResult(layer="linux", status=status, data=data, warnings=warnings)


class RosProbe:
    def __init__(
        self,
        *,
        ros_root: Path = Path("/opt/ros"),
        environment: Mapping[str, str] | None = None,
    ) -> None:
        self.ros_root = ros_root
        self.environment = dict(os.environ if environment is None else environment)

    def _resolve_setup(self) -> Path | None:
        os_version = _parse_os_release().get("VERSION_ID")
        preferred = [self.environment.get("ROS_DISTRO"), UBUNTU_ROS_DEFAULTS.get(os_version)]
        if self.ros_root.is_dir():
            preferred.extend(sorted(path.name for path in self.ros_root.iterdir() if path.is_dir()))
        for distro in dict.fromkeys(item for item in preferred if item):
            setup = self.ros_root / distro / "setup.bash"
            if setup.is_file():
                return setup
        return None

    @staticmethod
    def _rmw_candidates(setup: Path | None) -> list[str]:
        if setup is None:
            return []
        candidates: set[str] = set()
        for path in (setup.parent / "lib").glob("librmw_*.so*"):
            match = re.match(r"lib(rmw_[A-Za-z0-9_]+)\.so", path.name)
            if match:
                candidates.add(match.group(1))
        return sorted(candidates)

    def _run_ros(self, args: Sequence[str]) -> dict[str, Any]:
        if shutil.which("ros2"):
            direct = _run(["ros2", *args], timeout_s=10, environment=self.environment)
            if direct.get("returncode") == 0:
                return direct
            if self.environment.get("CODEX_SANDBOX_NETWORK_DISABLED") == "1":
                return direct
        else:
            direct = None
        setup = self._resolve_setup()
        if setup is not None and shutil.which("bash"):
            command = (
                "unset PYTHONHOME PYTHONPATH VIRTUAL_ENV; "
                f"source {shlex.quote(str(setup))} && ros2 {shlex.join(args)}"
            )
            fallback = _run(
                ["bash", "--noprofile", "--norc", "-c", command],
                timeout_s=10,
                environment=self.environment,
            )
            fallback["execution_context"] = "clean_ros_base_setup"
            if direct is not None:
                fallback["attempts"] = [
                    {"context": "inherited_environment", **_command_diagnostic(direct)},
                    {
                        "context": "clean_ros_base_setup",
                        **_command_diagnostic(fallback),
                    },
                ]
            return fallback
        if direct is not None:
            return direct
        return {"available": False, "error": "ROS 2 environment not found"}

    def run(self) -> ProbeResult:
        installed_distros: list[str] = []
        if self.ros_root.is_dir():
            installed_distros = sorted(
                path.name for path in self.ros_root.iterdir() if path.is_dir()
            )
        setup = self._resolve_setup()
        configured_distro = self.environment.get("ROS_DISTRO")
        configured_rmw = self.environment.get("RMW_IMPLEMENTATION")
        configured_domain = self.environment.get("ROS_DOMAIN_ID")
        codex_network_sandboxed = self.environment.get("CODEX_SANDBOX_NETWORK_DISABLED") == "1"
        data: dict[str, Any] = {
            "ros_distro": configured_distro or (setup.parent.name if setup else None),
            "ros_distro_source": (
                "ENVIRONMENT" if configured_distro else "SETUP_PATH" if setup else "NOT_FOUND"
            ),
            "installed_distros": installed_distros,
            "domain_id": configured_domain or "0",
            "domain_id_source": "ENVIRONMENT" if configured_domain else "ROS_DEFAULT",
            "rmw": configured_rmw,
            "rmw_source": "ENVIRONMENT" if configured_rmw else "NOT_SELECTED",
            "rmw_candidates": self._rmw_candidates(setup),
            "runtime_environment": admitted_runtime_environment(self.environment),
            "execution_environment": {
                "codex_sandbox_network_disabled": codex_network_sandboxed,
            },
            "nodes": [],
            "topics": [],
            "services": [],
            "actions": [],
            "command_diagnostics": {},
        }
        warnings: list[str] = []
        if not configured_distro and len(installed_distros) > 1:
            warnings.append(
                "multiple ROS distributions are installed; setup-path selection is inferred"
            )
        if not configured_rmw and data["rmw_candidates"]:
            warnings.append(
                "RMW implementation is not selected; installed candidates are not runtime proof"
            )
        command_map = {
            "nodes": ["node", "list", "--no-daemon"],
            "topics": ["topic", "list", "-t", "--no-daemon"],
            "services": ["service", "list", "-t", "--no-daemon"],
            # Humble's action verb does not accept --no-daemon.
            "actions": ["action", "list", "-t"],
        }
        successes = 0
        sandbox_failures = 0
        for field, args in command_map.items():
            result = self._run_ros(args)
            diagnostic = _command_diagnostic(result)
            if result.get("returncode") != 0:
                failure_class = _ros_failure_class(
                    result,
                    codex_network_sandboxed=codex_network_sandboxed,
                )
                diagnostic["failure_class"] = failure_class
                sandbox_failures += failure_class == "EXECUTION_SANDBOX_RESTRICTED"
            data["command_diagnostics"][field] = diagnostic
            if result.get("returncode") == 0:
                data[field] = result["stdout"].splitlines()[:MAX_DISCOVERED_ITEMS]
                successes += 1
            else:
                warnings.append(
                    f"ros2 {' '.join(args)} unavailable: {_command_failure_summary(result)}"
                )
        if sandbox_failures:
            warnings.append(
                "Codex network sandbox blocked one or more ROS graph queries; collect runtime "
                "ROS evidence from a target terminal outside the coding sandbox."
            )

        if successes:
            status = (
                DiscoveryStatus.SUCCEEDED
                if successes == len(command_map)
                else DiscoveryStatus.PARTIAL
            )
        else:
            status = DiscoveryStatus.UNAVAILABLE
        return ProbeResult(layer="ros", status=status, data=data, warnings=warnings)


def _without_c_cpp_comments(text: str) -> str:
    """Remove C/C++ comments while preserving quoted strings and line structure."""
    output: list[str] = []
    index = 0
    quote: str | None = None
    escaped = False
    line_comment = False
    block_comment = False
    while index < len(text):
        current = text[index]
        following = text[index + 1] if index + 1 < len(text) else ""
        if line_comment:
            if current == "\n":
                line_comment = False
                output.append(current)
            else:
                output.append(" ")
            index += 1
            continue
        if block_comment:
            if current == "*" and following == "/":
                output.extend((" ", " "))
                block_comment = False
                index += 2
            else:
                output.append("\n" if current == "\n" else " ")
                index += 1
            continue
        if quote:
            output.append(current)
            if escaped:
                escaped = False
            elif current == "\\":
                escaped = True
            elif current == quote:
                quote = None
            index += 1
            continue
        if current in {'"', "'"}:
            quote = current
            output.append(current)
            index += 1
            continue
        if current == "/" and following == "/":
            output.extend((" ", " "))
            line_comment = True
            index += 2
            continue
        if current == "/" and following == "*":
            output.extend((" ", " "))
            block_comment = True
            index += 2
            continue
        output.append(current)
        index += 1
    return "".join(output)


def _interface_name(expression: str) -> tuple[str, str]:
    expression = " ".join(expression.strip().split())
    literal = re.fullmatch(r"(?:u8|u|U|L)?(['\"])(.*?)\1", expression)
    if literal:
        return literal.group(2), "STRING_LITERAL"
    return f"<symbol:{expression[:120]}>", "SYMBOLIC_EXPRESSION"


def _extract_ros_interfaces(text: str, source_path: Path) -> list[dict[str, str]]:
    python_patterns = {
        "publisher": r"create_publisher\(\s*([^,]+),\s*['\"]([^'\"]+)",
        "subscriber": r"create_subscription\(\s*([^,]+),\s*['\"]([^'\"]+)",
        "service": r"create_service\(\s*([^,]+),\s*['\"]([^'\"]+)",
        "client": r"create_client\(\s*([^,]+),\s*['\"]([^'\"]+)",
    }
    interfaces: list[dict[str, str]] = []
    suffix = source_path.suffix.casefold()
    c_cpp_suffixes = {".c", ".cc", ".cpp", ".cxx", ".h", ".hpp"}
    scanned_text = _without_c_cpp_comments(text) if suffix in c_cpp_suffixes else text
    for role, pattern in python_patterns.items():
        for message_type, name in re.findall(pattern, scanned_text):
            interfaces.append(
                {
                    "role": role,
                    "name": name,
                    "type": message_type.strip(),
                    "source": str(source_path),
                    "name_source": "STRING_LITERAL",
                }
            )
    cpp_pattern = re.compile(
        r"create_(publisher|subscription|service|client)\s*<\s*([^>]+?)\s*>\s*"
        r"\(\s*([^,\r\n]+)",
        re.MULTILINE,
    )
    role_names = {
        "publisher": "publisher",
        "subscription": "subscriber",
        "service": "service",
        "client": "client",
    }
    for kind, message_type, expression in cpp_pattern.findall(scanned_text):
        name, name_source = _interface_name(expression)
        interfaces.append(
            {
                "role": role_names[kind],
                "name": name,
                "type": message_type.strip(),
                "source": str(source_path),
                "name_source": name_source,
            }
        )
    return interfaces


def _entrypoint_source_files(root: Path, manifest: Path, target: str) -> list[str]:
    module = target.split(":", 1)[0].strip().replace(".", "/")
    candidates = [
        manifest.parent / f"{module}.py",
        manifest.parent / module / "__init__.py",
        root / f"{module}.py",
        root / module / "__init__.py",
    ]
    existing = [path for path in candidates if path.is_file()]
    selected = existing or candidates[:2]
    return sorted(
        {
            path.resolve().relative_to(root).as_posix()
            for path in selected
            if path.resolve().is_relative_to(root)
        }
    )


def _parse_console_script(value: str) -> tuple[str, str] | None:
    if "=" not in value:
        return None
    name, target = (part.strip() for part in value.split("=", 1))
    if not name or not target or not re.fullmatch(r"[A-Za-z0-9_.+-]+", name):
        return None
    return name, target


def _setup_py_entrypoints(path: Path, root: Path) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return []
    results: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function_name = (
            node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", None)
        )
        if function_name != "setup":
            continue
        entry_points = next(
            (keyword.value for keyword in node.keywords if keyword.arg == "entry_points"),
            None,
        )
        if entry_points is None:
            continue
        try:
            declared = ast.literal_eval(entry_points)
        except (ValueError, TypeError):
            continue
        scripts = declared.get("console_scripts", []) if isinstance(declared, dict) else []
        for raw in scripts:
            parsed = _parse_console_script(str(raw))
            if parsed is None:
                continue
            name, target = parsed
            results.append(
                {
                    "name": name,
                    "target": target,
                    "source": "setup.py",
                    "source_files": _entrypoint_source_files(root, path, target),
                }
            )
    return results


def _setup_cfg_entrypoints(path: Path, root: Path) -> list[dict[str, Any]]:
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read(path, encoding="utf-8")
    except (configparser.Error, OSError, UnicodeDecodeError):
        return []
    if not parser.has_option("options.entry_points", "console_scripts"):
        return []
    results: list[dict[str, Any]] = []
    for raw in parser.get("options.entry_points", "console_scripts").splitlines():
        parsed = _parse_console_script(raw.strip())
        if parsed is None:
            continue
        name, target = parsed
        results.append(
            {
                "name": name,
                "target": target,
                "source": "setup.cfg",
                "source_files": _entrypoint_source_files(root, path, target),
            }
        )
    return results


def _cmake_without_comments(text: str) -> str:
    return "\n".join(line.split("#", 1)[0] for line in text.splitlines())


def _cmake_source_file(root: Path, cmake_path: Path, token: str) -> str:
    candidate = (cmake_path.parent / token.strip("\"'")).resolve()
    try:
        return candidate.relative_to(root).as_posix()
    except ValueError:
        return token.strip("\"'")


def _cmake_program_entrypoints(text: str, path: Path, root: Path) -> list[dict[str, Any]]:
    cleaned = _cmake_without_comments(text)
    results: list[dict[str, Any]] = []
    for body in re.findall(
        r"(?ims)\binstall\s*\(\s*PROGRAMS\s+(.+?)\s+DESTINATION\b",
        cleaned,
    ):
        for token in re.split(r"\s+", body.strip()):
            source = _cmake_source_file(root, path, token)
            if not source.casefold().endswith(".py"):
                continue
            results.append(
                {
                    "name": Path(source).stem,
                    "target": source,
                    "source": "cmake_install_program",
                    "source_files": [source],
                }
            )
    return results


def _extract_semantic_candidates(
    text: str, *, source_path: Path, source_kind: str
) -> list[dict[str, Any]]:
    """Extract numeric hints without executing or trusting source configuration."""
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, float, str]] = set()
    number = r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)"
    for source_key, (field, unit) in SEMANTIC_PARAMETER_ALIASES.items():
        pattern = re.compile(
            rf"(?i)(?<![A-Za-z0-9_]){re.escape(source_key)}(?![A-Za-z0-9_])"
            rf"[^\r\n]{{0,120}}?{number}"
        )
        for match in pattern.finditer(text):
            value = float(match.group(1))
            if not math.isfinite(value) or value <= 0:
                continue
            identity = (field, value, source_key)
            if identity in seen:
                continue
            seen.add(identity)
            candidates.append(
                {
                    "field": field,
                    "value": value,
                    "unit": unit,
                    "source_kind": source_kind,
                    "source_path": str(source_path),
                    "source_key": source_key,
                    "status": "DISCOVERED_UNVERIFIED",
                    "safety_authority": "none",
                }
            )
    return candidates


def _extract_ros_config_names(text: str, *, suffix: str) -> dict[str, list[str]]:
    """Read concrete ROS names from inert configuration data without executing it."""
    names: dict[str, set[str]] = {"topics": set(), "services": set(), "actions": set()}
    payload: Any = None
    if suffix.casefold() in {".yaml", ".yml", ".json"}:
        try:
            payload = yaml.safe_load(text)
        except yaml.YAMLError:
            # Vendor ROS parameter files frequently contain tab-indented comments that
            # strict YAML rejects. A bounded literal key/value pass still recovers names
            # without attempting to repair or execute the configuration.
            payload = None

    def visit(value: Any, key_hint: str = "") -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                visit(nested, str(key).casefold())
            return
        if isinstance(value, list):
            for nested in value:
                visit(nested, key_hint)
            return
        if not isinstance(value, str) or not _is_concrete_ros_endpoint(value):
            return
        collection = next(
            (
                collection
                for token, collection in (
                    ("topic", "topics"),
                    ("service", "services"),
                    ("action", "actions"),
                )
                if token in key_hint
            ),
            None,
        )
        if collection:
            names[collection].add(_ros_entity_name(value))

    visit(payload)
    literal_pattern = re.compile(
        r"(?m)^\s*['\"]?(?P<key>[A-Za-z0-9_.-]*(?:topic|service|action)"
        r"[A-Za-z0-9_.-]*)['\"]?\s*[:=]\s*['\"]?(?P<value>/?[A-Za-z0-9_/]+)"
    )
    for match in literal_pattern.finditer(text):
        key = match.group("key").casefold()
        value = match.group("value")
        if not _is_concrete_ros_endpoint(value):
            continue
        collection = next(
            collection
            for token, collection in (
                ("topic", "topics"),
                ("service", "services"),
                ("action", "actions"),
            )
            if token in key
        )
        names[collection].add(_ros_entity_name(value))
    return {name: sorted(values) for name, values in names.items()}


def _extract_parameter_default_ros_names(text: str) -> dict[str, list[str]]:
    """Resolve literal ROS names used as defaults for C++ topic/service/action parameters."""
    names: dict[str, set[str]] = {"topics": set(), "services": set(), "actions": set()}
    pattern = re.compile(
        r"declare_parameter(?:\s*<[^>]+>)?\s*\(\s*['\"]"
        r"(?P<key>[^'\"]+)['\"]\s*,\s*(?:std::string\s*\(\s*)?['\"]"
        r"(?P<value>[^'\"]+)['\"]",
        re.MULTILINE,
    )
    for match in pattern.finditer(text):
        key = match.group("key").casefold()
        value = match.group("value")
        if not _is_concrete_ros_endpoint(value):
            continue
        collection = next(
            (
                collection
                for token, collection in (
                    ("topic", "topics"),
                    ("service", "services"),
                    ("action", "actions"),
                )
                if token in key
            ),
            None,
        )
        if collection:
            names[collection].add(_ros_entity_name(value))
    return {name: sorted(values) for name, values in names.items()}


def _python_without_comments(text: str) -> str:
    """Remove Python comments without changing string literals or executing source."""
    try:
        tokens = tokenize.generate_tokens(io.StringIO(text).readline)
        return tokenize.untokenize(token for token in tokens if token.type != tokenize.COMMENT)
    except (IndentationError, tokenize.TokenError):
        return text


@dataclass(frozen=True)
class ApplicationScanResult:
    probe: ProbeResult
    evidence_text: dict[Path, str]


class ApplicationProbe:
    def run(self, source_roots: Sequence[Path]) -> ProbeResult:
        return self.scan(source_roots).probe

    def scan(self, source_roots: Sequence[Path]) -> ApplicationScanResult:
        projects: list[dict[str, Any]] = []
        warnings: list[str] = []
        evidence_text: dict[Path, str] = {}
        for requested_root in source_roots:
            root = requested_root.expanduser().resolve()
            if not root.is_dir():
                warnings.append(f"source root does not exist: {root}")
                continue
            files, truncated, walk_warnings = walk_files(
                [root],
                limit=MAX_SOURCE_FILES,
                skip_directories=SKIP_DIRECTORIES,
            )
            warnings.extend(walk_warnings)
            project: dict[str, Any] = {
                "root": str(root),
                "file_count_scanned": len(files),
                "scan_truncated": truncated,
                "build_systems": [],
                "packages": [],
                "entrypoints": [],
                "launch_files": [],
                "readmes": [],
                "config_files": [],
                "semantic_candidates": [],
                "ros_names": {"topics": [], "services": [], "actions": []},
                "ros_interfaces": [],
                "protocols": [],
                "languages": [],
                "build_targets": [],
                "declared_dependencies": [],
                "dependency_declarations": [],
                "manifest_digests": {},
                "source_revision": None,
            }
            relative_names = {path.relative_to(root).as_posix(): path for path in files}
            if "pyproject.toml" in relative_names:
                project["build_systems"].append("python/pyproject")
                pyproject_path = relative_names["pyproject.toml"]
                try:
                    metadata = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
                    project_data = metadata.get("project", {})
                    if project_data.get("name"):
                        project["packages"].append(project_data["name"])
                    for dependency in project_data.get("dependencies", []):
                        declaration = str(dependency)
                        try:
                            requirement = Requirement(declaration)
                        except InvalidRequirement as exc:
                            requirement = None
                            warnings.append(
                                f"cannot parse dependency {declaration!r} in "
                                f"{pyproject_path}: {exc}"
                            )
                        if requirement is not None:
                            name = requirement.name
                            project["declared_dependencies"].append(name)
                            project["dependency_declarations"].append(
                                {
                                    "name": name,
                                    "ecosystem": "python",
                                    "scope": "runtime",
                                    "required": True,
                                    "specifier": str(requirement.specifier) or None,
                                    "marker": (
                                        str(requirement.marker) if requirement.marker else None
                                    ),
                                    "applicable": (
                                        requirement.marker is None or requirement.marker.evaluate()
                                    ),
                                    "extras": sorted(requirement.extras),
                                    "source": str(pyproject_path),
                                }
                            )
                    scripts = project_data.get("scripts", {})
                    project["entrypoints"].extend(
                        {"name": name, "target": target, "source": "pyproject"}
                        for name, target in scripts.items()
                    )
                except (OSError, tomllib.TOMLDecodeError, TypeError) as exc:
                    warnings.append(f"cannot parse {pyproject_path}: {exc}")
            if any(Path(name).name in {"setup.py", "setup.cfg"} for name in relative_names):
                project["build_systems"].append("python/setuptools")
            if "CMakeLists.txt" in relative_names:
                project["build_systems"].append("cmake")
            if "Cargo.toml" in relative_names:
                project["build_systems"].append("rust/cargo")

            loaded_text: dict[Path, str | None] = {}

            ros_names: dict[str, set[str]] = {
                "topics": set(),
                "services": set(),
                "actions": set(),
            }
            source_suffixes = {".py", ".cpp", ".cc", ".cxx", ".hpp", ".h"}
            for relative, path in relative_names.items():
                lower = relative.lower()
                if path.name == "package.xml":
                    try:
                        package_root = ET.parse(path).getroot()
                        name = package_root.findtext("name")
                        if name:
                            project["packages"].append(name)
                        for tag in (
                            "depend",
                            "build_depend",
                            "buildtool_depend",
                            "exec_depend",
                            "test_depend",
                        ):
                            project["declared_dependencies"].extend(
                                dependency.text.strip()
                                for dependency in package_root.findall(tag)
                                if dependency.text and dependency.text.strip()
                            )
                            for dependency in package_root.findall(tag):
                                if not dependency.text or not dependency.text.strip():
                                    continue
                                operators = {
                                    "version_lt": "<",
                                    "version_lte": "<=",
                                    "version_eq": "==",
                                    "version_gte": ">=",
                                    "version_gt": ">",
                                }
                                constraints = [
                                    f"{operator}{dependency.attrib[attribute]}"
                                    for attribute, operator in operators.items()
                                    if attribute in dependency.attrib
                                ]
                                project["dependency_declarations"].append(
                                    {
                                        "name": dependency.text.strip(),
                                        "ecosystem": "ros",
                                        "scope": tag,
                                        "required": tag != "test_depend",
                                        "specifier": ",".join(constraints) or None,
                                        "source": str(path),
                                    }
                                )
                    except (OSError, ET.ParseError) as exc:
                        warnings.append(f"cannot parse {path}: {exc}")
                if path.name == "setup.py":
                    project["entrypoints"].extend(_setup_py_entrypoints(path, root))
                elif path.name == "setup.cfg":
                    project["entrypoints"].extend(_setup_cfg_entrypoints(path, root))
                is_launch_file = path.name.endswith((".launch.py", ".launch.xml"))
                if is_launch_file:
                    project["launch_files"].append(relative)
                is_readme = path.name.lower().startswith("readme")
                if is_readme:
                    project["readmes"].append(relative)
                if path.suffix.lower() in {".yaml", ".yml", ".json", ".toml", ".ini"}:
                    project["config_files"].append(relative)
                candidate_source_kind = (
                    "launch"
                    if is_launch_file and "launch" in lower
                    else "config"
                    if path.suffix.lower() in {".yaml", ".yml", ".json", ".toml", ".ini"}
                    else None
                )
                if candidate_source_kind and path.stat().st_size <= 2_000_000:
                    candidate_text = _cached_read_text(path, loaded_text, 2_000_000)
                    if candidate_text:
                        if path.name.endswith(".launch.py"):
                            candidate_text = _python_without_comments(candidate_text)
                        project["semantic_candidates"].extend(
                            _extract_semantic_candidates(
                                candidate_text,
                                source_path=path,
                                source_kind=candidate_source_kind,
                            )
                        )
                        if candidate_source_kind == "config":
                            config_names = _extract_ros_config_names(
                                candidate_text,
                                suffix=path.suffix,
                            )
                            for collection, values in config_names.items():
                                ros_names[collection].update(values)
                if path.name in {
                    "pyproject.toml",
                    "setup.py",
                    "setup.cfg",
                    "package.xml",
                    "CMakeLists.txt",
                }:
                    project["manifest_digests"][relative] = sha256_file(path)
                if path.suffix.lower() in source_suffixes and path.stat().st_size <= 2_000_000:
                    text = _cached_read_text(path, loaded_text, 2_000_000)
                    if text:
                        language = {
                            ".py": "python",
                            ".cpp": "cpp",
                            ".cc": "cpp",
                            ".cxx": "cpp",
                            ".hpp": "cpp",
                            ".h": "c_or_cpp",
                        }.get(path.suffix.lower())
                        if language:
                            project["languages"].append(language)
                        interfaces = _extract_ros_interfaces(text, path)
                        project["ros_interfaces"].extend(interfaces)
                        parameter_names = _extract_parameter_default_ros_names(text)
                        for collection, values in parameter_names.items():
                            ros_names[collection].update(values)
                        for interface in interfaces:
                            if interface.get("name_source") != "STRING_LITERAL":
                                continue
                            role = interface.get("role")
                            collection = (
                                "topics"
                                if role in {"publisher", "subscriber"}
                                else "services"
                                if role in {"service", "client"}
                                else None
                            )
                            if collection:
                                ros_names[collection].add(str(interface["name"]))
                        project["protocols"].extend(extract_protocols(text))
                if path.name == "CMakeLists.txt" and path.stat().st_size <= 2_000_000:
                    cmake_text = _cached_read_text(path, loaded_text, 2_000_000) or ""
                    cleaned_cmake = _cmake_without_comments(cmake_text)
                    target_matches = re.findall(
                        r"(?ims)^\s*add_(?:executable|library)\s*\(\s*"
                        r"([A-Za-z0-9_.+-]+)\s+([^\)]*)\)",
                        cleaned_cmake,
                    )
                    targets = [target for target, _ in target_matches]
                    project["build_targets"].extend(targets)
                    cmake_entrypoints = [
                        {
                            "name": target,
                            "target": target,
                            "source": "cmake",
                            "source_files": sorted(
                                {
                                    _cmake_source_file(root, path, token)
                                    for token in re.split(r"\s+", body)
                                    if token.lower().endswith((".c", ".cc", ".cpp", ".cxx"))
                                }
                            ),
                        }
                        for target, body in target_matches
                    ]
                    project["entrypoints"].extend(cmake_entrypoints)
                    project["entrypoints"].extend(
                        _cmake_program_entrypoints(cmake_text, path, root)
                    )
                if (is_readme or is_launch_file) and path.stat().st_size <= 2_000_000:
                    if (text := _cached_read_text(path, loaded_text, 2_000_000)) is not None:
                        evidence_text[path.resolve()] = text

            for kind, values in ros_names.items():
                project["ros_names"][kind] = sorted(values)[:MAX_DISCOVERED_ITEMS]
            project["packages"] = sorted(set(project["packages"]))
            project["languages"] = sorted(set(project["languages"]))
            project["build_targets"] = sorted(set(project["build_targets"]))
            project["declared_dependencies"] = sorted(set(project["declared_dependencies"]))
            project["dependency_declarations"] = sorted(
                project["dependency_declarations"],
                key=lambda item: (
                    item["ecosystem"],
                    item["name"].casefold(),
                    item["scope"],
                    item["source"],
                ),
            )
            project["protocols"] = sorted(set(project["protocols"]))
            unique_entrypoints: dict[tuple[str, str, str], dict[str, Any]] = {}
            for entrypoint in project["entrypoints"]:
                key = (
                    str(entrypoint.get("name", "")),
                    str(entrypoint.get("target", "")),
                    str(entrypoint.get("source", "")),
                )
                unique_entrypoints[key] = entrypoint
            project["entrypoints"] = list(unique_entrypoints.values())[:MAX_DISCOVERED_ITEMS]
            project["ros_interfaces"] = sorted(
                project["ros_interfaces"],
                key=lambda item: (item["role"], item["name"], item["type"], item["source"]),
            )[:MAX_DISCOVERED_ITEMS]
            project["launch_files"] = project["launch_files"][:MAX_DISCOVERED_ITEMS]
            project["config_files"] = project["config_files"][:MAX_DISCOVERED_ITEMS]
            project["semantic_candidates"] = project["semantic_candidates"][:MAX_DISCOVERED_ITEMS]
            revision = _run(["git", "-C", str(root), "rev-parse", "HEAD"], timeout_s=5)
            if revision.get("returncode") == 0:
                project["source_revision"] = revision["stdout"].strip()
            projects.append(project)

        if projects:
            status = DiscoveryStatus.PARTIAL if warnings else DiscoveryStatus.SUCCEEDED
        else:
            status = DiscoveryStatus.UNAVAILABLE
        declared_routes = ApplicationCliRouteProvider().declared_routes(projects)
        return ApplicationScanResult(
            probe=ProbeResult(
                layer="application",
                status=status,
                data={
                    "projects": projects,
                    "route_evidence": [
                        route.model_dump(mode="json")
                        for route in sorted(declared_routes, key=lambda item: item.resource_id)
                    ],
                },
                warnings=warnings,
            ),
            evidence_text=evidence_text,
        )


def _ros_entity_name(value: str) -> str:
    name = value.split(" ", 1)[0].strip()
    return f"/{name.lstrip('/')}" if name else ""


def _is_concrete_ros_endpoint(value: str) -> bool:
    """Accept only fully resolved ROS graph names as routable evidence."""
    endpoint = _ros_entity_name(value)
    return bool(re.fullmatch(r"/[A-Za-z0-9_]+(?:/[A-Za-z0-9_]+)*", endpoint))


def _ros_entity_type(value: str) -> str | None:
    parts = value.strip().split(maxsplit=1)
    if len(parts) != 2:
        return None
    interface_type = parts[1].strip()
    if interface_type.startswith("[") and interface_type.endswith("]"):
        interface_type = interface_type[1:-1].strip()
    return interface_type or None


def _semantic_bindings(probes: dict[str, ProbeResult]) -> dict[str, dict[str, Any]]:
    bindings: dict[str, dict[str, Any]] = {}
    ros_probe = probes["ros"]
    ros_revision = ":".join(
        str(value)
        for value in (ros_probe.data.get("ros_distro"), ros_probe.data.get("rmw"))
        if value
    )
    topic_evidence = [
        (
            raw_topic,
            "ros2_topic",
            "live_ros_graph",
            ros_probe.observed_at,
            ros_revision or None,
        )
        for raw_topic in ros_probe.data.get("topics", [])
    ]
    for project in probes["application"].data.get("projects", []):
        topic_evidence.extend(
            (topic, "ros2_topic_candidate", f"source:{project['root']}", None, None)
            for topic in project.get("ros_names", {}).get("topics", [])
        )
    for raw_topic, transport, source, observed_at, runtime_revision in topic_evidence:
        topic = _ros_entity_name(raw_topic)
        if not _is_concrete_ros_endpoint(raw_topic):
            continue
        for rule in matching_semantic_rules(topic):
            if any(
                binding.get("semantic_rule_id") == rule.rule_id
                and _ros_entity_name(str(binding.get("binding", ""))) == topic
                for binding in bindings.values()
            ):
                continue
            semantic_uri = rule.semantic_uri
            if semantic_uri in bindings:
                semantic_uri = f"{semantic_uri}/{sha256_bytes(topic.encode('utf-8'))[:16]}"
            if semantic_uri not in bindings:
                bindings[semantic_uri] = {
                    "transport": transport,
                    "binding": topic,
                    "interface_type": _ros_entity_type(raw_topic),
                    "status": "DISCOVERED_UNVERIFIED",
                    "evidence": source,
                    "observed_at": observed_at,
                    "runtime_revision": runtime_revision,
                    "semantic_rule_id": rule.rule_id,
                    "operations": list(rule.operations),
                    "route_kind": "ros_topic",
                    "resource_id": f"ros_topic:{topic}",
                    "provider_id": None,
                    "interface_schema_sha256": None,
                    "observed": source == "live_ros_graph",
                }

    application_probe = probes.get(
        "application",
        ProbeResult(layer="application", status="UNAVAILABLE", data={}),
    )
    linux_probe = probes.get(
        "linux",
        ProbeResult(layer="linux", status="UNAVAILABLE", data={}),
    )
    bindings.update(
        ApplicationCliRouteProvider().semantic_bindings(
            application_probe,
            linux_probe,
            occupied_semantic_uris=set(bindings),
        )
    )
    return bindings


def _hardware_modality(value: Any) -> str:
    normalized = str(value or "").casefold()
    for canonical, tokens in {
        "camera": ("camera", "image", "video"),
        "lidar": ("lidar", "laser", "range_scan"),
        "imu": ("imu", "inertial"),
        "encoder": ("encoder",),
    }.items():
        if any(token in normalized for token in tokens):
            return canonical
    return normalized


def _hardware_reconciliation(
    robot: RobotCapability, observed_hardware: dict[str, Any]
) -> dict[str, Any]:
    declared: list[dict[str, Any]] = []
    for name, sensor in sorted(robot.sensors.items()):
        declared.append({"kind": "sensor", "name": name, **sensor})
    urdf_hardware = robot.features.get("urdf_hardware", {})
    for gazebo in urdf_hardware.get("gazebo", []):
        for sensor in gazebo.get("sensors", []):
            declared.append(
                {
                    "kind": "sensor",
                    "name": sensor.get("name"),
                    "modality": sensor.get("type"),
                    "urdf_link": gazebo.get("reference"),
                    "update_rate_hz": sensor.get("update_rate_hz"),
                }
            )
    for transmission in urdf_hardware.get("transmissions", []):
        for actuator in transmission.get("actuators", []):
            actuator_name = actuator.get("name") if isinstance(actuator, dict) else actuator
            declared.append(
                {
                    "kind": "actuator",
                    "name": actuator_name,
                    "transmission": transmission.get("name"),
                    "driver": transmission.get("type"),
                    "specifications": actuator if isinstance(actuator, dict) else {},
                }
            )
    for control in urdf_hardware.get("ros2_control", []):
        for plugin in control.get("plugins", []):
            declared.append(
                {
                    "kind": "board_driver",
                    "name": control.get("name") or plugin,
                    "driver": plugin,
                }
            )

    observed = [
        component
        for component in observed_hardware.get("components", [])
        if isinstance(component, dict) and component.get("name")
    ]
    observed_by_name = {str(item["name"]).casefold(): item for item in observed}
    effective: list[dict[str, Any]] = []
    differences: list[dict[str, Any]] = []
    matched_observed: set[str] = set()
    compare_fields = {"kind", "model", "driver", "modality", "firmware", "version"}
    for item in declared:
        name = str(item.get("name") or "")
        actual = observed_by_name.get(name.casefold())
        if actual is None and item.get("kind") == "sensor":
            modality = _hardware_modality(item.get("modality"))
            candidates = [
                candidate
                for candidate in observed
                if candidate.get("kind") == "sensor"
                and _hardware_modality(candidate.get("modality")) == modality
                and str(candidate["name"]).casefold() not in matched_observed
            ]
            if len(candidates) == 1:
                actual = candidates[0]
        if actual is None:
            effective.append({**item, "effective_source": "urdf"})
            continue
        actual_name = str(actual["name"])
        matched_observed.add(actual_name.casefold())
        observed_values = {
            key: value
            for key, value in actual.items()
            if key != "name" and value is not None and value != ""
        }
        if _hardware_modality(item.get("modality")) == _hardware_modality(actual.get("modality")):
            observed_values.pop("modality", None)
        merged = {
            **item,
            **observed_values,
            "observed_name": actual_name,
            "effective_source": "probe",
        }
        effective.append(merged)
        declared_specs = item.get("specifications", {})
        observed_specs = actual.get("specifications", {})
        fields = compare_fields | (set(declared_specs) & set(observed_specs))
        for field in sorted(fields):
            expected_value = declared_specs.get(field, item.get(field))
            observed_value = observed_specs.get(field, actual.get(field))
            if (
                expected_value is None
                or expected_value == ""
                or observed_value is None
                or observed_value == ""
            ):
                continue
            if field == "modality" and _hardware_modality(expected_value) == _hardware_modality(
                observed_value
            ):
                continue
            if str(expected_value).casefold() != str(observed_value).casefold():
                differences.append(
                    {
                        "component": name,
                        "field": field,
                        "urdf": expected_value,
                        "observed": observed_value,
                        "effective": observed_value,
                    }
                )
    for item in observed:
        if str(item["name"]).casefold() not in matched_observed:
            effective.append({**item, "effective_source": "probe"})
    return {
        "declared": declared,
        "observed": observed,
        "effective": effective,
        "differences": differences,
        "precedence": "probe_over_urdf",
    }


def _capability_manifest(
    robot: RobotCapability,
    probes: dict[str, ProbeResult],
    bindings: dict[str, dict[str, Any]],
    software_summary: SoftwareSummary,
) -> dict[str, Any]:
    expected_arch = str(robot.platform.get("architecture", "")).lower()
    expected_compute = str(robot.platform.get("compute", "auto_discover")).lower()
    observed_arch = str(probes["hw"].data.get("architecture", "")).lower()
    arch_aliases = {"aarch64": "arm64", "x86_64": "amd64", "amd64": "amd64"}
    normalized_observed = arch_aliases.get(observed_arch, observed_arch)
    mismatches: list[dict[str, Any]] = []
    unknowns: list[str] = []
    hardware_reconciliation = _hardware_reconciliation(robot, probes["hw"].data)
    if not normalized_observed:
        unknowns.append("platform.architecture")
    if (
        expected_arch not in {"", "auto_discover"}
        and normalized_observed
        and expected_arch != normalized_observed
    ):
        mismatches.append(
            {
                "field": "platform.architecture",
                "expected": expected_arch,
                "observed": normalized_observed,
            }
        )
    observed_compute = probes["hw"].data.get("compute_platform")
    if observed_compute in {None, "unknown"}:
        unknowns.append("platform.compute")
    if (
        expected_compute not in {"", "auto_discover"}
        and observed_compute not in {None, "unknown"}
        and expected_compute != observed_compute
    ):
        mismatches.append(
            {
                "field": "platform.compute",
                "expected": expected_compute,
                "observed": observed_compute,
            }
        )
    ros_distro = probes["ros"].data.get("ros_distro")
    installed_distros = probes["ros"].data.get("installed_distros", [])
    expected_ros = robot.platform.get("ros_distro")
    if (
        expected_ros not in {None, "", "auto_discover"}
        and expected_ros != ros_distro
        and expected_ros not in installed_distros
    ):
        mismatches.append(
            {
                "field": "platform.ros_distro",
                "expected": expected_ros,
                "observed": ros_distro,
            }
        )
    mismatches.extend(
        {
            "field": f"hardware.components.{item['component']}.{item['field']}",
            "expected": item["urdf"],
            "observed": item["observed"],
        }
        for item in hardware_reconciliation["differences"]
    )
    return {
        "schema_version": "robot-discovered-capability/v1",
        "robot_id": robot.robot_id,
        "expected_profile": robot.model_dump(mode="json"),
        "observed": {
            "hardware": probes["hw"].data,
            "software_stack": {
                "host": probes["linux"].data.get("host", {}),
                "executables": probes["linux"].data.get("executables", {}),
                "dependency_resolution": software_summary.model_dump(mode="json"),
            },
            "ros_graph": probes["ros"].data,
            "applications": probes["application"].data.get("projects", []),
        },
        "semantic_bindings": bindings,
        "hardware_reconciliation": hardware_reconciliation,
        "compatibility": {
            "status": "MISMATCH" if mismatches else "PARTIAL" if unknowns else "MATCH",
            "mismatches": mismatches,
            "unknowns": unknowns,
        },
    }


def _semantic_context(
    robot: RobotCapability,
    probes: dict[str, ProbeResult],
    discovery_id: str,
) -> SemanticContext:
    enrollment = robot.features.get("enrollment", {})
    unresolved = set(enrollment.get("unresolved_semantics", []))
    required_fields = {
        "geometry.hard_max_linear_velocity_mps": robot.geometry.get("hard_max_linear_velocity_mps"),
        "geometry.hard_max_angular_velocity_radps": robot.geometry.get(
            "hard_max_angular_velocity_radps"
        ),
        "platform.drive_model": robot.platform.get("drive_model"),
    }
    for field, value in required_fields.items():
        if value in {None, "", "unresolved"}:
            unresolved.add(field)

    candidates: list[SemanticCandidate] = []
    seen: set[tuple[str, str, str, str]] = set()
    profile_path = str(enrollment.get("profile_path", "discovery URDF"))
    declared_fields = {
        "geometry.hard_max_linear_velocity_mps": (
            robot.geometry.get("hard_max_linear_velocity_mps"),
            "m/s",
            "rolo@hard_max_linear_velocity_mps",
        ),
        "geometry.hard_max_angular_velocity_radps": (
            robot.geometry.get("hard_max_angular_velocity_radps"),
            "rad/s",
            "rolo@hard_max_angular_velocity_radps",
        ),
    }
    for field, (value, unit, source_key) in declared_fields.items():
        if value is None:
            continue
        candidate = SemanticCandidate(
            field=field,
            value=value,
            unit=unit,
            source_kind="urdf",
            source_path=profile_path,
            source_key=source_key,
            status="DECLARED_UNVERIFIED",
        )
        candidates.append(candidate)
        seen.add((candidate.field, str(candidate.value), candidate.source_path, source_key))
    for project in probes["application"].data.get("projects", []):
        for raw_candidate in project.get("semantic_candidates", []):
            candidate = SemanticCandidate.model_validate(raw_candidate)
            identity = (
                candidate.field,
                str(candidate.value),
                candidate.source_path,
                candidate.source_key,
            )
            if identity not in seen:
                seen.add(identity)
                candidates.append(candidate)
    return SemanticContext(
        robot_id=robot.robot_id,
        discovery_id=discovery_id,
        unresolved_semantics=sorted(unresolved),
        candidates=candidates,
        motion_safety_status=enrollment.get("motion_safety_status", "UNAPPROVED"),
    )


def _read_discovery_urdf(
    robot: RobotCapability,
    urdf_path: Path | None,
) -> RobotCapability:
    """Load the explicitly supplied URDF into a discovery-time capability snapshot."""
    if urdf_path is None:
        features = dict(robot.features)
        enrollment = dict(features.get("enrollment", {}))
        unresolved = set(enrollment.get("unresolved_semantics", []))
        for field, value in {
            "geometry.footprint_m": robot.geometry.get("footprint_m"),
            "geometry.hard_max_linear_velocity_mps": robot.geometry.get(
                "hard_max_linear_velocity_mps"
            ),
            "geometry.hard_max_angular_velocity_radps": robot.geometry.get(
                "hard_max_angular_velocity_radps"
            ),
            "platform.drive_model": robot.platform.get("drive_model"),
        }.items():
            if value is None or value == "" or value == "unresolved":
                unresolved.add(field)
        enrollment.update(
            {
                "urdf_status": "NOT_PROVIDED",
                "semantic_status": "PARTIAL" if unresolved else "RESOLVED",
                "unresolved_semantics": sorted(unresolved),
            }
        )
        features["enrollment"] = enrollment
        return robot.model_copy(update={"features": features})
    enrollment = dict(robot.features.get("enrollment", {}))
    profile = load_urdf_profile(urdf_path)
    enrollment.update(
        {
            "profile_id": profile.profile_id,
            "profile_format": "urdf",
            "profile_path": str(profile.path),
            "profile_sha256": profile.sha256,
            "urdf_status": "SCANNED",
            "semantic_status": ("RESOLVED" if not profile.unresolved_semantics else "PARTIAL"),
            "motion_safety_status": enrollment.get(
                "motion_safety_status",
                "UNAPPROVED",
            ),
            "unresolved_semantics": list(profile.unresolved_semantics),
        }
    )
    enrollment.pop("safety_profile_complete", None)
    features = dict(profile.features)
    features["enrollment"] = enrollment
    return RobotCapability(
        schema_version=robot.schema_version,
        robot_id=robot.robot_id,
        adapter=profile.adapter,
        platform=profile.platform,
        geometry=profile.geometry,
        sensors=profile.sensors,
        features=features,
    )


def _build_operation_candidates(
    bindings: dict[str, dict[str, Any]],
) -> list[OperationCandidate]:
    """Translate host evidence only into product-defined applicability candidates."""

    def route(semantic_uri: str) -> RouteEvidence:
        binding = bindings[semantic_uri]
        kind = str(binding.get("route_kind", "ros_topic"))
        endpoint = str(binding["binding"])
        if kind.startswith("ros_"):
            endpoint = _ros_entity_name(endpoint)
            limitations = [
                "ROS interface schema digest was not collected",
                "ROS publisher/provider identity was not collected",
            ]
        else:
            limitations = [
                "CLI self-description does not prove Operation result semantics",
                "Generated Adapter must pass independent contract conformance",
            ]
        observed = bool(binding.get("observed", False))
        return RouteEvidence(
            resource_id=str(binding.get("resource_id", f"{kind}:{endpoint}")),
            kind=kind,
            endpoint=endpoint,
            interface_type=binding.get("interface_type"),
            interface_schema_sha256=binding.get("interface_schema_sha256"),
            provider_id=binding.get("provider_id"),
            runtime_revision=binding.get("runtime_revision"),
            observed_at=binding.get("observed_at"),
            evidence_origin=("OBSERVED_RUNTIME" if observed else "DECLARED_STATIC"),
            source=str(binding.get("evidence", "unknown")),
            limitations=limitations,
        )

    candidates: list[OperationCandidate] = []
    operation_bindings: dict[str, list[str]] = {}
    for semantic_uri, binding in bindings.items():
        for operation in binding.get("operations", []):
            operation_bindings.setdefault(str(operation), []).append(semantic_uri)
    for operation, semantic_uris in sorted(operation_bindings.items()):
        semantic_uris = sorted(semantic_uris)
        candidates.append(
            OperationCandidate(
                operation=operation,
                semantic_bindings=semantic_uris,
                evidence=[bindings[semantic_uri]["binding"] for semantic_uri in semantic_uris],
                route_evidence=[route(semantic_uri) for semantic_uri in semantic_uris],
                limitations=[
                    "Heuristic CLI/help applicability requires target-runtime interface, provider, "
                    "and semantic validation",
                    "Requires adapter generation and independent conformance",
                ],
            )
        )
    validate_candidate_operations(candidates)
    return candidates


def _bind_candidate_evidence_ids(
    candidates: list[OperationCandidate],
    active_report: ActiveDiscoveryReport,
    hardware_probe: ProbeResult,
) -> list[OperationCandidate]:
    """Bind candidates only to explicitly attributable executable and hardware IDs."""
    executable_endpoints: dict[str, set[str]] = {}
    for executable in active_report.executables:
        endpoints: set[str] = set()
        for role in ("publishers", "subscribers", "services", "clients"):
            for interface in executable.communication.ros.get(role, []):
                if isinstance(interface, dict) and interface.get("name"):
                    endpoints.add(_ros_entity_name(str(interface["name"])))
        endpoints.add(executable.name)
        endpoints.add(canonical_executable_name(executable.name))
        if executable.path:
            endpoints.add(executable.path)
            endpoints.add(canonical_executable_name(executable.path))
        executable_endpoints[executable.executable_id] = endpoints

    hardware_components = [
        item
        for item in hardware_probe.data.get("components", [])
        if isinstance(item, dict) and item.get("resource_id")
    ]
    bound: list[OperationCandidate] = []
    for candidate in candidates:
        route_endpoints = {
            (_ros_entity_name(route.endpoint) if route.kind.startswith("ros_") else route.endpoint)
            for route in candidate.route_evidence
        }
        route_providers = {
            route.provider_id for route in candidate.route_evidence if route.provider_id
        }
        executable_ids = sorted(
            executable_id
            for executable_id, endpoints in executable_endpoints.items()
            if endpoints & route_endpoints or executable_id in route_providers
        )
        hardware_resource_ids = sorted(
            str(component["resource_id"])
            for component in hardware_components
            if str(component.get("path", "")) in route_endpoints
            or str(component["resource_id"]) in route_providers
        )
        bound.append(
            candidate.model_copy(
                update={
                    "executable_ids": executable_ids,
                    "hardware_resource_ids": hardware_resource_ids,
                }
            )
        )
    return bound


def _merge_target_executable_help(
    active_report: ActiveDiscoveryReport,
    linux_probe: ProbeResult,
) -> None:
    """Merge verified target-side help evidence without executing target binaries locally."""
    binding = linux_probe.data.get("target_evidence")
    if not isinstance(binding, dict):
        return
    raw_records = binding.get("executable_help", [])
    if not isinstance(raw_records, list):
        return
    bundle_digest = str(binding.get("bundle_payload_sha256", "unknown"))
    for raw in raw_records:
        if not isinstance(raw, dict):
            continue
        executable_id = str(raw.get("executable_id", ""))
        target_path = str(raw.get("path", ""))
        executable_sha256 = str(raw.get("executable_sha256", ""))
        if not executable_id or not target_path or not executable_sha256:
            continue
        try:
            help_probe = HelpProbeResult.model_validate(raw.get("help_probe", {}))
        except ValueError:
            continue
        help_probe = help_probe.model_copy(
            update={
                "output_ref": (f"target-evidence:{bundle_digest}#executable-help/{executable_id}"),
                "usage": list(raw.get("usage", [])),
                "parameters": list(raw.get("parameters", [])),
                "subcommands": list(raw.get("subcommands", [])),
            }
        )
        target_name = canonical_executable_name(target_path)
        matching = next(
            (
                executable
                for executable in active_report.executables
                if executable.path == target_path
            ),
            None,
        )
        if matching is None:
            matching = next(
                (
                    executable
                    for executable in active_report.executables
                    if executable.name == target_name
                ),
                None,
            )
        evidence_ref = help_probe.output_ref
        if matching is None:
            active_report.executables.append(
                ExecutableDiscovery(
                    executable_id=executable_id,
                    name=target_name,
                    path=target_path,
                    origin="EXPLICIT",
                    sha256=executable_sha256,
                    invocation=InvocationAnalysis(
                        entrypoint=target_path,
                        arguments=help_probe.parameters,
                        subcommands=help_probe.subcommands,
                        help_probe=help_probe,
                    ),
                    safety={
                        "target_help_probe": "ALLOWLISTED_READ_ONLY",
                        "possible_side_effect": True,
                    },
                    evidence={"help": [evidence_ref] if evidence_ref else []},
                )
            )
            continue
        matching.path = target_path
        matching.sha256 = executable_sha256
        matching.invocation.entrypoint = matching.invocation.entrypoint or target_path
        matching.invocation.arguments = sorted(
            set(matching.invocation.arguments) | set(help_probe.parameters)
        )
        matching.invocation.subcommands = sorted(
            set(matching.invocation.subcommands) | set(help_probe.subcommands)
        )
        matching.invocation.help_probe = help_probe
        matching.safety["target_help_probe"] = "ALLOWLISTED_READ_ONLY"
        matching.safety["possible_side_effect"] = True
        if evidence_ref:
            matching.evidence["help"] = sorted(
                set(matching.evidence.get("help", [])) | {evidence_ref}
            )
    active_report.executables.sort(key=lambda item: (item.name, item.executable_id))


class _DeterministicR0ProbeDispatcher(WhitelistedR0ProbeDispatcher):
    """Bind Agent-visible IDs only to existing deterministic read-only implementations."""

    def __init__(
        self,
        *,
        robot_id: str,
        run_root: Path,
        artifact_prefix: str,
        artifacts: ArtifactStore,
        software_policy: SoftwareDiscoveryPolicy,
        dependency_report_ref: str,
        allow_host_runtime_probes: bool = True,
    ) -> None:
        self.robot_id = robot_id
        self.run_root = run_root
        self.artifact_prefix = artifact_prefix
        self.artifacts = artifacts
        self.software_policy = software_policy
        self.dependency_report_ref = dependency_report_ref
        self.allow_host_runtime_probes = allow_host_runtime_probes
        super().__init__(
            {
                "probe.hardware.inventory": self._hardware,
                "probe.linux.environment": self._linux,
                "probe.ros.runtime_graph": self._ros,
                "query.application.source_interfaces": self._application,
                "query.application.build_install": self._build_install,
                "query.executable.help": self._executable_help,
            }
        )

    def _require_target_host(self) -> None:
        if not self.allow_host_runtime_probes:
            raise RuntimeError(
                "remote target evidence can be refreshed only by collecting a new signed bundle"
            )

    @staticmethod
    def _replace_model(target: Any, source: Any) -> None:
        for field_name in type(source).model_fields:
            setattr(target, field_name, getattr(source, field_name))

    def _replace_probe(
        self,
        report: DiscoveryReport,
        active: ActiveDiscoveryReport,
        layer: str,
        probe: ProbeResult,
    ) -> tuple[DiscoveryReport, ActiveDiscoveryReport]:
        updated = report.model_copy(deep=True)
        updated.probes[layer] = persist_route_evidence(probe)
        bindings = _semantic_bindings(updated.probes)
        candidates = _build_operation_candidates(bindings)
        candidates = _bind_candidate_evidence_ids(candidates, active, updated.probes["hw"])
        updated.semantic_bindings = bindings
        updated.operation_candidates = candidates
        self._replace_model(report, updated)
        return report, active

    def _hardware(
        self, report: DiscoveryReport, active: ActiveDiscoveryReport
    ) -> tuple[DiscoveryReport, ActiveDiscoveryReport]:
        self._require_target_host()
        return self._replace_probe(
            report,
            active,
            "hw",
            HardwareProbe().run(robot_id=self.robot_id),
        )

    def _linux(
        self, report: DiscoveryReport, active: ActiveDiscoveryReport
    ) -> tuple[DiscoveryReport, ActiveDiscoveryReport]:
        self._require_target_host()
        return self._replace_probe(report, active, "linux", LinuxProbe().run())

    def _ros(
        self, report: DiscoveryReport, active: ActiveDiscoveryReport
    ) -> tuple[DiscoveryReport, ActiveDiscoveryReport]:
        self._require_target_host()
        inputs = ActiveDiscoveryInputs.model_validate(active.inputs)
        if inputs.active_probe != ActiveProbeMode.RUNTIME_READONLY:
            raise RuntimeError("ROS runtime Probe was not authorized at installation/run time")
        return self._replace_probe(report, active, "ros", RosProbe().run())

    def _refresh_application(
        self,
        report: DiscoveryReport,
        active: ActiveDiscoveryReport,
    ) -> tuple[DiscoveryReport, ActiveDiscoveryReport]:
        inputs = ActiveDiscoveryInputs.model_validate(active.inputs).resolved()
        scan = ApplicationProbe().scan(inputs.source_roots)
        updated_report = report.model_copy(deep=True)
        updated_report.probes["application"] = persist_route_evidence(scan.probe)
        updated_active = ActiveDiscoveryAnalyzer(
            inputs=inputs,
            projects=scan.probe.data.get("projects", []),
            ros_probe=updated_report.probes["ros"],
            run_root=self.run_root,
            artifact_prefix=self.artifact_prefix,
            evidence_text=scan.evidence_text,
        ).build(
            discovery_id=active.discovery_id,
            robot_id=active.robot_id,
            technical_status=active.technical_status,
            created_at=datetime.now(timezone.utc),
        )
        dependency_report = DirectDependencyResolver(self.software_policy).resolve(
            discovery_id=active.discovery_id,
            projects=scan.probe.data.get("projects", []),
            active_report=updated_active,
            collected_at=datetime.now(timezone.utc),
        )
        enrich_active_report(
            updated_active,
            dependency_report,
            dependency_report_ref=self.dependency_report_ref,
        )
        software_summary = build_software_summary(
            report=dependency_report,
            dependency_report_ref=self.dependency_report_ref,
        )
        updated_report.software_summary = software_summary.model_dump(mode="json")
        run_location = self.artifact_prefix.removeprefix("artifact://")
        self.artifacts.write_json(
            f"{run_location}/direct_dependencies.json",
            dependency_report.model_dump(mode="json"),
        )
        self.artifacts.write_json(
            f"{run_location}/software_summary.json",
            software_summary.model_dump(mode="json"),
        )
        bindings = _semantic_bindings(updated_report.probes)
        candidates = _build_operation_candidates(bindings)
        candidates = _bind_candidate_evidence_ids(
            candidates,
            updated_active,
            updated_report.probes["hw"],
        )
        updated_report.semantic_bindings = bindings
        updated_report.operation_candidates = candidates
        self._replace_model(report, updated_report)
        self._replace_model(active, updated_active)
        return report, active

    def _application(
        self, report: DiscoveryReport, active: ActiveDiscoveryReport
    ) -> tuple[DiscoveryReport, ActiveDiscoveryReport]:
        if not active.inputs.get("source_roots"):
            raise RuntimeError("source-interface query requires caller-supplied source roots")
        return self._refresh_application(report, active)

    def _build_install(
        self, report: DiscoveryReport, active: ActiveDiscoveryReport
    ) -> tuple[DiscoveryReport, ActiveDiscoveryReport]:
        if not any(
            active.inputs.get(name) for name in ("build_roots", "install_roots", "executables")
        ):
            raise RuntimeError("build/install query requires caller-supplied artifact roots")
        return self._refresh_application(report, active)

    def _executable_help(
        self, report: DiscoveryReport, active: ActiveDiscoveryReport
    ) -> tuple[DiscoveryReport, ActiveDiscoveryReport]:
        self._require_target_host()
        inputs = ActiveDiscoveryInputs.model_validate(active.inputs)
        if inputs.active_probe not in {ActiveProbeMode.HELP, ActiveProbeMode.RUNTIME_READONLY}:
            raise RuntimeError("help query was not authorized at installation/run time")
        if not any(
            active.inputs.get(name) for name in ("executables", "build_roots", "install_roots")
        ):
            raise RuntimeError("help query requires caller-supplied executable evidence")
        return self._refresh_application(report, active)


class DiscoveryService:
    def __init__(
        self,
        artifacts: ArtifactStore,
        software_policy: SoftwareDiscoveryPolicy | None = None,
        wiki_polisher: WikiNarrativePolisher | None = None,
        wiki_insight_provider: WikiInsightProvider | None = None,
        heuristic_orchestrator: HeuristicDiscoveryOrchestrator | None = None,
    ) -> None:
        self.artifacts = artifacts
        self.software_policy = software_policy or SoftwareDiscoveryPolicy()
        self.wiki_polisher = wiki_polisher
        self.wiki_insight_provider = wiki_insight_provider
        self.heuristic_orchestrator = heuristic_orchestrator

    def run(
        self,
        *,
        robot: RobotCapability,
        urdf_path: Path | None = None,
        source_roots: Sequence[Path] | None = None,
        active_inputs: ActiveDiscoveryInputs | None = None,
        target_probes: Mapping[str, ProbeResult] | None = None,
    ) -> tuple[DiscoveryReport, Path]:
        if active_inputs is not None and source_roots is not None:
            raise ValueError("pass active_inputs or source_roots, not both")
        if active_inputs is None:
            active_inputs = ActiveDiscoveryInputs(
                source_roots=list(source_roots or []),
                active_probe=ActiveProbeMode.NONE,
            )
        active_inputs = active_inputs.resolved()
        if active_inputs.active_probe == ActiveProbeMode.RUNTIME_READONLY and target_probes is None:
            raise ValueError(
                "runtime-readonly discovery requires a verified target evidence bundle"
            )
        robot = _read_discovery_urdf(robot, urdf_path)
        previous_report: DiscoveryReport | None = None
        previous_active: ActiveDiscoveryReport | None = None
        try:
            previous_report = load_latest_report(self.artifacts.root, robot.robot_id)
            previous_active_path = resolve_artifact_ref(
                self.artifacts.root,
                previous_report.active_discovery_report_ref,
            )
            previous_active = ActiveDiscoveryReport.model_validate_json(
                previous_active_path.read_text(encoding="utf-8")
            )
        except (FileNotFoundError, OSError, ValueError):
            previous_report = None
            previous_active = None
        now = datetime.now(timezone.utc)
        discovery_id = f"disc-{now.strftime('%Y%m%dT%H%M%S')}-{uuid4().hex[:8]}"
        layout = ArtifactLayout(self.artifacts.root)
        run_root = layout.discovery_run(robot.robot_id, discovery_id)
        run_location = layout.relative(run_root)
        software_summary_ref = (
            f"artifact://discovery/{robot.robot_id}/runs/{discovery_id}/software_summary.json"
        )
        dependency_report_ref = (
            f"artifact://discovery/{robot.robot_id}/runs/{discovery_id}/direct_dependencies.json"
        )
        target_probe_mode: str | None = None
        if target_probes is not None:
            if set(target_probes) != {"hw", "linux", "ros"}:
                raise ValueError("target evidence must contain exactly hw, linux, and ros probes")
            if any(probe.layer != layer for layer, probe in target_probes.items()):
                raise ValueError("target evidence probe layer identity mismatch")
            target_bindings = [
                probe.data.get("target_evidence") for probe in target_probes.values()
            ]
            if not all(isinstance(binding, dict) for binding in target_bindings):
                raise ValueError("target evidence probes lack verified target binding metadata")
            binding_identities = {
                (
                    binding.get("robot_id"),
                    binding.get("collector_id"),
                    binding.get("target_host_fingerprint"),
                    binding.get("bundle_payload_sha256"),
                    binding.get("access"),
                    binding.get("deployment_mode"),
                )
                for binding in target_bindings
                if isinstance(binding, dict)
            }
            if len(binding_identities) != 1:
                raise ValueError("target evidence binding identity is inconsistent")
            binding_identity = next(iter(binding_identities))
            if binding_identity[0] != robot.robot_id:
                raise ValueError("target evidence binding identity is inconsistent")
            target_probe_mode = str(binding_identity[-1])
            if target_probe_mode not in {"local", "remote"}:
                raise ValueError("target evidence deployment mode is invalid")
            if target_probe_mode == "remote" and active_inputs.executables:
                raise ValueError(
                    "remote target evidence forbids controller-side explicit executable probes"
                )
            if binding_identity[-2] != "READ_ONLY":
                raise ValueError("target evidence binding is not read-only")
            ros_probe = target_probes["ros"]
        else:
            ros_probe = ProbeResult(
                layer="ros",
                status=DiscoveryStatus.UNAVAILABLE,
                data={"nodes": [], "topics": [], "services": [], "actions": []},
                warnings=["verified target ROS evidence was not supplied"],
            )
        application_scan = ApplicationProbe().scan(active_inputs.source_roots)
        probes = {
            "hw": (
                target_probes["hw"]
                if target_probes is not None
                else ProbeResult(
                    layer="hw",
                    status=DiscoveryStatus.UNAVAILABLE,
                    data={"robot_id": robot.robot_id},
                    warnings=["verified target hardware evidence was not supplied"],
                )
            ),
            "linux": (
                target_probes["linux"]
                if target_probes is not None
                else ProbeResult(
                    layer="linux",
                    status=DiscoveryStatus.UNAVAILABLE,
                    data={},
                    warnings=["verified target Linux evidence was not supplied"],
                )
            ),
            "ros": ros_probe,
            "application": application_scan.probe,
        }
        probes = {name: persist_route_evidence(probe) for name, probe in probes.items()}
        bindings = _semantic_bindings(probes)
        operation_candidates = _build_operation_candidates(bindings)
        applicable_probes = {
            name: probe
            for name, probe in probes.items()
            if (name != "application" or active_inputs.source_roots)
            and (name != "ros" or active_inputs.active_probe == ActiveProbeMode.RUNTIME_READONLY)
        }
        probe_status = aggregate_probe_status(probe.status for probe in applicable_probes.values())
        active_report_ref = f"artifact://{run_location}/active_discovery_report.json"
        active_report = ActiveDiscoveryAnalyzer(
            inputs=active_inputs,
            projects=probes["application"].data.get("projects", []),
            ros_probe=probes["ros"],
            run_root=run_root,
            artifact_prefix=f"artifact://{run_location}",
            evidence_text=application_scan.evidence_text,
        ).build(
            discovery_id=discovery_id,
            robot_id=robot.robot_id,
            technical_status=probe_status.value,
            created_at=now,
        )
        _merge_target_executable_help(active_report, probes["linux"])
        operation_candidates = _bind_candidate_evidence_ids(
            operation_candidates,
            active_report,
            probes["hw"],
        )
        dependency_report = DirectDependencyResolver(self.software_policy).resolve(
            discovery_id=discovery_id,
            projects=probes["application"].data.get("projects", []),
            active_report=active_report,
            collected_at=now,
        )
        enrich_active_report(
            active_report,
            dependency_report,
            dependency_report_ref=dependency_report_ref,
        )
        software_summary = build_software_summary(
            report=dependency_report,
            dependency_report_ref=dependency_report_ref,
        )
        capability_manifest = _capability_manifest(robot, probes, bindings, software_summary)
        status = derive_discovery_status(
            probe_status,
            partial_coverage=any(
                record.status == CoverageStatus.PARTIAL
                for record in active_report.coverage.values()
            ),
            partial_dependencies=dependency_report.status == ResolutionStatus.PARTIAL,
            has_executables=bool(active_report.executables),
        )
        active_report.technical_status = status.value
        semantic_context = _semantic_context(robot, probes, discovery_id)
        report = DiscoveryReport(
            discovery_id=discovery_id,
            robot_id=robot.robot_id,
            status=status,
            platform=robot.platform,
            capability_manifest=capability_manifest,
            probes=probes,
            semantic_bindings=bindings,
            operation_candidates=operation_candidates,
            software_summary=software_summary.model_dump(mode="json"),
            software_summary_ref=software_summary_ref,
            dependency_report_ref=dependency_report_ref,
            active_discovery_report_ref=active_report_ref,
            review_ref=f"artifact://{run_location}/robot_wiki.md",
            discovery_mode=active_report.discovery_mode.level.value,
            source_roots=[str(path) for path in active_inputs.source_roots],
            created_at=now,
        )
        self.artifacts.write_json(
            layout.relative(run_root / "software_summary.json"),
            software_summary.model_dump(mode="json"),
        )
        self.artifacts.write_json(
            f"{run_location}/direct_dependencies.json",
            dependency_report.model_dump(mode="json"),
        )
        self.artifacts.write_json(
            f"{run_location}/active_discovery_report.json",
            active_report.model_dump(mode="json"),
        )
        self.artifacts.write_text(
            f"{run_location}/active_discovery_report.md",
            render_active_discovery_markdown(active_report),
        )
        heuristic_markdown = ""
        if self.heuristic_orchestrator is not None:
            heuristic_summary, heuristic_candidates = self.heuristic_orchestrator.run(
                report,
                active_report,
                relative_root=run_location,
                probe_dispatcher=_DeterministicR0ProbeDispatcher(
                    robot_id=robot.robot_id,
                    run_root=run_root,
                    artifact_prefix=f"artifact://{run_location}",
                    artifacts=self.artifacts,
                    software_policy=self.software_policy,
                    dependency_report_ref=dependency_report_ref,
                    allow_host_runtime_probes=target_probe_mode != "remote",
                ),
            )
            self.artifacts.write_json(
                f"{run_location}/active_discovery_report.json",
                active_report.model_dump(mode="json"),
            )
            report = report.model_copy(
                update={
                    "operation_candidates": heuristic_candidates,
                    "heuristic_analysis_ref": (f"artifact://{run_location}/heuristic/summary.json"),
                    "heuristic_status": heuristic_summary.status.value,
                    "heuristic_mode": heuristic_summary.mode.value,
                    "heuristic_inferred_operation_count": len(
                        heuristic_summary.inferred_operations
                    ),
                    "heuristic_missing_evidence_count": len(heuristic_summary.missing_evidence),
                }
            )
            heuristic_markdown = render_heuristic_summary_markdown(heuristic_summary)
        wiki_insights, insight_fallback_reason = collect_wiki_insights(
            report,
            active_report,
            self.wiki_insight_provider,
        )
        wiki_draft = render_discovery_review_markdown(
            report,
            active_report,
            insight_bundle=wiki_insights,
            previous_report=previous_report,
            previous_active=previous_active,
        )
        if heuristic_markdown:
            wiki_draft = f"{wiki_draft.rstrip()}\n\n{heuristic_markdown}"
        robot_wiki, wiki_generation = generate_robot_wiki(
            wiki_draft,
            self.wiki_polisher,
        )
        wiki_generation = wiki_generation.model_copy(
            update={
                "insight_provider": getattr(self.wiki_insight_provider, "provider", None),
                "insight_count": len(wiki_insights.findings),
                "insight_fallback_reason": insight_fallback_reason,
            }
        )
        self.artifacts.write_text(
            f"{run_location}/robot_wiki.md",
            robot_wiki,
        )
        self.artifacts.write_json(
            f"{run_location}/wiki_insights.json",
            wiki_insights.model_dump(mode="json"),
        )
        self.artifacts.write_json(
            f"{run_location}/wiki_diff.json",
            build_wiki_discovery_diff(
                report,
                active_report,
                previous_report,
                previous_active,
            ).model_dump(mode="json"),
        )
        self.artifacts.write_json(
            f"{run_location}/wiki_generation.json",
            wiki_generation.model_dump(mode="json"),
        )
        self.artifacts.write_json(
            f"{run_location}/capability_manifest.json",
            capability_manifest,
        )
        self.artifacts.write_json(
            f"{run_location}/discovered_capability.json",
            robot.model_dump(mode="json"),
        )
        self.artifacts.write_json(
            f"{run_location}/semantic_context.json",
            semantic_context.model_dump(mode="json"),
        )
        for layer, probe in probes.items():
            self.artifacts.write_json(
                f"{run_location}/{layer}.json",
                probe.model_dump(mode="json"),
            )
        semantic_context_ref = (
            f"artifact://discovery/{robot.robot_id}/runs/{discovery_id}/semantic_context.json"
        )
        discovery_manifest_ref = (
            f"artifact://discovery/{robot.robot_id}/runs/{discovery_id}/manifest.json"
        )
        adapt_inputs = AdaptInputs(
            robot_id=robot.robot_id,
            discovery_id=discovery_id,
            semantic_context_ref=semantic_context_ref,
            robot_wiki_ref=report.review_ref,
            discovery_manifest_ref=discovery_manifest_ref,
            heuristic_analysis_ref=report.heuristic_analysis_ref,
        )
        inputs_payload = adapt_inputs.model_dump(mode="json")
        stage_payloads: dict[str, dict[str, Any]] = {}
        for stage in ("diagnose", "verify"):
            stage_inputs = StageSemanticInputs(
                stage=stage,
                robot_id=robot.robot_id,
                source_discovery_id=discovery_id,
                semantic_context_ref=semantic_context_ref,
                unresolved_semantics=semantic_context.unresolved_semantics,
                semantic_candidates=semantic_context.candidates,
            ).model_dump(mode="json")
            stage_payloads[stage] = stage_inputs

        payload = report.model_dump(mode="json")
        # The immutable run report is its commit marker as well.
        run_path = self.artifacts.write_json(f"{run_location}/report.json", payload)

        manifest = create_discovery_manifest(run_path.parent, robot.robot_id, discovery_id)
        manifest_path = self.artifacts.write_json(
            f"{run_location}/manifest.json", manifest.model_dump(mode="json")
        )
        inputs_payload["discovery_manifest_sha256"] = sha256_file(manifest_path)
        # Publish only small mutable stage indexes; immutable evidence remains in discovery/.
        self.artifacts.write_json(
            layout.relative(layout.stage_latest("adapt", robot.robot_id) / "inputs.json"),
            inputs_payload,
        )
        for stage, stage_inputs in stage_payloads.items():
            self.artifacts.write_json(
                layout.relative(layout.stage_latest(stage, robot.robot_id) / "inputs.json"),
                stage_inputs,
            )
        latest = DiscoveryLatestIndex(
            robot_id=robot.robot_id,
            discovery_id=discovery_id,
            report_sha256=sha256_file(run_path),
            manifest_ref=(
                f"artifact://discovery/{robot.robot_id}/runs/{discovery_id}/manifest.json"
            ),
            manifest_sha256=sha256_file(manifest_path),
            published_at=now,
        )
        # latest.json is the atomic commit marker for readers of the latest snapshot.
        self.artifacts.write_json(
            layout.relative(layout.discovery_latest(robot.robot_id)),
            latest.model_dump(mode="json"),
        )
        return report, run_path


def load_latest_report(artifact_root: Path, robot_id: str) -> DiscoveryReport:
    index_path = ArtifactLayout(artifact_root).discovery_latest(robot_id)
    if not index_path.is_file():
        raise FileNotFoundError(
            f"No discovery report for {robot_id}; run robotctl adapt discover run first"
        )
    index = DiscoveryLatestIndex.model_validate_json(index_path.read_text(encoding="utf-8"))
    if index.robot_id != robot_id or Path(index.discovery_id).name != index.discovery_id:
        raise ValueError(f"Invalid latest discovery index for {robot_id}")
    _, manifest_path = load_and_verify_discovery_manifest(
        artifact_root, robot_id, index.discovery_id
    )
    if sha256_file(manifest_path) != index.manifest_sha256:
        raise ValueError(f"Latest discovery manifest hash mismatch: {index.discovery_id}")
    report_path = (
        ArtifactLayout(artifact_root).discovery_run(robot_id, index.discovery_id) / "report.json"
    )
    if not report_path.is_file():
        raise FileNotFoundError(f"Latest discovery run is incomplete: {index.discovery_id}")
    if sha256_file(report_path) != index.report_sha256:
        raise ValueError(f"Latest discovery report hash mismatch: {index.discovery_id}")
    report = DiscoveryReport.model_validate_json(report_path.read_text(encoding="utf-8"))
    if report.robot_id != robot_id or report.discovery_id != index.discovery_id:
        raise ValueError(f"Latest discovery report identity mismatch: {index.discovery_id}")
    return report


def load_report(artifact_root: Path, robot_id: str, discovery_id: str) -> DiscoveryReport:
    load_and_verify_discovery_manifest(artifact_root, robot_id, discovery_id)
    path = ArtifactLayout(artifact_root).discovery_run(robot_id, discovery_id) / "report.json"
    if not path.is_file():
        raise FileNotFoundError(f"No discovery report {discovery_id} for {robot_id}")
    return DiscoveryReport.model_validate_json(path.read_text(encoding="utf-8"))
