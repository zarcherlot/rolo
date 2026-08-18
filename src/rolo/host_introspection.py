"""Bounded, read-only host introspection used before and during Adapt discovery."""

from __future__ import annotations

import csv
import getpass
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_OUTPUT = 200_000
MAX_ITEMS = 1_000
MAX_HASH_BYTES = 256 * 1024 * 1024
CONFIG_SUFFIXES = {".conf", ".ini", ".json", ".toml", ".xml", ".yaml", ".yml"}
SAFE_ENV_KEYS = {
    "AMENT_PREFIX_PATH",
    "COLCON_PREFIX_PATH",
    "ROS_DISTRO",
    "ROS_DOMAIN_ID",
    "ROS_LOCALHOST_ONLY",
    "RMW_IMPLEMENTATION",
}
SECRET_KEY = re.compile(r"(?i)(?:password|passwd|secret|token|api[_-]?key|credential|cookie|auth)")
SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(password|passwd|secret|token|api[_-]?key|credential|cookie|authorization)"
    r"(\s*[=:]\s*)([^\s,;]+)"
)
SECRET_ARGUMENT = re.compile(
    r"(?i)(--?(?:password|passwd|secret|token|api[_-]?key|credential|cookie|authorization)\s+)"
    r"([^\s,;]+)"
)
SELF_DESCRIPTION_ARGS = {
    "--help",
    "-h",
    "help",
    "--version",
    "version",
    "completion",
    "list",
    "status",
    "inspect",
    "--print-config",
    "--schema",
    "--dry-run",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _redact(text: str) -> str:
    text = SECRET_ASSIGNMENT.sub(
        lambda match: f"{match.group(1)}{match.group(2)}<redacted>", text
    )
    return SECRET_ARGUMENT.sub(lambda match: f"{match.group(1)}<redacted>", text)


def _redact_data(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "<redacted>" if SECRET_KEY.search(str(key)) else _redact_data(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_data(item) for item in value]
    if isinstance(value, str):
        return _redact(value)
    return value


def _bounded(text: str, limit: int = MAX_OUTPUT) -> tuple[str, bool]:
    if len(text) <= limit:
        return _redact(text), False
    return _redact(text[:limit]), True


def _command(
    argv: Sequence[str],
    *,
    timeout_s: float = 8.0,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Execute an argv-only read probe and retain bounded evidence."""
    resolved = shutil.which(argv[0])
    if resolved is None and Path(argv[0]).is_file():
        resolved = str(Path(argv[0]).resolve())
    record: dict[str, Any] = {
        "argv": [str(item) for item in argv],
        "executable": resolved,
        "cwd": str(Path.cwd()),
        "started_at": _now(),
        "timeout_s": timeout_s,
    }
    if resolved is None:
        return {**record, "status": "UNAVAILABLE", "error": "executable not found"}
    started = time.monotonic()
    try:
        completed = subprocess.run(
            [resolved, *argv[1:]],
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        timeout_stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        timeout_stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
        stdout, stdout_truncated = _bounded(timeout_stdout)
        stderr, stderr_truncated = _bounded(timeout_stderr, 20_000)
        return {
            **record,
            "status": "TIMEOUT",
            "duration_ms": round((time.monotonic() - started) * 1000, 3),
            "stdout": stdout,
            "stderr": stderr,
            "output_truncated": stdout_truncated or stderr_truncated,
        }
    except OSError as exc:
        return {
            **record,
            "status": "PROBE_FAILED",
            "duration_ms": round((time.monotonic() - started) * 1000, 3),
            "error": str(exc),
        }
    stdout, stdout_truncated = _bounded(completed.stdout)
    stderr, stderr_truncated = _bounded(completed.stderr, 20_000)
    return {
        **record,
        "status": "SUCCEEDED" if completed.returncode == 0 else "PROBE_FAILED",
        "duration_ms": round((time.monotonic() - started) * 1000, 3),
        "returncode": completed.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "output_truncated": stdout_truncated or stderr_truncated,
    }


def _result(
    operation: str,
    data: dict[str, Any],
    *,
    evidence: Sequence[dict[str, Any]] = (),
    warnings: Sequence[str] = (),
    status: str | None = None,
) -> dict[str, Any]:
    evidence_list = list(evidence)
    if status is None:
        statuses = {item.get("status") for item in evidence_list}
        status = (
            "UNAVAILABLE"
            if evidence_list and statuses == {"UNAVAILABLE"}
            else "PARTIAL"
            if any(item in {"UNAVAILABLE", "TIMEOUT", "PROBE_FAILED"} for item in statuses)
            else "SUCCEEDED"
        )
    return {
        "schema_version": "robot-host-introspection/v1",
        "operation": operation,
        "status": status,
        "observed_at": _now(),
        "data": data,
        "evidence": evidence_list,
        "warnings": list(warnings),
    }


def host_inventory() -> dict[str, Any]:
    managers = {
        name: shutil.which(executable)
        for name, executable in {
            "systemd": "systemctl",
            "launchd": "launchctl",
            "windows_scm": "sc.exe",
            "supervisor": "supervisorctl",
        }.items()
    }
    runtimes = {
        name: shutil.which(executable)
        for name, executable in {
            "docker": "docker",
            "podman": "podman",
            "kubernetes": "kubectl",
        }.items()
    }
    schedulers = {
        name: shutil.which(executable)
        for name, executable in {
            "cron": "crontab",
            "systemd_timers": "systemctl",
            "windows_tasks": "schtasks.exe",
        }.items()
    }
    is_admin: bool | None = None
    if os.name == "posix" and hasattr(os, "geteuid"):
        is_admin = os.geteuid() == 0
    elif os.name == "nt":
        try:
            import ctypes

            is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
        except (AttributeError, OSError):
            pass
    container_markers = [
        str(path)
        for path in (Path("/.dockerenv"), Path("/run/.containerenv"))
        if path.exists()
    ]
    data = {
        "host": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "architecture": platform.machine().lower(),
            "hostname": platform.node(),
            "python": sys.version.split()[0],
        },
        "identity": {"user": getpass.getuser(), "is_administrator": is_admin},
        "control_planes": {
            "service_managers": managers,
            "container_runtimes": runtimes,
            "schedulers": schedulers,
            "container_markers": container_markers,
        },
        "path": os.environ.get("PATH", "").split(os.pathsep),
        "middleware_environment": {
            key: os.environ[key] for key in sorted(SAFE_ENV_KEYS) if key in os.environ
        },
    }
    return _result("linux.host.inventory", data)


def service_list() -> dict[str, Any]:
    warnings: list[str] = []
    if platform.system() == "Linux":
        record = _command(
            [
                "systemctl",
                "list-units",
                "--type=service",
                "--all",
                "--no-legend",
                "--no-pager",
            ]
        )
        services = []
        if record.get("status") == "SUCCEEDED":
            for line in record["stdout"].splitlines()[:MAX_ITEMS]:
                parts = line.split(None, 4)
                if len(parts) >= 4:
                    services.append(
                        {
                            "name": parts[0],
                            "load": parts[1],
                            "active": parts[2],
                            "sub": parts[3],
                            "description": parts[4] if len(parts) == 5 else "",
                        }
                    )
        return _result("linux.service.list", {"services": services}, evidence=[record])
    if platform.system() == "Windows":
        record = _command(["sc.exe", "query", "state=", "all"], timeout_s=10)
        services = []
        current: dict[str, str] = {}
        for line in record.get("stdout", "").splitlines():
            if line.startswith("SERVICE_NAME:"):
                if current:
                    services.append(current)
                current = {"name": line.split(":", 1)[1].strip()}
            elif "STATE" in line and ":" in line:
                current["state"] = line.split(":", 1)[1].strip()
            if len(services) >= MAX_ITEMS:
                break
        if current and len(services) < MAX_ITEMS:
            services.append(current)
        return _result("linux.service.list", {"services": services}, evidence=[record])
    warnings.append("No service-list adapter is available for this platform")
    return _result("linux.service.list", {"services": []}, warnings=warnings, status="UNAVAILABLE")


def _validate_name(value: str, label: str) -> str:
    if not value or value.startswith("-") or any(character in value for character in "\r\n\0"):
        raise ValueError(f"invalid {label}")
    return value


def service_inspect(name: str) -> dict[str, Any]:
    name = _validate_name(name, "service name")
    if platform.system() == "Linux":
        show = _command(
            [
                "systemctl",
                "show",
                name,
                "--no-pager",
                "--property=Id,Description,LoadState,ActiveState,SubState,MainPID,ExecStart,"
                "WorkingDirectory,EnvironmentFiles,FragmentPath,DropInPaths,Restart,After,Requires,"
                "StandardOutput,StandardError,SyslogIdentifier",
            ]
        )
        definition = _command(["systemctl", "cat", name, "--no-pager"])
        properties = {}
        for line in show.get("stdout", "").splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                properties[key] = _redact(value)
        return _result(
            "linux.service.inspect",
            {"name": name, "properties": properties, "definition": definition.get("stdout", "")},
            evidence=[show, definition],
        )
    if platform.system() == "Windows":
        query = _command(["sc.exe", "queryex", name])
        config = _command(["sc.exe", "qc", name])
        return _result(
            "linux.service.inspect",
            {"name": name, "query": query.get("stdout", ""), "config": config.get("stdout", "")},
            evidence=[query, config],
        )
    return _result(
        "linux.service.inspect",
        {"name": name},
        warnings=["No service-inspection adapter is available for this platform"],
        status="UNAVAILABLE",
    )


def _container_runtime(requested: str | None = None) -> str | None:
    if requested is not None:
        if requested not in {"docker", "podman"}:
            raise ValueError("runtime must be docker or podman")
        return requested if shutil.which(requested) else None
    return next((runtime for runtime in ("docker", "podman") if shutil.which(runtime)), None)


def container_list(runtime: str | None = None) -> dict[str, Any]:
    selected = _container_runtime(runtime)
    if selected is None:
        return _result(
            "linux.container.list",
            {"runtime": runtime, "containers": []},
            warnings=["Neither Docker nor Podman is available"],
            status="UNAVAILABLE",
        )
    record = _command([selected, "ps", "--all", "--format", "{{json .}}"], timeout_s=10)
    containers = []
    for line in record.get("stdout", "").splitlines()[:MAX_ITEMS]:
        try:
            containers.append(json.loads(line))
        except json.JSONDecodeError:
            containers.append({"raw": line})
    return _result(
        "linux.container.list",
        {"runtime": selected, "containers": containers},
        evidence=[record],
    )


def container_inspect(name: str, runtime: str | None = None) -> dict[str, Any]:
    name = _validate_name(name, "container name")
    selected = _container_runtime(runtime)
    if selected is None:
        return _result(
            "linux.container.inspect",
            {"runtime": runtime, "name": name},
            warnings=["Neither Docker nor Podman is available"],
            status="UNAVAILABLE",
        )
    record = _command([selected, "inspect", name], timeout_s=10)
    try:
        details = _redact_data(json.loads(record.get("stdout", "[]") or "[]"))
    except json.JSONDecodeError:
        details = []
    return _result(
        "linux.container.inspect",
        {"runtime": selected, "name": name, "details": details},
        evidence=[record],
    )


def schedule_list() -> dict[str, Any]:
    if platform.system() == "Linux":
        timers = _command(
            ["systemctl", "list-timers", "--all", "--no-legend", "--no-pager"]
        )
        crontab = _command(["crontab", "-l"])
        return _result(
            "linux.schedule.list",
            {
                "systemd_timers": timers.get("stdout", "").splitlines()[:MAX_ITEMS],
                "user_crontab": crontab.get("stdout", "").splitlines()[:MAX_ITEMS],
            },
            evidence=[timers, crontab],
        )
    if platform.system() == "Windows":
        record = _command(["schtasks.exe", "/Query", "/FO", "CSV", "/V"], timeout_s=10)
        rows = list(csv.DictReader(record.get("stdout", "").splitlines()))[:MAX_ITEMS]
        return _result("linux.schedule.list", {"tasks": rows}, evidence=[record])
    return _result(
        "linux.schedule.list",
        {"tasks": []},
        warnings=["No scheduled-task adapter is available for this platform"],
        status="UNAVAILABLE",
    )


def schedule_inspect(name: str) -> dict[str, Any]:
    name = _validate_name(name, "scheduled task name")
    if platform.system() == "Linux":
        record = _command(["systemctl", "show", name, "--no-pager"])
        properties = {}
        for line in record.get("stdout", "").splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                properties[key] = _redact(value)
        return _result(
            "linux.schedule.inspect",
            {"name": name, "properties": properties},
            evidence=[record],
        )
    if platform.system() == "Windows":
        record = _command(["schtasks.exe", "/Query", "/TN", name, "/XML"], timeout_s=10)
        return _result(
            "linux.schedule.inspect",
            {"name": name, "definition": record.get("stdout", "")},
            evidence=[record],
        )
    return _result(
        "linux.schedule.inspect",
        {"name": name},
        warnings=["No scheduled-task adapter is available for this platform"],
        status="UNAVAILABLE",
    )


def process_list() -> dict[str, Any]:
    if platform.system() == "Linux":
        record = _command(["ps", "-eo", "pid=,ppid=,user=,stat=,etimes=,comm=,args="])
        processes = []
        for line in record.get("stdout", "").splitlines()[:MAX_ITEMS]:
            parts = line.strip().split(None, 6)
            if len(parts) >= 6:
                processes.append(
                    {
                        "pid": int(parts[0]),
                        "ppid": int(parts[1]),
                        "user": parts[2],
                        "state": parts[3],
                        "elapsed_s": int(parts[4]),
                        "command": parts[5],
                        "argv": _redact(parts[6]) if len(parts) == 7 else parts[5],
                    }
                )
        return _result("linux.process.list", {"processes": processes}, evidence=[record])
    if platform.system() == "Windows":
        record = _command(["tasklist.exe", "/FO", "CSV", "/NH"])
        processes = []
        for row in list(csv.reader(record.get("stdout", "").splitlines()))[:MAX_ITEMS]:
            if len(row) >= 2 and row[1].isdigit():
                processes.append({"name": row[0], "pid": int(row[1])})
        return _result("linux.process.list", {"processes": processes}, evidence=[record])
    return _result(
        "linux.process.list",
        {"processes": []},
        warnings=["No process-list adapter is available for this platform"],
        status="UNAVAILABLE",
    )


def _read_proc_text(path: Path, limit: int = MAX_OUTPUT) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return None


def process_inspect(pid: int) -> dict[str, Any]:
    if pid <= 0:
        raise ValueError("pid must be positive")
    if platform.system() == "Linux":
        root = Path("/proc") / str(pid)
        if not root.is_dir():
            return _result(
                "linux.process.inspect",
                {"pid": pid},
                warnings=["process does not exist or is not readable"],
                status="UNAVAILABLE",
            )
        cmdline = (_read_proc_text(root / "cmdline") or "").replace("\0", " ").strip()
        environ_text = _read_proc_text(root / "environ") or ""
        environment = {}
        environment_keys = []
        for item in environ_text.split("\0"):
            if "=" not in item:
                continue
            key, value = item.split("=", 1)
            environment_keys.append(key)
            if key in SAFE_ENV_KEYS:
                environment[key] = value
            elif SECRET_KEY.search(key):
                environment[key] = "<redacted>"
        links = {}
        for name in ("exe", "cwd", "root"):
            try:
                links[name] = str((root / name).readlink())
            except OSError:
                links[name] = None
        maps = _read_proc_text(root / "maps") or ""
        mapped_files = sorted(
            {line.rsplit(None, 1)[-1] for line in maps.splitlines() if "/" in line}
        )[:MAX_ITEMS]
        children = _read_proc_text(root / "task" / str(pid) / "children", 20_000)
        return _result(
            "linux.process.inspect",
            {
                "pid": pid,
                "argv": _redact(cmdline),
                "status": _read_proc_text(root / "status", 50_000),
                "links": links,
                "environment_keys": sorted(environment_keys)[:MAX_ITEMS],
                "safe_environment": environment,
                "children": [int(value) for value in (children or "").split() if value.isdigit()],
                "mapped_files": mapped_files,
            },
        )
    if platform.system() == "Windows":
        script = (
            f"Get-CimInstance Win32_Process -Filter 'ProcessId={pid}' | "
            "Select-Object ProcessId,ParentProcessId,Name,ExecutablePath,CommandLine | "
            "ConvertTo-Json -Compress"
        )
        record = _command(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script])
        try:
            process = json.loads(record.get("stdout", "null"))
        except json.JSONDecodeError:
            process = None
        if isinstance(process, dict) and isinstance(process.get("CommandLine"), str):
            process["CommandLine"] = _redact(process["CommandLine"])
        return _result("linux.process.inspect", {"pid": pid, "process": process}, evidence=[record])
    return _result(
        "linux.process.inspect",
        {"pid": pid},
        warnings=["No process-inspection adapter is available for this platform"],
        status="UNAVAILABLE",
    )


def _sha256(path: Path) -> tuple[str | None, str | None]:
    try:
        size = path.stat().st_size
        if size > MAX_HASH_BYTES:
            return None, f"hash omitted because file exceeds {MAX_HASH_BYTES} bytes"
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest(), None
    except OSError as exc:
        return None, str(exc)


def binary_describe(path: Path) -> dict[str, Any]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        return _result(
            "linux.binary.describe",
            {"path": str(resolved)},
            warnings=["binary does not exist or is not a regular file"],
            status="UNAVAILABLE",
        )
    digest, hash_warning = _sha256(resolved)
    header = resolved.read_bytes()[:64]
    format_name = (
        "ELF"
        if header.startswith(b"\x7fELF")
        else "PE"
        if header.startswith(b"MZ")
        else "Mach-O"
        if header[:4] in {b"\xfe\xed\xfa\xce", b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe"}
        else "script"
        if header.startswith(b"#!")
        else "unknown"
    )
    evidence = [_command(["file", str(resolved)])]
    if platform.system() == "Linux" and format_name == "ELF":
        evidence.append(_command(["ldd", str(resolved)]))
        evidence.append(_command(["readelf", "-h", "-d", str(resolved)]))
        evidence.append(_command(["nm", "-D", "--defined-only", str(resolved)]))
    stat = resolved.stat()
    return _result(
        "linux.binary.describe",
        {
            "path": str(resolved),
            "size_bytes": stat.st_size,
            "mode": oct(stat.st_mode),
            "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            "sha256": digest,
            "format": format_name,
            "architecture": platform.machine().lower(),
        },
        evidence=evidence,
        warnings=[hash_warning] if hash_warning else [],
    )


def cli_probe(path: Path, args: Sequence[str]) -> dict[str, Any]:
    resolved = path.expanduser().resolve()
    probe_args = list(args) or ["--help"]
    disallowed = [argument for argument in probe_args if argument not in SELF_DESCRIPTION_ARGS]
    if disallowed:
        raise ValueError(f"unsupported self-description arguments: {', '.join(disallowed)}")
    if not resolved.is_file():
        return _result(
            "linux.cli.probe",
            {"path": str(resolved), "args": probe_args},
            warnings=["executable does not exist or is not a regular file"],
            status="UNAVAILABLE",
        )
    sanitized_env = {
        "PATH": os.environ.get("PATH", ""),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8"),
        "HOME": str(Path.home()),
    }
    for key in ("SYSTEMROOT", "WINDIR", "PATHEXT", "TEMP", "TMP"):
        if key in os.environ:
            sanitized_env[key] = os.environ[key]
    record = _command([str(resolved), *probe_args], timeout_s=5, env=sanitized_env)
    return _result(
        "linux.cli.probe",
        {"path": str(resolved), "args": probe_args, "probe_status": record["status"]},
        evidence=[record],
    )


def _config_candidates(base: Path, source: str) -> list[dict[str, str]]:
    candidates = []
    directories = [base, base / "config", base.parent / "config", Path("/etc") / base.name]
    for directory in directories:
        if not directory.is_dir():
            continue
        try:
            paths = sorted(directory.iterdir())
        except OSError:
            continue
        for path in paths:
            if path.is_file() and path.suffix.lower() in CONFIG_SUFFIXES:
                candidates.append({"path": str(path.resolve()), "source": source})
                if len(candidates) >= MAX_ITEMS:
                    return candidates
    return candidates


def config_locate(*, pid: int | None = None, binary: Path | None = None) -> dict[str, Any]:
    if pid is None and binary is None:
        raise ValueError("provide --process or --binary")
    candidates: list[dict[str, str]] = []
    warnings: list[str] = []
    resolved_binary: Path | None = binary.expanduser().resolve() if binary else None
    if pid is not None:
        process = process_inspect(pid)
        process_data = process.get("data", {})
        argv = str(process_data.get("argv") or "")
        for token in argv.split():
            candidate = Path(token.strip("'\""))
            if candidate.suffix.lower() in CONFIG_SUFFIXES:
                candidates.append({"path": str(candidate), "source": "process argv"})
        links = process_data.get("links", {})
        exe = links.get("exe") if isinstance(links, dict) else None
        cwd = links.get("cwd") if isinstance(links, dict) else None
        if exe:
            resolved_binary = Path(exe)
        if cwd:
            candidates.extend(_config_candidates(Path(cwd), "process working directory"))
        if process.get("status") == "UNAVAILABLE":
            warnings.extend(process.get("warnings", []))
    if resolved_binary is not None:
        candidates.extend(_config_candidates(resolved_binary.parent, "binary adjacency"))
    unique = {item["path"]: item for item in candidates}
    return _result(
        "linux.config.locate",
        {
            "process": pid,
            "binary": str(resolved_binary) if resolved_binary else None,
            "candidates": list(unique.values())[:MAX_ITEMS],
        },
        warnings=warnings,
    )


def network_listeners() -> dict[str, Any]:
    if platform.system() == "Linux":
        record = _command(["ss", "-H", "-lntup"])
        listeners = [
            {"raw": line}
            for line in record.get("stdout", "").splitlines()[:MAX_ITEMS]
            if line.strip()
        ]
        return _result("linux.network.listeners", {"listeners": listeners}, evidence=[record])
    if platform.system() == "Windows":
        script = (
            "$tcp=Get-NetTCPConnection -State Listen | Select-Object "
            "Protocol,LocalAddress,LocalPort,OwningProcess; "
            "$udp=Get-NetUDPEndpoint | Select-Object "
            "Protocol,LocalAddress,LocalPort,OwningProcess; "
            "@($tcp)+@($udp) | ConvertTo-Json -Compress"
        )
        record = _command(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script])
        try:
            listeners = json.loads(record.get("stdout", "[]") or "[]")
        except json.JSONDecodeError:
            listeners = []
        if isinstance(listeners, dict):
            listeners = [listeners]
        return _result("linux.network.listeners", {"listeners": listeners}, evidence=[record])
    return _result(
        "linux.network.listeners",
        {"listeners": []},
        warnings=["No listener adapter is available for this platform"],
        status="UNAVAILABLE",
    )


def middleware_inspect() -> dict[str, Any]:
    known = {
        "ros2": "ros2",
        "ros1": "rosnode",
        "cyclonedds": "ddsls",
        "fastdds": "fastdds",
        "zenoh": "zenohd",
        "mqtt": "mosquitto_sub",
        "docker": "docker",
        "kubernetes": "kubectl",
    }
    installed = {name: shutil.which(executable) for name, executable in known.items()}
    process_result = process_list()
    listener_result = network_listeners()
    tokens = ("ros", "dds", "mqtt", "mosquitto", "zenoh", "grpc", "nats", "redis", "kafka")
    candidates = []
    for process in process_result.get("data", {}).get("processes", []):
        text = " ".join(str(value) for value in process.values()).lower()
        matches = sorted({token for token in tokens if token in text})
        if matches:
            candidates.append({"process": process, "protocol_tokens": matches})
    return _result(
        "middleware.inspect",
        {
            "installed_interfaces": installed,
            "environment": {
                key: os.environ[key] for key in sorted(SAFE_ENV_KEYS) if key in os.environ
            },
            "process_candidates": candidates[:MAX_ITEMS],
            "listeners": listener_result.get("data", {}).get("listeners", [])[:MAX_ITEMS],
        },
        warnings=[*process_result.get("warnings", []), *listener_result.get("warnings", [])],
        status=(
            "PARTIAL"
            if process_result.get("status") != "SUCCEEDED"
            or listener_result.get("status") != "SUCCEEDED"
            else "SUCCEEDED"
        ),
    )


def ros_node_status(name: str) -> dict[str, Any]:
    name = _validate_name(name, "ROS node name")
    if shutil.which("ros2"):
        record = _command(["ros2", "node", "info", name], timeout_s=10)
        return _result(
            "ros.node.status",
            {"name": name, "ros_version": 2, "details": record.get("stdout", "")},
            evidence=[record],
        )
    if shutil.which("rosnode"):
        record = _command(["rosnode", "info", name], timeout_s=10)
        return _result(
            "ros.node.status",
            {"name": name, "ros_version": 1, "details": record.get("stdout", "")},
            evidence=[record],
        )
    return _result(
        "ros.node.status",
        {"name": name},
        warnings=["Neither ROS 2 nor ROS 1 CLI is available"],
        status="UNAVAILABLE",
    )
