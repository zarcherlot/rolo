from __future__ import annotations

import hashlib
import os
import platform
import re
import shlex
import shutil
import subprocess
import tomllib
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from robot_loop.artifacts import ArtifactStore
from robot_loop.models import (
    DiscoveryReport,
    DiscoveryStatus,
    ProbeResult,
    RobotCapability,
    ToolDescriptor,
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
SAFE_ENV_KEYS = (
    "ROS_DISTRO",
    "ROS_DOMAIN_ID",
    "ROS_LOCALHOST_ONLY",
    "RMW_IMPLEMENTATION",
    "AMENT_PREFIX_PATH",
    "COLCON_PREFIX_PATH",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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
            "packages": [],
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
            packages = _run(["dpkg-query", "-W", "-f=${Package}\t${Version}\n"], timeout_s=15)
            if packages.get("returncode") == 0:
                data["packages"] = packages["stdout"].splitlines()[:MAX_DISCOVERED_ITEMS]
            else:
                warnings.append("dpkg package inventory is unavailable")
        else:
            warnings.append("Linux process and dpkg probes were skipped on a non-Linux host")

        status = (
            DiscoveryStatus.SUCCEEDED if platform.system() == "Linux" else DiscoveryStatus.PARTIAL
        )
        return ProbeResult(layer="linux", status=status, data=data, warnings=warnings)


class RosProbe:
    def _run_ros(self, args: Sequence[str]) -> dict[str, Any]:
        if shutil.which("ros2"):
            return _run(["ros2", *args], timeout_s=10)
        setup = Path("/opt/ros/humble/setup.bash")
        if setup.is_file() and shutil.which("bash"):
            command = f"source {shlex.quote(str(setup))} && ros2 {shlex.join(args)}"
            return _run(["bash", "-lc", command], timeout_s=10)
        return {"available": False, "error": "ROS 2 environment not found"}

    def run(self) -> ProbeResult:
        installed_distros: list[str] = []
        ros_root = Path("/opt/ros")
        if ros_root.is_dir():
            installed_distros = sorted(path.name for path in ros_root.iterdir() if path.is_dir())
        data: dict[str, Any] = {
            "ros_distro": os.environ.get("ROS_DISTRO"),
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
                "ros_names": {"topics": [], "services": [], "actions": []},
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
                if path.name in {
                    "pyproject.toml",
                    "setup.py",
                    "setup.cfg",
                    "package.xml",
                    "CMakeLists.txt",
                }:
                    project["manifest_digests"][relative] = _sha256(path)
                if path.suffix.lower() in source_suffixes and path.stat().st_size <= 2_000_000:
                    text = _read_text(path, 2_000_000)
                    if text:
                        extracted = _extract_ros_names(text)
                        for kind, values in extracted.items():
                            ros_names[kind].update(values)

            for kind, values in ros_names.items():
                project["ros_names"][kind] = sorted(values)[:MAX_DISCOVERED_ITEMS]
            project["packages"] = sorted(set(project["packages"]))
            project["launch_files"] = project["launch_files"][:MAX_DISCOVERED_ITEMS]
            project["config_files"] = project["config_files"][:MAX_DISCOVERED_ITEMS]
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
) -> dict[str, Any]:
    expected_arch = str(robot.platform.get("architecture", "")).lower()
    expected_compute = str(robot.platform.get("compute", "auto_discover")).lower()
    observed_arch = str(probes["hw"].data.get("architecture", "")).lower()
    arch_aliases = {"aarch64": "arm64", "x86_64": "amd64", "amd64": "amd64"}
    normalized_observed = arch_aliases.get(observed_arch, observed_arch)
    mismatches: list[dict[str, Any]] = []
    if expected_arch and normalized_observed and expected_arch != normalized_observed:
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
    if expected_ros and expected_ros != ros_distro and expected_ros not in installed_distros:
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
            "software_stack": probes["linux"].data,
            "ros_graph": probes["ros"].data,
            "applications": probes["application"].data.get("projects", []),
        },
        "semantic_bindings": bindings,
        "compatibility": {
            "status": "MATCH" if not mismatches else "MISMATCH",
            "mismatches": mismatches,
        },
    }


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
    def __init__(self, artifacts: ArtifactStore) -> None:
        self.artifacts = artifacts

    def run(
        self,
        *,
        robot: RobotCapability,
        source_roots: Sequence[Path],
    ) -> tuple[DiscoveryReport, Path]:
        probes = {
            "hw": HardwareProbe().run(),
            "linux": LinuxProbe().run(),
            "ros": RosProbe().run(),
            "application": ApplicationProbe().run(source_roots),
        }
        bindings = _semantic_bindings(probes)
        tools = _build_tool_catalog(probes, bindings)
        capability_manifest = _capability_manifest(robot, probes, bindings)
        statuses = {probe.status for probe in probes.values()}
        if DiscoveryStatus.FAILED in statuses:
            status = DiscoveryStatus.FAILED
        elif statuses == {DiscoveryStatus.SUCCEEDED}:
            status = DiscoveryStatus.SUCCEEDED
        else:
            status = DiscoveryStatus.PARTIAL
        now = datetime.now(UTC)
        discovery_id = f"disc-{now.strftime('%Y%m%dT%H%M%S')}-{uuid4().hex[:8]}"
        report = DiscoveryReport(
            discovery_id=discovery_id,
            robot_id=robot.robot_id,
            status=status,
            platform=robot.platform,
            capability_manifest=capability_manifest,
            probes=probes,
            semantic_bindings=bindings,
            tool_catalog=tools,
            source_roots=[str(path.expanduser().resolve()) for path in source_roots],
            created_at=now,
        )
        payload = report.model_dump(mode="json")
        run_path = self.artifacts.write_json(
            f"discovery/{robot.robot_id}/runs/{discovery_id}/report.json", payload
        )
        self.artifacts.write_json(f"discovery/{robot.robot_id}/latest/report.json", payload)
        for location in (f"runs/{discovery_id}", "latest"):
            self.artifacts.write_json(
                f"discovery/{robot.robot_id}/{location}/capability_manifest.json",
                capability_manifest,
            )
        for layer, probe in probes.items():
            for location in (f"runs/{discovery_id}", "latest"):
                self.artifacts.write_json(
                    f"discovery/{robot.robot_id}/{location}/{layer}.json",
                    probe.model_dump(mode="json"),
                )
        catalog_payload = {
            "schema_version": "robot-tool-catalog/v1",
            "robot_id": robot.robot_id,
            "discovery_id": discovery_id,
            "tools": [tool.model_dump(mode="json") for tool in tools],
        }
        for location in (f"runs/{discovery_id}", "latest"):
            self.artifacts.write_json(
                f"discovery/{robot.robot_id}/{location}/tool_catalog.json",
                catalog_payload,
            )
        return report, run_path


def load_latest_report(artifact_root: Path, robot_id: str) -> DiscoveryReport:
    path = artifact_root / "discovery" / robot_id / "latest" / "report.json"
    if not path.is_file():
        raise FileNotFoundError(
            f"No discovery report for {robot_id}; run robotctl discover run first"
        )
    return DiscoveryReport.model_validate_json(path.read_text(encoding="utf-8"))
