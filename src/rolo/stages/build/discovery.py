"""Stage 1 bounded hardware, software, ROS, and application discovery."""

from __future__ import annotations

import math
import os
import platform
import re
import shlex
import shutil
import subprocess
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from packaging.requirements import InvalidRequirement, Requirement

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

from rolo.core.artifacts import ArtifactStore
from rolo.core.hashing import sha256_file
from rolo.core.models import (
    DiscoveryLatestIndex,
    DiscoveryReport,
    DiscoveryStatus,
    ProbeResult,
    RobotCapability,
    ToolDescriptor,
)
from rolo.stages.build.active_discovery import (
    ActiveDiscoveryAnalyzer,
    ActiveDiscoveryInputs,
    ActiveProbeMode,
    render_active_discovery_markdown,
)
from rolo.stages.build.enrollment import load_urdf_profile
from rolo.stages.build.inputs import (
    BuildInputs,
    BuildInputsStatus,
    SemanticCandidate,
    SemanticContext,
    StageSemanticInputs,
)
from rolo.stages.build.software_relevance import (
    CandidateResolutionStatus,
    DirectDependencyResolver,
    ResolutionStatus,
    SoftwareDiscoveryPolicy,
    SoftwareSummary,
    build_software_summary,
    enrich_active_report,
)

MAX_COMMAND_OUTPUT = 200_000
MAX_SOURCE_FILES = 10_000
MAX_DISCOVERED_ITEMS = 1_000
SKIP_DIRECTORIES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "build",
    "dist",
    "install",
    "log",
    "artifacts",
    "__pycache__",
}
UBUNTU_ROS_DEFAULTS = {"20.04": "foxy", "22.04": "humble", "24.04": "jazzy"}
SAFE_ENV_KEYS = (
    "ROS_DISTRO",
    "ROS_DOMAIN_ID",
    "ROS_LOCALHOST_ONLY",
    "RMW_IMPLEMENTATION",
    "AMENT_PREFIX_PATH",
    "COLCON_PREFIX_PATH",
)
SEMANTIC_PARAMETER_ALIASES = {
    "max_vel_x": ("geometry.hard_max_linear_velocity_mps", "m/s"),
    "max_linear_velocity": ("geometry.hard_max_linear_velocity_mps", "m/s"),
    "max_linear_speed": ("geometry.hard_max_linear_velocity_mps", "m/s"),
    "max_vel_theta": ("geometry.hard_max_angular_velocity_radps", "rad/s"),
    "max_angular_velocity": ("geometry.hard_max_angular_velocity_radps", "rad/s"),
    "max_angular_speed": ("geometry.hard_max_angular_velocity_radps", "rad/s"),
}


def _read_text(path: Path, limit: int = MAX_COMMAND_OUTPUT) -> str | None:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as stream:
            return stream.read(limit)
    except OSError:
        return None


def _run(args: Sequence[str], *, timeout_s: float = 8.0) -> dict[str, Any]:
    executable = shutil.which(args[0])
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


class HardwareProbe:
    def run(self) -> ProbeResult:
        device_tree_model = _device_tree_model()
        data: dict[str, Any] = {
            "architecture": platform.machine().lower(),
            "processor": platform.processor() or None,
            "device_tree_model": device_tree_model,
            "compute_platform": detect_compute_platform(device_tree_model),
            "devices": [],
            "buses": {},
            "thermal_zones": [],
        }
        warnings: list[str] = []
        if platform.system() != "Linux":
            warnings.append("Linux /sys and /dev hardware enumeration is unavailable on this host")
            return ProbeResult(
                layer="hw", status=DiscoveryStatus.PARTIAL, data=data, warnings=warnings
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
                    data["devices"].append(
                        {
                            "path": str(path),
                            "category": modality,
                            "semantic_candidate": f"semantic://device/{modality}/{path.name}",
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

        for zone in sorted(Path("/sys/class/thermal").glob("thermal_zone*")):
            zone_type = _read_text(zone / "type", 256)
            temperature = _read_text(zone / "temp", 256)
            if zone_type and temperature:
                try:
                    value_c = float(temperature.strip()) / 1000.0
                except ValueError:
                    continue
                data["thermal_zones"].append({"name": zone_type.strip(), "temperature_c": value_c})

        return ProbeResult(
            layer="hw", status=DiscoveryStatus.SUCCEEDED, data=data, warnings=warnings
        )


class LinuxProbe:
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
            "environment": {key: os.environ[key] for key in SAFE_ENV_KEYS if key in os.environ},
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
            result = _run(command, timeout_s=5)
            data["executables"][name] = {
                "path": shutil.which(command[0]),
                "available": result.get("available", False),
                "version_output": (result.get("stdout") or result.get("stderr") or "").splitlines()[
                    :1
                ],
            }

        if platform.system() == "Linux":
            processes = _run(["ps", "-eo", "pid=,ppid=,stat=,comm="])
            if processes.get("returncode") == 0:
                data["processes"] = processes["stdout"].splitlines()[:MAX_DISCOVERED_ITEMS]
        else:
            warnings.append("Linux process probes were skipped on a non-Linux host")

        status = (
            DiscoveryStatus.SUCCEEDED if platform.system() == "Linux" else DiscoveryStatus.PARTIAL
        )
        return ProbeResult(layer="linux", status=status, data=data, warnings=warnings)


class RosProbe:
    def _resolve_setup(self) -> Path | None:
        ros_root = Path("/opt/ros")
        os_version = _parse_os_release().get("VERSION_ID")
        preferred = [os.environ.get("ROS_DISTRO"), UBUNTU_ROS_DEFAULTS.get(os_version)]
        if ros_root.is_dir():
            preferred.extend(sorted(path.name for path in ros_root.iterdir() if path.is_dir()))
        for distro in dict.fromkeys(item for item in preferred if item):
            setup = ros_root / distro / "setup.bash"
            if setup.is_file():
                return setup
        return None

    def _run_ros(self, args: Sequence[str]) -> dict[str, Any]:
        if shutil.which("ros2"):
            return _run(["ros2", *args], timeout_s=10)
        setup = self._resolve_setup()
        if setup is not None and shutil.which("bash"):
            command = f"source {shlex.quote(str(setup))} && ros2 {shlex.join(args)}"
            return _run(["bash", "-lc", command], timeout_s=10)
        return {"available": False, "error": "ROS 2 environment not found"}

    def run(self) -> ProbeResult:
        installed_distros: list[str] = []
        ros_root = Path("/opt/ros")
        if ros_root.is_dir():
            installed_distros = sorted(path.name for path in ros_root.iterdir() if path.is_dir())
        setup = self._resolve_setup()
        data: dict[str, Any] = {
            "ros_distro": os.environ.get("ROS_DISTRO") or (setup.parent.name if setup else None),
            "installed_distros": installed_distros,
            "domain_id": os.environ.get("ROS_DOMAIN_ID", "0"),
            "rmw": os.environ.get("RMW_IMPLEMENTATION"),
            "nodes": [],
            "topics": [],
            "services": [],
            "actions": [],
        }
        warnings: list[str] = []
        command_map = {
            "nodes": ["node", "list"],
            "topics": ["topic", "list", "-t"],
            "services": ["service", "list", "-t"],
            "actions": ["action", "list", "-t"],
        }
        successes = 0
        for field, args in command_map.items():
            result = self._run_ros(args)
            if result.get("returncode") == 0:
                data[field] = result["stdout"].splitlines()[:MAX_DISCOVERED_ITEMS]
                successes += 1
            else:
                warnings.append(
                    f"ros2 {' '.join(args)} unavailable: {result.get('error', 'failed')}"
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


def _walk_source(root: Path) -> tuple[list[Path], bool]:
    files: list[Path] = []
    truncated = False
    for directory, names, filenames in os.walk(root):
        names[:] = sorted(name for name in names if name not in SKIP_DIRECTORIES)
        for filename in sorted(filenames):
            files.append(Path(directory) / filename)
            if len(files) >= MAX_SOURCE_FILES:
                truncated = True
                return files, truncated
    return files, truncated


def _extract_ros_names(text: str) -> dict[str, list[str]]:
    patterns = {
        "topics": r"create_(?:publisher|subscription)\([^,]+,\s*['\"]([^'\"]+)",
        "services": r"create_(?:service|client)\([^,]+,\s*['\"]([^'\"]+)",
        "actions": r"(?:ActionServer|ActionClient)\([^,]+,\s*[^,]+,\s*['\"]([^'\"]+)",
    }
    return {key: sorted(set(re.findall(pattern, text))) for key, pattern in patterns.items()}


def _extract_ros_interfaces(text: str, source_path: Path) -> list[dict[str, str]]:
    patterns = {
        "publisher": r"create_publisher\(\s*([^,]+),\s*['\"]([^'\"]+)",
        "subscriber": r"create_subscription\(\s*([^,]+),\s*['\"]([^'\"]+)",
        "service": r"create_service\(\s*([^,]+),\s*['\"]([^'\"]+)",
        "client": r"create_client\(\s*([^,]+),\s*['\"]([^'\"]+)",
    }
    interfaces: list[dict[str, str]] = []
    for role, pattern in patterns.items():
        for message_type, name in re.findall(pattern, text):
            interfaces.append(
                {
                    "role": role,
                    "name": name,
                    "type": message_type.strip(),
                    "source": str(source_path),
                }
            )
    return interfaces


def _extract_protocols(text: str) -> list[str]:
    pattern = re.compile(
        r"(?i)\b(tcp|udp|http|https|grpc|websocket|mqtt|serial|socketcan|can|dbus)\b"
    )
    return sorted({match.lower() for match in pattern.findall(text)})


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


class ApplicationProbe:
    def run(self, source_roots: Sequence[Path]) -> ProbeResult:
        projects: list[dict[str, Any]] = []
        warnings: list[str] = []
        for requested_root in source_roots:
            root = requested_root.expanduser().resolve()
            if not root.is_dir():
                warnings.append(f"source root does not exist: {root}")
                continue
            files, truncated = _walk_source(root)
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
                                        str(requirement.marker)
                                        if requirement.marker
                                        else None
                                    ),
                                    "applicable": (
                                        requirement.marker is None
                                        or requirement.marker.evaluate()
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
            if "setup.py" in relative_names or "setup.cfg" in relative_names:
                project["build_systems"].append("python/setuptools")
            if "CMakeLists.txt" in relative_names:
                project["build_systems"].append("cmake")
            if "Cargo.toml" in relative_names:
                project["build_systems"].append("rust/cargo")

            ros_names: dict[str, set[str]] = {"topics": set(), "services": set(), "actions": set()}
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
                is_launch_file = path.name.endswith(".launch.py") or path.suffix in {
                    ".xml",
                    ".yaml",
                    ".yml",
                }
                if is_launch_file and "launch" in lower:
                    project["launch_files"].append(relative)
                if path.name.lower().startswith("readme"):
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
                    candidate_text = _read_text(path, 2_000_000)
                    if candidate_text:
                        project["semantic_candidates"].extend(
                            _extract_semantic_candidates(
                                candidate_text,
                                source_path=path,
                                source_kind=candidate_source_kind,
                            )
                        )
                if path.name in {
                    "pyproject.toml",
                    "setup.py",
                    "setup.cfg",
                    "package.xml",
                    "CMakeLists.txt",
                }:
                    project["manifest_digests"][relative] = sha256_file(path)
                if path.suffix.lower() in source_suffixes and path.stat().st_size <= 2_000_000:
                    text = _read_text(path, 2_000_000)
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
                        extracted = _extract_ros_names(text)
                        for kind, values in extracted.items():
                            ros_names[kind].update(values)
                        project["ros_interfaces"].extend(
                            _extract_ros_interfaces(text, path)
                        )
                        project["protocols"].extend(_extract_protocols(text))
                if path.name == "CMakeLists.txt" and path.stat().st_size <= 2_000_000:
                    cmake_text = _read_text(path, 2_000_000) or ""
                    targets = re.findall(
                        r"(?im)^\s*add_(?:executable|library)\s*\(\s*([A-Za-z0-9_.+-]+)",
                        cmake_text,
                    )
                    project["build_targets"].extend(targets)
                    project["entrypoints"].extend(
                        {"name": target, "target": target, "source": "cmake"}
                        for target in targets
                    )

            for kind, values in ros_names.items():
                project["ros_names"][kind] = sorted(values)[:MAX_DISCOVERED_ITEMS]
            project["packages"] = sorted(set(project["packages"]))
            project["languages"] = sorted(set(project["languages"]))
            project["build_targets"] = sorted(set(project["build_targets"]))
            project["declared_dependencies"] = sorted(
                set(project["declared_dependencies"])
            )
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
            project["ros_interfaces"] = sorted(
                project["ros_interfaces"],
                key=lambda item: (item["role"], item["name"], item["type"], item["source"]),
            )[:MAX_DISCOVERED_ITEMS]
            project["launch_files"] = project["launch_files"][:MAX_DISCOVERED_ITEMS]
            project["config_files"] = project["config_files"][:MAX_DISCOVERED_ITEMS]
            project["semantic_candidates"] = project["semantic_candidates"][
                :MAX_DISCOVERED_ITEMS
            ]
            revision = _run(["git", "-C", str(root), "rev-parse", "HEAD"], timeout_s=5)
            if revision.get("returncode") == 0:
                project["source_revision"] = revision["stdout"].strip()
            projects.append(project)

        if projects:
            status = DiscoveryStatus.PARTIAL if warnings else DiscoveryStatus.SUCCEEDED
        else:
            status = DiscoveryStatus.UNAVAILABLE
        return ProbeResult(
            layer="application", status=status, data={"projects": projects}, warnings=warnings
        )


def _ros_entity_name(value: str) -> str:
    return value.split(" ", 1)[0].strip()


def _semantic_bindings(probes: dict[str, ProbeResult]) -> dict[str, dict[str, Any]]:
    bindings: dict[str, dict[str, Any]] = {}
    topic_rules = {
        "cmd_vel": "semantic://actuator/base/velocity_command",
        "odom": "semantic://state/base/odometry",
        "scan": "semantic://sensor/range_scan_2d",
        "image": "semantic://sensor/front_camera/image",
        "imu": "semantic://sensor/imu",
        "map": "semantic://environment/map_2d",
        "battery": "semantic://power/battery_state",
    }
    topic_evidence = [
        (raw_topic, "ros2_topic", "live_ros_graph")
        for raw_topic in probes["ros"].data.get("topics", [])
    ]
    for project in probes["application"].data.get("projects", []):
        topic_evidence.extend(
            (topic, "ros2_topic_candidate", f"source:{project['root']}")
            for topic in project.get("ros_names", {}).get("topics", [])
        )
    for raw_topic, transport, source in topic_evidence:
        topic = _ros_entity_name(raw_topic)
        lowered = topic.lower()
        for token, semantic_uri in topic_rules.items():
            if token in lowered and semantic_uri not in bindings:
                bindings[semantic_uri] = {
                    "transport": transport,
                    "binding": topic,
                    "status": "DISCOVERED_UNVERIFIED",
                    "evidence": source,
                }
    return bindings


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
        "compatibility": {
            "status": "MATCH" if not mismatches else "MISMATCH",
            "mismatches": mismatches,
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
        "geometry.hard_max_linear_velocity_mps": robot.geometry.get(
            "hard_max_linear_velocity_mps"
        ),
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


def _read_discovery_urdf(robot: RobotCapability, urdf_path: Path) -> RobotCapability:
    """Load the explicitly supplied URDF into a discovery-time capability snapshot."""
    enrollment = dict(robot.features.get("enrollment", {}))
    profile = load_urdf_profile(urdf_path)
    enrollment.update(
        {
            "profile_id": profile.profile_id,
            "profile_format": "urdf",
            "profile_path": str(profile.path),
            "profile_sha256": profile.sha256,
            "urdf_status": "SCANNED",
            "semantic_status": (
                "RESOLVED" if not profile.unresolved_semantics else "PARTIAL"
            ),
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


def _tool(
    operation: str,
    cli: str,
    layer: str,
    description: str,
    *,
    availability: str = "AVAILABLE",
    adapter: str = "builtin.discovery",
    risk: str = "R0",
    access: str = "read",
    idempotent: bool = True,
    bindings: Sequence[str] = (),
    evidence: Sequence[str] = (),
    limitations: Sequence[str] = (),
) -> ToolDescriptor:
    return ToolDescriptor(
        operation=operation,
        canonical_cli=cli.split(),
        layer=layer,
        description=description,
        risk=risk,
        access=access,
        idempotent=idempotent,
        availability=availability,
        adapter=adapter,
        semantic_bindings=list(bindings),
        evidence=list(evidence),
        limitations=list(limitations),
    )


def _build_tool_catalog(
    probes: dict[str, ProbeResult], bindings: dict[str, dict[str, Any]]
) -> list[ToolDescriptor]:
    tools = [
        _tool("hw.inventory.scan", "robotctl hw inventory scan", "hw", "Enumerate hardware"),
        _tool("linux.host.inspect", "robotctl linux host inspect", "linux", "Inspect host stack"),
        _tool(
            "ros.graph.snapshot",
            "robotctl ros graph snapshot",
            "ros",
            "Snapshot the live ROS graph",
            availability=(
                "AVAILABLE"
                if probes["ros"].status in {DiscoveryStatus.SUCCEEDED, DiscoveryStatus.PARTIAL}
                else "UNAVAILABLE"
            ),
        ),
        _tool(
            "app.robot.discover",
            "robotctl app robot discover",
            "app",
            "Discover application projects and candidate capabilities",
        ),
        _tool("tool.catalog", "robotctl tool catalog", "control", "Read generated tool catalog"),
    ]
    semantic_to_operations = {
        "semantic://actuator/base/velocity_command": (
            "app.teleop.velocity",
            "robotctl app teleop velocity",
            "R3",
            "write",
        ),
        "semantic://state/base/odometry": (
            "app.localization.status",
            "robotctl app localization status",
            "R0",
            "read",
        ),
        "semantic://environment/map_2d": (
            "app.map.inspect",
            "robotctl app map inspect",
            "R0",
            "read",
        ),
    }
    for semantic_uri, (operation, cli, risk, access) in semantic_to_operations.items():
        if semantic_uri not in bindings:
            continue
        tools.append(
            _tool(
                operation,
                cli,
                "app",
                "Candidate application operation inferred from a discovered semantic binding",
                availability="DISCOVERED_UNVERIFIED",
                adapter="generated.binding_candidate",
                risk=risk,
                access=access,
                idempotent=access == "read",
                bindings=[semantic_uri],
                evidence=[bindings[semantic_uri]["binding"]],
                limitations=["Requires adapter generation and conformance tests before execution"],
            )
        )
    return tools


class DiscoveryService:
    def __init__(
        self,
        artifacts: ArtifactStore,
        software_policy: SoftwareDiscoveryPolicy | None = None,
    ) -> None:
        self.artifacts = artifacts
        self.software_policy = software_policy or SoftwareDiscoveryPolicy()

    def run(
        self,
        *,
        robot: RobotCapability,
        urdf_path: Path,
        source_roots: Sequence[Path] | None = None,
        active_inputs: ActiveDiscoveryInputs | None = None,
    ) -> tuple[DiscoveryReport, Path]:
        if active_inputs is not None and source_roots is not None:
            raise ValueError("pass active_inputs or source_roots, not both")
        if active_inputs is None:
            active_inputs = ActiveDiscoveryInputs(
                source_roots=list(source_roots or []),
                active_probe=ActiveProbeMode.RUNTIME_READONLY,
            )
        active_inputs = active_inputs.resolved()
        robot = _read_discovery_urdf(robot, urdf_path)
        now = datetime.now(timezone.utc)
        discovery_id = f"disc-{now.strftime('%Y%m%dT%H%M%S')}-{uuid4().hex[:8]}"
        software_summary_ref = (
            f"artifact://discovery/{robot.robot_id}/runs/{discovery_id}/software_summary.json"
        )
        dependency_report_ref = (
            f"artifact://discovery/{robot.robot_id}/runs/{discovery_id}/"
            "direct_dependencies.json"
        )
        ros_probe = (
            RosProbe().run()
            if active_inputs.active_probe == ActiveProbeMode.RUNTIME_READONLY
            else ProbeResult(
                layer="ros",
                status=DiscoveryStatus.UNAVAILABLE,
                data={"nodes": [], "topics": [], "services": [], "actions": []},
                warnings=["ROS runtime inspection was not requested"],
            )
        )
        probes = {
            "hw": HardwareProbe().run(),
            "linux": LinuxProbe().run(),
            "ros": ros_probe,
            "application": ApplicationProbe().run(active_inputs.source_roots),
        }
        bindings = _semantic_bindings(probes)
        tools = _build_tool_catalog(probes, bindings)
        applicable_probes = {
            name: probe
            for name, probe in probes.items()
            if (name != "application" or active_inputs.source_roots)
            and (
                name != "ros"
                or active_inputs.active_probe == ActiveProbeMode.RUNTIME_READONLY
            )
        }
        statuses = {probe.status for probe in applicable_probes.values()}
        if DiscoveryStatus.FAILED in statuses:
            status = DiscoveryStatus.FAILED
        elif statuses == {DiscoveryStatus.SUCCEEDED}:
            status = DiscoveryStatus.SUCCEEDED
        else:
            status = DiscoveryStatus.PARTIAL
        run_location = f"discovery/{robot.robot_id}/runs/{discovery_id}"
        active_report_ref = f"artifact://{run_location}/active_discovery_report.json"
        active_report = ActiveDiscoveryAnalyzer(
            inputs=active_inputs,
            projects=probes["application"].data.get("projects", []),
            ros_probe=probes["ros"],
            tools=tools,
            run_root=self.artifacts.root / run_location,
            artifact_prefix=f"artifact://{run_location}",
        ).build(
            discovery_id=discovery_id,
            robot_id=robot.robot_id,
            technical_status=status.value,
            created_at=now,
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
            discovery_id=discovery_id,
            report=dependency_report,
            dependency_report_ref=dependency_report_ref,
        )
        capability_manifest = _capability_manifest(robot, probes, bindings, software_summary)
        if (
            dependency_report.status == ResolutionStatus.PARTIAL
            and status == DiscoveryStatus.SUCCEEDED
        ):
            status = DiscoveryStatus.PARTIAL
        if not active_report.executables and status != DiscoveryStatus.FAILED:
            status = DiscoveryStatus.PARTIAL
            active_report.technical_status = status.value
        elif (
            active_report.technical_status == DiscoveryStatus.PARTIAL.value
            and status == DiscoveryStatus.SUCCEEDED
        ):
            status = DiscoveryStatus.PARTIAL
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
            tool_catalog=tools,
            software_summary=software_summary.model_dump(mode="json"),
            software_summary_ref=software_summary_ref,
            dependency_report_ref=dependency_report_ref,
            active_discovery_report_ref=active_report_ref,
            discovery_mode=active_report.discovery_mode.level.value,
            source_roots=[str(path) for path in active_inputs.source_roots],
            created_at=now,
        )
        payload = report.model_dump(mode="json")
        self.artifacts.write_json(
            f"discovery/{robot.robot_id}/runs/{discovery_id}/software_summary.json",
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
        catalog_payload = {
            "schema_version": "robot-tool-catalog/v1",
            "robot_id": robot.robot_id,
            "discovery_id": discovery_id,
            "tools": [tool.model_dump(mode="json") for tool in tools],
        }
        self.artifacts.write_json(f"{run_location}/tool_catalog.json", catalog_payload)
        unresolved = [
            f"{layer}:{probe.status}"
            for layer, probe in probes.items()
            if probe.status != DiscoveryStatus.SUCCEEDED
            and not (
                layer == "ros"
                and active_inputs.active_probe != ActiveProbeMode.RUNTIME_READONLY
            )
        ]
        unresolved.extend(
            f"dependency:{candidate.ecosystem}:{candidate.name}:{candidate.status.value}"
            for candidate in dependency_report.candidates
            if candidate.required
            and candidate.status
            in {
                CandidateResolutionStatus.MISSING,
                CandidateResolutionStatus.VERSION_CONFLICT,
                CandidateResolutionStatus.UNKNOWN,
            }
        )
        unresolved.extend(
            f"dependency:executable:{executable_id}:UNKNOWN"
            for executable_id in dependency_report.unresolved_executables
        )
        unresolved.extend(
            f"compatibility:{item['field']}"
            for item in capability_manifest["compatibility"]["mismatches"]
        )
        semantic_context_ref = (
            f"artifact://discovery/{robot.robot_id}/runs/{discovery_id}/semantic_context.json"
        )
        inputs_status = (
            BuildInputsStatus.BLOCKED
            if status == DiscoveryStatus.FAILED
            else BuildInputsStatus.AWAITING_CONFIRMATION
        )
        build_inputs = BuildInputs(
            robot_id=robot.robot_id,
            discovery_id=discovery_id,
            status=inputs_status,
            capability_manifest_ref=(
                f"artifact://discovery/{robot.robot_id}/runs/{discovery_id}/"
                "capability_manifest.json"
            ),
            semantic_bindings_ref=(
                f"artifact://discovery/{robot.robot_id}/runs/{discovery_id}/"
                "report.json#/semantic_bindings"
            ),
            semantic_context_ref=semantic_context_ref,
            tool_catalog_ref=(
                f"artifact://discovery/{robot.robot_id}/runs/{discovery_id}/tool_catalog.json"
            ),
            software_summary_ref=software_summary_ref,
            dependency_report_ref=dependency_report_ref,
            active_discovery_report_ref=active_report_ref,
            probe_refs={
                layer: (
                    f"artifact://discovery/{robot.robot_id}/runs/{discovery_id}/{layer}.json"
                )
                for layer in probes
            },
            semantic_binding_candidates=len(bindings),
            semantic_value_candidates=len(semantic_context.candidates),
            tool_count=len(tools),
            unresolved_dependencies=unresolved,
            unresolved_semantics=semantic_context.unresolved_semantics,
        )
        inputs_payload = build_inputs.model_dump(mode="json")
        self.artifacts.write_json(
            f"build/{robot.robot_id}/runs/{discovery_id}/inputs.json", inputs_payload
        )
        self.artifacts.write_json(
            f"build/{robot.robot_id}/runs/{discovery_id}/semantic_context.json",
            semantic_context.model_dump(mode="json"),
        )
        stage_payloads: dict[str, dict[str, Any]] = {}
        for stage in ("debug", "test"):
            stage_inputs = StageSemanticInputs(
                stage=stage,
                robot_id=robot.robot_id,
                source_discovery_id=discovery_id,
                semantic_context_ref=semantic_context_ref,
                unresolved_semantics=semantic_context.unresolved_semantics,
                semantic_candidates=semantic_context.candidates,
            ).model_dump(mode="json")
            stage_payloads[stage] = stage_inputs
            self.artifacts.write_json(
                f"{stage}/{robot.robot_id}/runs/{discovery_id}/inputs.json", stage_inputs
            )

        # The immutable run report is its commit marker as well.
        run_path = self.artifacts.write_json(f"{run_location}/report.json", payload)

        # Publish downstream convenience inputs before advancing the discovery index.
        self.artifacts.write_json(
            f"build/{robot.robot_id}/latest/inputs.json", inputs_payload
        )
        self.artifacts.write_json(
            f"build/{robot.robot_id}/latest/semantic_context.json",
            semantic_context.model_dump(mode="json"),
        )
        for stage, stage_inputs in stage_payloads.items():
            self.artifacts.write_json(
                f"{stage}/{robot.robot_id}/latest/inputs.json", stage_inputs
            )
        latest = DiscoveryLatestIndex(
            robot_id=robot.robot_id,
            discovery_id=discovery_id,
            report_sha256=sha256_file(run_path),
            published_at=now,
        )
        # latest.json is the atomic commit marker for readers of the latest snapshot.
        self.artifacts.write_json(
            f"discovery/{robot.robot_id}/latest.json",
            latest.model_dump(mode="json"),
        )
        return report, run_path


def load_latest_report(artifact_root: Path, robot_id: str) -> DiscoveryReport:
    index_path = artifact_root / "discovery" / robot_id / "latest.json"
    if not index_path.is_file():
        raise FileNotFoundError(
            f"No discovery report for {robot_id}; run robotctl build discover run first"
        )
    index = DiscoveryLatestIndex.model_validate_json(index_path.read_text(encoding="utf-8"))
    if index.robot_id != robot_id or Path(index.discovery_id).name != index.discovery_id:
        raise ValueError(f"Invalid latest discovery index for {robot_id}")
    report_path = (
        artifact_root
        / "discovery"
        / robot_id
        / "runs"
        / index.discovery_id
        / "report.json"
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
    path = artifact_root / "discovery" / robot_id / "runs" / discovery_id / "report.json"
    if not path.is_file():
        raise FileNotFoundError(f"No discovery report {discovery_id} for {robot_id}")
    return DiscoveryReport.model_validate_json(path.read_text(encoding="utf-8"))
