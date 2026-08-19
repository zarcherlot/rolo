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
import socket
import stat
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
    text = SECRET_ASSIGNMENT.sub(lambda match: f"{match.group(1)}{match.group(2)}<redacted>", text)
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
        str(path) for path in (Path("/.dockerenv"), Path("/run/.containerenv")) if path.exists()
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


def _uptime_seconds() -> tuple[float | None, str | None]:
    system = platform.system()
    if system == "Linux":
        try:
            return float(Path("/proc/uptime").read_text(encoding="utf-8").split()[0]), None
        except (OSError, ValueError, IndexError) as exc:
            return None, str(exc)
    if system == "Windows":
        try:
            import ctypes

            return round(ctypes.windll.kernel32.GetTickCount64() / 1000, 3), None
        except (AttributeError, OSError) as exc:
            return None, str(exc)
    return None, f"host uptime is not implemented for {system or 'this platform'}"


def host_uptime() -> dict[str, Any]:
    uptime_s, warning = _uptime_seconds()
    return _result(
        "linux.host.uptime",
        {"uptime_s": uptime_s},
        warnings=[warning] if warning else [],
        status="SUCCEEDED" if uptime_s is not None else "UNAVAILABLE",
    )


def host_status() -> dict[str, Any]:
    uptime_s, warning = _uptime_seconds()
    return _result(
        "linux.host.status",
        {
            "system": platform.system(),
            "release": platform.release(),
            "architecture": platform.machine().lower(),
            "hostname": platform.node(),
            "uptime_s": uptime_s,
        },
        warnings=[warning] if warning else [],
        status="SUCCEEDED" if uptime_s is not None else "PARTIAL",
    )


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


def container_stats(
    name: str | None = None, runtime: str | None = None
) -> dict[str, Any]:
    if name is not None:
        name = _validate_name(name, "container name")
    selected = _container_runtime(runtime)
    if selected is None:
        return _result(
            "linux.container.stats",
            {"runtime": runtime, "name": name, "containers": []},
            warnings=["Neither Docker nor Podman is available"],
            status="UNAVAILABLE",
        )
    argv = [selected, "stats", "--no-stream", "--format", "{{json .}}"]
    if name is not None:
        argv.append(name)
    record = _command(argv, timeout_s=10)
    containers = []
    for line in record.get("stdout", "").splitlines()[:MAX_ITEMS]:
        try:
            containers.append(_redact_data(json.loads(line)))
        except json.JSONDecodeError:
            containers.append({"raw": _redact(line)})
    return _result(
        "linux.container.stats",
        {"runtime": selected, "name": name, "containers": containers},
        evidence=[record],
    )


def schedule_list() -> dict[str, Any]:
    if platform.system() == "Linux":
        timers = _command(["systemctl", "list-timers", "--all", "--no-legend", "--no-pager"])
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


def _proc_key_values(text: str, *, byte_values: bool = False) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, raw = line.split(":", 1)
        raw = raw.strip()
        if byte_values and raw.endswith(" kB"):
            number = raw.removesuffix(" kB").strip()
            values[f"{key}_bytes"] = int(number) * 1024 if number.isdigit() else raw
        else:
            values[key] = int(raw) if raw.isdigit() else raw
    return values


def process_resources(pid: int) -> dict[str, Any]:
    if pid <= 0:
        raise ValueError("pid must be positive")
    if platform.system() == "Linux":
        root = Path("/proc") / str(pid)
        status_text = _read_proc_text(root / "status", 50_000)
        if status_text is None:
            return _result(
                "linux.process.resources",
                {"pid": pid},
                warnings=["process does not exist or resource data is not readable"],
                status="UNAVAILABLE",
            )
        io_text = _read_proc_text(root / "io", 20_000)
        return _result(
            "linux.process.resources",
            {
                "pid": pid,
                "status": _proc_key_values(status_text, byte_values=True),
                "io": _proc_key_values(io_text or ""),
            },
        )
    if platform.system() == "Windows":
        script = (
            f"Get-Process -Id {pid} -ErrorAction SilentlyContinue | Select-Object "
            "Id,ProcessName,CPU,WorkingSet64,PrivateMemorySize64,VirtualMemorySize64,"
            "PagedMemorySize64,HandleCount,ThreadCount,StartTime | ConvertTo-Json -Compress"
        )
        record = _command(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script])
        try:
            resources = json.loads(record.get("stdout", "null") or "null")
        except json.JSONDecodeError:
            resources = None
        return _result(
            "linux.process.resources",
            {"pid": pid, "resources": resources},
            evidence=[record],
        )
    return _result(
        "linux.process.resources",
        {"pid": pid},
        warnings=["No process-resource adapter is available for this platform"],
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


def file_hash(path: Path) -> dict[str, Any]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        return _result(
            "linux.file.hash",
            {"path": str(resolved), "algorithm": "sha256", "sha256": None},
            warnings=["path does not exist or is not a regular file"],
            status="UNAVAILABLE",
        )
    digest, warning = _sha256(resolved)
    return _result(
        "linux.file.hash",
        {
            "path": str(resolved),
            "size_bytes": resolved.stat().st_size,
            "algorithm": "sha256",
            "sha256": digest,
        },
        warnings=[warning] if warning else [],
        status="SUCCEEDED" if digest else "PARTIAL",
    )


def binary_verify(path: Path, expected_sha256: str) -> dict[str, Any]:
    expected = expected_sha256.strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError("expected SHA-256 must contain exactly 64 hexadecimal characters")
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        return _result(
            "linux.binary.verify",
            {
                "path": str(resolved),
                "algorithm": "sha256",
                "expected_sha256": expected,
                "observed_sha256": None,
                "verified": False,
            },
            warnings=["binary does not exist or is not a regular file"],
            status="UNAVAILABLE",
        )
    observed, warning = _sha256(resolved)
    return _result(
        "linux.binary.verify",
        {
            "path": str(resolved),
            "algorithm": "sha256",
            "expected_sha256": expected,
            "observed_sha256": observed,
            "verified": observed == expected,
        },
        warnings=[warning] if warning else [],
        status="SUCCEEDED" if observed is not None else "PARTIAL",
    )


def file_inspect(path: Path) -> dict[str, Any]:
    expanded = path.expanduser().absolute()
    try:
        metadata = expanded.lstat()
    except OSError as exc:
        return _result(
            "linux.file.inspect",
            {"path": str(expanded)},
            warnings=[str(exc)],
            status="UNAVAILABLE",
        )
    kind = (
        "symlink"
        if stat.S_ISLNK(metadata.st_mode)
        else "directory"
        if stat.S_ISDIR(metadata.st_mode)
        else "file"
        if stat.S_ISREG(metadata.st_mode)
        else "other"
    )
    target = None
    if kind == "symlink":
        try:
            target = str(expanded.readlink())
        except OSError:
            pass
    return _result(
        "linux.file.inspect",
        {
            "path": str(expanded),
            "kind": kind,
            "size_bytes": metadata.st_size,
            "mode": oct(stat.S_IMODE(metadata.st_mode)),
            "modified_at": datetime.fromtimestamp(metadata.st_mtime, timezone.utc).isoformat(),
            "created_at": datetime.fromtimestamp(metadata.st_ctime, timezone.utc).isoformat(),
            "symlink_target": target,
        },
    )


def file_list(path: Path, limit: int = 100) -> dict[str, Any]:
    if limit < 1 or limit > MAX_ITEMS:
        raise ValueError(f"limit must be between 1 and {MAX_ITEMS}")
    resolved = path.expanduser().resolve()
    if not resolved.is_dir():
        return _result(
            "linux.file.list",
            {"path": str(resolved), "entries": []},
            warnings=["path does not exist or is not a directory"],
            status="UNAVAILABLE",
        )
    entries = []
    warnings = []
    try:
        children = sorted(resolved.iterdir(), key=lambda item: item.name)[:limit]
    except OSError as exc:
        children = []
        warnings.append(str(exc))
    for child in children:
        try:
            metadata = child.lstat()
            entries.append(
                {
                    "name": child.name,
                    "kind": (
                        "symlink"
                        if stat.S_ISLNK(metadata.st_mode)
                        else "directory"
                        if stat.S_ISDIR(metadata.st_mode)
                        else "file"
                        if stat.S_ISREG(metadata.st_mode)
                        else "other"
                    ),
                    "size_bytes": metadata.st_size,
                    "modified_at": datetime.fromtimestamp(
                        metadata.st_mtime, timezone.utc
                    ).isoformat(),
                }
            )
        except OSError as exc:
            warnings.append(f"{child.name}: {exc}")
    return _result(
        "linux.file.list",
        {"path": str(resolved), "limit": limit, "entries": entries},
        warnings=warnings,
        status="PARTIAL" if warnings else "SUCCEEDED",
    )


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


def package_inspect(name: str) -> dict[str, Any]:
    name = _validate_name(name, "package name")
    system = platform.system()
    record: dict[str, Any] | None = None
    manager: str | None = None
    if system == "Linux" and shutil.which("dpkg-query"):
        manager = "dpkg"
        record = _command(
            [
                "dpkg-query",
                "-W",
                "-f=${binary:Package}\t${Version}\t${Architecture}\t${Status}\n",
                name,
            ]
        )
    elif system == "Linux" and shutil.which("rpm"):
        manager = "rpm"
        record = _command(
            ["rpm", "-q", "--qf", "%{NAME}\t%{VERSION}-%{RELEASE}\t%{ARCH}\n", name]
        )
    elif system == "Linux" and shutil.which("pacman"):
        manager = "pacman"
        record = _command(["pacman", "-Qi", name])
    elif system == "Darwin" and shutil.which("brew"):
        manager = "brew"
        record = _command(["brew", "info", "--json=v2", name])
    elif system == "Windows":
        manager = "powershell"
        escaped = name.replace("'", "''")
        script = (
            f"Get-Package -Name '{escaped}' -ErrorAction SilentlyContinue | "
            "Select-Object Name,Version,ProviderName,Source | ConvertTo-Json -Compress"
        )
        record = _command(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script])
    if record is None:
        return _result(
            "linux.package.inspect",
            {"name": name, "manager": manager, "package": None},
            warnings=["No supported package metadata provider is available"],
            status="UNAVAILABLE",
        )
    raw = record.get("stdout", "").strip()
    package: Any = raw
    if manager in {"brew", "powershell"}:
        try:
            package = json.loads(raw or "null")
        except json.JSONDecodeError:
            package = raw
    return _result(
        "linux.package.inspect",
        {"name": name, "manager": manager, "package": package},
        evidence=[record],
    )


def package_verify(name: str) -> dict[str, Any]:
    name = _validate_name(name, "package name")
    manager: str | None = None
    record: dict[str, Any] | None = None
    if platform.system() == "Linux" and shutil.which("dpkg"):
        manager = "dpkg"
        record = _command(["dpkg", "--verify", name], timeout_s=15)
    elif platform.system() == "Linux" and shutil.which("rpm"):
        manager = "rpm"
        record = _command(["rpm", "-V", name], timeout_s=15)
    if record is None:
        return _result(
            "linux.package.verify",
            {"name": name, "manager": manager, "verified": None, "findings": []},
            warnings=["No supported package integrity provider is available"],
            status="UNAVAILABLE",
        )
    findings = [
        line for line in record.get("stdout", "").splitlines()[:MAX_ITEMS] if line.strip()
    ]
    verified = record.get("returncode") == 0 and not findings
    return _result(
        "linux.package.verify",
        {"name": name, "manager": manager, "verified": verified, "findings": findings},
        evidence=[record],
        status="SUCCEEDED",
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


def network_interfaces() -> dict[str, Any]:
    system = platform.system()
    if system == "Linux":
        record = _command(["ip", "-json", "address", "show"])
        try:
            interfaces = json.loads(record.get("stdout", "[]") or "[]")
        except json.JSONDecodeError:
            interfaces = []
        if not isinstance(interfaces, list):
            interfaces = []
        return _result(
            "linux.network.interfaces",
            {"interfaces": interfaces[:MAX_ITEMS]},
            evidence=[record],
        )
    if system == "Windows":
        script = (
            "Get-NetIPConfiguration | Select-Object InterfaceAlias,InterfaceIndex,"
            "InterfaceDescription,NetProfile,IPv4Address,IPv6Address,IPv4DefaultGateway,"
            "DNSServer | ConvertTo-Json -Depth 5 -Compress"
        )
        record = _command(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script])
        try:
            interfaces = json.loads(record.get("stdout", "[]") or "[]")
        except json.JSONDecodeError:
            interfaces = []
        if isinstance(interfaces, dict):
            interfaces = [interfaces]
        elif not isinstance(interfaces, list):
            interfaces = []
        return _result(
            "linux.network.interfaces",
            {"interfaces": interfaces[:MAX_ITEMS]},
            evidence=[record],
        )
    try:
        interfaces = [
            {"index": index, "name": name} for index, name in socket.if_nameindex()
        ][:MAX_ITEMS]
    except OSError as exc:
        return _result(
            "linux.network.interfaces",
            {"interfaces": []},
            warnings=[str(exc)],
            status="UNAVAILABLE",
        )
    return _result("linux.network.interfaces", {"interfaces": interfaces})


def network_statistics() -> dict[str, Any]:
    system = platform.system()
    if system == "Linux":
        record = _command(["ip", "-statistics", "-json", "link", "show"])
        try:
            interfaces = json.loads(record.get("stdout", "[]") or "[]")
        except json.JSONDecodeError:
            interfaces = []
        if not isinstance(interfaces, list):
            interfaces = []
        return _result(
            "linux.network.statistics",
            {"interfaces": interfaces[:MAX_ITEMS]},
            evidence=[record],
        )
    if system == "Windows":
        script = (
            "Get-NetAdapterStatistics | Select-Object Name,InterfaceDescription,"
            "ReceivedBytes,ReceivedUnicastPackets,ReceivedDiscardedPackets,ReceivedPacketErrors,"
            "SentBytes,SentUnicastPackets,OutboundDiscardedPackets,OutboundPacketErrors | "
            "ConvertTo-Json -Compress"
        )
        record = _command(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script])
        try:
            interfaces = json.loads(record.get("stdout", "[]") or "[]")
        except json.JSONDecodeError:
            interfaces = []
        if isinstance(interfaces, dict):
            interfaces = [interfaces]
        elif not isinstance(interfaces, list):
            interfaces = []
        return _result(
            "linux.network.statistics",
            {"interfaces": interfaces[:MAX_ITEMS]},
            evidence=[record],
        )
    return _result(
        "linux.network.statistics",
        {"interfaces": []},
        warnings=["No network-statistics adapter is available for this platform"],
        status="UNAVAILABLE",
    )


def network_connections() -> dict[str, Any]:
    system = platform.system()
    if system == "Linux":
        record = _command(["ss", "-H", "-ntup"])
        connections = [
            {"raw": line}
            for line in record.get("stdout", "").splitlines()[:MAX_ITEMS]
            if line.strip()
        ]
        return _result(
            "linux.network.connections",
            {"connections": connections},
            evidence=[record],
        )
    if system == "Windows":
        script = (
            "$tcp=Get-NetTCPConnection | Select-Object State,LocalAddress,LocalPort,"
            "RemoteAddress,RemotePort,OwningProcess; $udp=Get-NetUDPEndpoint | Select-Object "
            "LocalAddress,LocalPort,OwningProcess; @($tcp)+@($udp) | ConvertTo-Json -Compress"
        )
        record = _command(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script])
        try:
            connections = json.loads(record.get("stdout", "[]") or "[]")
        except json.JSONDecodeError:
            connections = []
        if isinstance(connections, dict):
            connections = [connections]
        elif not isinstance(connections, list):
            connections = []
        return _result(
            "linux.network.connections",
            {"connections": connections[:MAX_ITEMS]},
            evidence=[record],
        )
    return _result(
        "linux.network.connections",
        {"connections": []},
        warnings=["No connection metadata adapter is available for this platform"],
        status="UNAVAILABLE",
    )


def network_dns() -> dict[str, Any]:
    system = platform.system()
    if system == "Linux":
        path = Path("/etc/resolv.conf")
        text = _read_proc_text(path, 50_000)
        if text is None:
            return _result(
                "linux.network.dns",
                {"source": str(path), "nameservers": [], "search": [], "options": []},
                warnings=["resolver configuration is not readable"],
                status="UNAVAILABLE",
            )
        values: dict[str, list[str]] = {
            "nameserver": [],
            "search": [],
            "options": [],
        }
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith(("#", ";")):
                continue
            key, *items = line.split()
            if key in values:
                values[key].extend(_redact(item) for item in items)
        return _result(
            "linux.network.dns",
            {
                "source": str(path),
                "nameservers": values["nameserver"][:MAX_ITEMS],
                "search": values["search"][:MAX_ITEMS],
                "options": values["options"][:MAX_ITEMS],
            },
        )
    if system == "Windows":
        script = (
            "Get-DnsClientServerAddress | Select-Object InterfaceAlias,InterfaceIndex,"
            "AddressFamily,ServerAddresses | ConvertTo-Json -Compress"
        )
        record = _command(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script])
        try:
            resolvers = json.loads(record.get("stdout", "[]") or "[]")
        except json.JSONDecodeError:
            resolvers = []
        if isinstance(resolvers, dict):
            resolvers = [resolvers]
        elif not isinstance(resolvers, list):
            resolvers = []
        return _result(
            "linux.network.dns",
            {"source": "Get-DnsClientServerAddress", "resolvers": resolvers[:MAX_ITEMS]},
            evidence=[record],
        )
    if system == "Darwin":
        record = _command(["scutil", "--dns"])
        return _result(
            "linux.network.dns",
            {"source": "scutil", "details": record.get("stdout", "")},
            evidence=[record],
        )
    return _result(
        "linux.network.dns",
        {"source": None},
        warnings=["No DNS metadata adapter is available for this platform"],
        status="UNAVAILABLE",
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


def network_routes() -> dict[str, Any]:
    system = platform.system()
    if system == "Linux":
        record = _command(["ip", "-json", "route", "show", "table", "all"])
        try:
            routes = json.loads(record.get("stdout", "[]") or "[]")
        except json.JSONDecodeError:
            routes = []
        if not isinstance(routes, list):
            routes = []
        return _result("linux.network.routes", {"routes": routes[:MAX_ITEMS]}, evidence=[record])
    if system == "Windows":
        script = (
            "Get-NetRoute | Select-Object DestinationPrefix,NextHop,InterfaceAlias,"
            "RouteMetric,AddressFamily | ConvertTo-Json -Compress"
        )
        record = _command(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script])
        try:
            routes = json.loads(record.get("stdout", "[]") or "[]")
        except json.JSONDecodeError:
            routes = []
        if isinstance(routes, dict):
            routes = [routes]
        elif not isinstance(routes, list):
            routes = []
        return _result("linux.network.routes", {"routes": routes[:MAX_ITEMS]}, evidence=[record])
    return _result(
        "linux.network.routes",
        {"routes": []},
        warnings=["No route adapter is available for this platform"],
        status="UNAVAILABLE",
    )


def resource_cpu() -> dict[str, Any]:
    load_average: list[float] | None = None
    if hasattr(os, "getloadavg"):
        try:
            load_average = [round(value, 6) for value in os.getloadavg()]
        except OSError:
            pass
    return _result(
        "linux.resource.cpu",
        {
            "logical_cpu_count": os.cpu_count(),
            "architecture": platform.machine().lower(),
            "processor": platform.processor(),
            "load_average_1m_5m_15m": load_average,
        },
    )


def _memory_totals() -> tuple[int | None, int | None, str | None]:
    if platform.system() == "Linux":
        try:
            values = {}
            for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
                key, raw = line.split(":", 1)
                values[key] = int(raw.strip().split()[0]) * 1024
            return values.get("MemTotal"), values.get("MemAvailable"), None
        except (OSError, ValueError, IndexError) as exc:
            return None, None, str(exc)
    if platform.system() == "Windows":
        try:
            import ctypes

            class MemoryStatus(ctypes.Structure):
                _fields_ = [
                    ("length", ctypes.c_ulong),
                    ("memory_load", ctypes.c_ulong),
                    ("total_physical", ctypes.c_ulonglong),
                    ("available_physical", ctypes.c_ulonglong),
                    ("total_page_file", ctypes.c_ulonglong),
                    ("available_page_file", ctypes.c_ulonglong),
                    ("total_virtual", ctypes.c_ulonglong),
                    ("available_virtual", ctypes.c_ulonglong),
                    ("available_extended_virtual", ctypes.c_ulonglong),
                ]

            status = MemoryStatus()
            status.length = ctypes.sizeof(MemoryStatus)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                raise OSError("GlobalMemoryStatusEx failed")
            return status.total_physical, status.available_physical, None
        except (AttributeError, OSError) as exc:
            return None, None, str(exc)
    return None, None, "memory totals are unavailable on this platform"


def resource_memory() -> dict[str, Any]:
    total, available, warning = _memory_totals()
    return _result(
        "linux.resource.memory",
        {
            "total_bytes": total,
            "available_bytes": available,
            "used_bytes": (
                total - available if total is not None and available is not None else None
            ),
        },
        warnings=[warning] if warning else [],
        status="SUCCEEDED" if total is not None else "UNAVAILABLE",
    )


def resource_disk(path: Path | None = None) -> dict[str, Any]:
    resolved = (path or Path.cwd()).expanduser().resolve()
    try:
        usage = shutil.disk_usage(resolved)
    except OSError as exc:
        return _result(
            "linux.resource.disk",
            {"path": str(resolved)},
            warnings=[str(exc)],
            status="UNAVAILABLE",
        )
    return _result(
        "linux.resource.disk",
        {
            "path": str(resolved),
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
        },
    )


def resource_gpu() -> dict[str, Any]:
    if shutil.which("nvidia-smi"):
        fields = [
            "index",
            "name",
            "uuid",
            "driver_version",
            "memory.total",
            "memory.used",
            "temperature.gpu",
            "utilization.gpu",
            "power.draw",
        ]
        record = _command(
            [
                "nvidia-smi",
                f"--query-gpu={','.join(fields)}",
                "--format=csv,noheader,nounits",
            ]
        )
        gpus = []
        for row in list(csv.reader(record.get("stdout", "").splitlines()))[:MAX_ITEMS]:
            if len(row) == len(fields):
                gpus.append({key: value.strip() for key, value in zip(fields, row, strict=True)})
        return _result(
            "linux.resource.gpu",
            {"provider": "nvidia", "gpus": gpus},
            evidence=[record],
        )
    if platform.system() == "Windows":
        script = (
            "Get-CimInstance Win32_VideoController | Select-Object Name,AdapterCompatibility,"
            "AdapterRAM,DriverVersion,VideoProcessor,Status | ConvertTo-Json -Compress"
        )
        record = _command(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script])
        try:
            gpus = json.loads(record.get("stdout", "[]") or "[]")
        except json.JSONDecodeError:
            gpus = []
        if isinstance(gpus, dict):
            gpus = [gpus]
        elif not isinstance(gpus, list):
            gpus = []
        return _result("linux.resource.gpu", {"provider": "wmi", "gpus": gpus}, evidence=[record])
    if platform.system() == "Linux" and shutil.which("lspci"):
        record = _command(["lspci", "-Dnn"])
        gpus = [
            {"raw": line}
            for line in record.get("stdout", "").splitlines()[:MAX_ITEMS]
            if any(kind in line.lower() for kind in ("vga", "3d controller", "display controller"))
        ]
        return _result(
            "linux.resource.gpu",
            {"provider": "pci", "gpus": gpus},
            evidence=[record],
            warnings=["Only static PCI GPU metadata is available"],
            status="PARTIAL" if gpus else "UNAVAILABLE",
        )
    return _result(
        "linux.resource.gpu",
        {"provider": None, "gpus": []},
        warnings=["No supported GPU metadata provider is available"],
        status="UNAVAILABLE",
    )


def resource_snapshot(path: Path | None = None) -> dict[str, Any]:
    cpu = resource_cpu()
    memory = resource_memory()
    disk = resource_disk(path)
    statuses = {cpu["status"], memory["status"], disk["status"]}
    status = "SUCCEEDED" if statuses == {"SUCCEEDED"} else "PARTIAL"
    return _result(
        "linux.resource.snapshot",
        {"cpu": cpu["data"], "memory": memory["data"], "disk": disk["data"]},
        warnings=[*memory["warnings"], *disk["warnings"]],
        status=status,
    )


def time_status() -> dict[str, Any]:
    wall = datetime.now().astimezone()
    return _result(
        "linux.time.status",
        {
            "utc": datetime.now(timezone.utc).isoformat(),
            "local": wall.isoformat(),
            "timezone": str(wall.tzinfo),
            "utc_offset_s": int((wall.utcoffset() or timezone.utc.utcoffset(wall)).total_seconds()),
            "monotonic_ns": time.monotonic_ns(),
            "wall_clock_resolution_s": time.get_clock_info("time").resolution,
            "monotonic_resolution_s": time.get_clock_info("monotonic").resolution,
        },
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
    component_warnings = [
        *process_result.get("warnings", []),
        *listener_result.get("warnings", []),
    ]
    if process_result.get("status") != "SUCCEEDED":
        component_warnings.append(
            f"process discovery status: {process_result.get('status', 'UNKNOWN')}"
        )
    if listener_result.get("status") != "SUCCEEDED":
        component_warnings.append(
            f"listener discovery status: {listener_result.get('status', 'UNKNOWN')}"
        )
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
        warnings=component_warnings,
        status=(
            "PARTIAL"
            if process_result.get("status") != "SUCCEEDED"
            or listener_result.get("status") != "SUCCEEDED"
            else "SUCCEEDED"
        ),
    )


def middleware_status() -> dict[str, Any]:
    inspection = middleware_inspect()
    data = inspection["data"]
    installed = {
        name: path
        for name, path in data.get("installed_interfaces", {}).items()
        if path is not None
    }
    return _result(
        "middleware.status",
        {
            "installed_interfaces": installed,
            "process_candidate_count": len(data.get("process_candidates", [])),
            "listener_count": len(data.get("listeners", [])),
        },
        warnings=inspection["warnings"],
        status=inspection["status"],
    )


def middleware_graph_snapshot() -> dict[str, Any]:
    inspection = middleware_inspect()
    data = inspection["data"]
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    node_ids: set[str] = set()
    for name, path in sorted(data.get("installed_interfaces", {}).items()):
        if path:
            node_ids.add(f"interface:{name}")
            nodes.append(
                {"id": f"interface:{name}", "kind": "interface", "name": name, "path": path}
            )
    for index, candidate in enumerate(data.get("process_candidates", [])[:MAX_ITEMS]):
        process = candidate.get("process", {})
        process_id = str(process.get("pid") or process.get("ProcessId") or index)
        node_id = f"process:{process_id}"
        nodes.append({"id": node_id, "kind": "process", "process": process})
        for protocol in candidate.get("protocol_tokens", []):
            interface_id = f"interface:{protocol}"
            if interface_id not in node_ids:
                node_ids.add(interface_id)
                nodes.append({"id": interface_id, "kind": "protocol", "name": protocol})
            edges.append({"source": node_id, "target": interface_id, "relation": "mentions"})
    return _result(
        "middleware.graph.snapshot",
        {"nodes": nodes[:MAX_ITEMS], "edges": edges[:MAX_ITEMS]},
        warnings=inspection["warnings"],
        status=inspection["status"],
    )


def ros_node_status(name: str) -> dict[str, Any]:
    name = _validate_name(name, "ROS node name")
    if shutil.which("ros2"):
        record = _command(["ros2", "node", "list"], timeout_s=10)
        nodes = {line.strip() for line in record.get("stdout", "").splitlines()}
        return _result(
            "ros.node.status",
            {"name": name, "visible": name in nodes, "ros_version": 2},
            evidence=[record],
        )
    if shutil.which("rosnode"):
        record = _command(["rosnode", "list"], timeout_s=10)
        nodes = {line.strip() for line in record.get("stdout", "").splitlines()}
        return _result(
            "ros.node.status",
            {"name": name, "visible": name in nodes, "ros_version": 1},
            evidence=[record],
        )
    return _result(
        "ros.node.status",
        {"name": name, "visible": False},
        warnings=["Neither ROS 2 nor ROS 1 CLI is available"],
        status="UNAVAILABLE",
    )


def _ros_command(
    ros2_args: Sequence[str], ros1_argv: Sequence[str] | None = None
) -> tuple[int | None, dict[str, Any] | None]:
    if shutil.which("ros2"):
        return 2, _command(["ros2", *ros2_args], timeout_s=10)
    if ros1_argv and shutil.which(ros1_argv[0]):
        return 1, _command(ros1_argv, timeout_s=10)
    return None, None


def _ros_list(
    operation: str,
    key: str,
    ros2_args: Sequence[str],
    ros1_argv: Sequence[str] | None,
) -> dict[str, Any]:
    version, record = _ros_command(ros2_args, ros1_argv)
    if record is None:
        return _result(
            operation,
            {"ros_version": None, key: []},
            warnings=["Neither a compatible ROS 2 nor ROS 1 CLI is available"],
            status="UNAVAILABLE",
        )
    values = [line.strip() for line in record.get("stdout", "").splitlines() if line.strip()]
    return _result(
        operation,
        {"ros_version": version, key: values[:MAX_ITEMS]},
        evidence=[record],
        warnings=["result truncated at the item limit"] if len(values) > MAX_ITEMS else [],
    )


def _ros_describe(
    operation: str,
    name: str,
    ros2_args: Sequence[str],
    ros1_argv: Sequence[str] | None,
) -> dict[str, Any]:
    name = _validate_name(name, f"{operation} name")
    version, record = _ros_command(ros2_args, ros1_argv)
    if record is None:
        return _result(
            operation,
            {"name": name, "ros_version": None, "details": ""},
            warnings=["Neither a compatible ROS 2 nor ROS 1 CLI is available"],
            status="UNAVAILABLE",
        )
    return _result(
        operation,
        {"name": name, "ros_version": version, "details": record.get("stdout", "")},
        evidence=[record],
    )


def ros_node_list() -> dict[str, Any]:
    return _ros_list("ros.node.list", "nodes", ["node", "list"], ["rosnode", "list"])


def ros_node_inspect(name: str) -> dict[str, Any]:
    return _ros_describe(
        "ros.node.inspect",
        name,
        ["node", "info", name],
        ["rosnode", "info", name],
    )


def ros_node_lifecycle(name: str) -> dict[str, Any]:
    name = _validate_name(name, "ROS node name")
    if not shutil.which("ros2"):
        return _result(
            "ros.node.lifecycle",
            {"name": name, "ros_version": None, "state": None},
            warnings=["ROS 2 lifecycle CLI is unavailable"],
            status="UNAVAILABLE",
        )
    record = _command(["ros2", "lifecycle", "get", name], timeout_s=10)
    return _result(
        "ros.node.lifecycle",
        {"name": name, "ros_version": 2, "state": record.get("stdout", "").strip()},
        evidence=[record],
    )


def ros_topic_list() -> dict[str, Any]:
    return _ros_list(
        "ros.topic.list", "topics", ["topic", "list", "-t"], ["rostopic", "list"]
    )


def ros_topic_describe(name: str) -> dict[str, Any]:
    return _ros_describe(
        "ros.topic.describe",
        name,
        ["topic", "info", name, "--verbose"],
        ["rostopic", "info", name],
    )


def ros_service_list() -> dict[str, Any]:
    return _ros_list(
        "ros.service.list",
        "services",
        ["service", "list", "-t"],
        ["rosservice", "list"],
    )


def ros_service_describe(name: str) -> dict[str, Any]:
    return _ros_describe(
        "ros.service.describe",
        name,
        ["service", "type", name],
        ["rosservice", "info", name],
    )


def ros_action_list() -> dict[str, Any]:
    return _ros_list("ros.action.list", "actions", ["action", "list", "-t"], None)


def ros_action_describe(name: str) -> dict[str, Any]:
    return _ros_describe(
        "ros.action.describe",
        name,
        ["action", "info", name, "-t"],
        None,
    )


def ros_parameter_list() -> dict[str, Any]:
    return _ros_list(
        "ros.parameter.list",
        "parameters",
        ["param", "list"],
        ["rosparam", "list"],
    )


def ros_parameter_get(node: str, name: str) -> dict[str, Any]:
    node = _validate_name(node, "ROS parameter node")
    name = _validate_name(name, "ROS parameter name")
    if shutil.which("ros2"):
        record = _command(["ros2", "param", "get", node, name], timeout_s=10)
        return _result(
            "ros.parameter.get",
            {
                "node": node,
                "name": name,
                "ros_version": 2,
                "value": record.get("stdout", "").strip(),
            },
            evidence=[record],
        )
    if shutil.which("rosparam"):
        key = f"{node.rstrip('/')}/{name.lstrip('/')}"
        record = _command(["rosparam", "get", key], timeout_s=10)
        return _result(
            "ros.parameter.get",
            {
                "node": node,
                "name": name,
                "ros_version": 1,
                "value": record.get("stdout", "").strip(),
            },
            evidence=[record],
        )
    return _result(
        "ros.parameter.get",
        {"node": node, "name": name, "ros_version": None, "value": None},
        warnings=["Neither ROS 2 param nor ROS 1 rosparam CLI is available"],
        status="UNAVAILABLE",
    )


def ros_parameter_describe(node: str, name: str) -> dict[str, Any]:
    node = _validate_name(node, "ROS parameter node")
    name = _validate_name(name, "ROS parameter name")
    if not shutil.which("ros2"):
        return _result(
            "ros.parameter.describe",
            {"node": node, "name": name, "ros_version": None, "details": ""},
            warnings=["ROS 2 parameter description CLI is unavailable"],
            status="UNAVAILABLE",
        )
    record = _command(["ros2", "param", "describe", node, name], timeout_s=10)
    return _result(
        "ros.parameter.describe",
        {
            "node": node,
            "name": name,
            "ros_version": 2,
            "details": record.get("stdout", ""),
        },
        evidence=[record],
    )


def ros_clock_status() -> dict[str, Any]:
    version, record = _ros_command(
        ["topic", "info", "/clock", "--verbose"], ["rostopic", "info", "/clock"]
    )
    return _result(
        "ros.clock.status",
        {
            "ros_version": version,
            "clock_topic_available": bool(record and record.get("status") == "SUCCEEDED"),
            "details": record.get("stdout", "") if record else "",
            "ros_domain_id": os.environ.get("ROS_DOMAIN_ID"),
        },
        evidence=[record] if record else [],
        warnings=[] if record else ["Neither a compatible ROS 2 nor ROS 1 CLI is available"],
        status=None if record else "UNAVAILABLE",
    )


def ros_bag_inspect(path: Path) -> dict[str, Any]:
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        return _result(
            "ros.bag.inspect",
            {"path": str(resolved), "ros_version": None, "details": ""},
            warnings=["bag path does not exist"],
            status="UNAVAILABLE",
        )
    version, record = _ros_command(
        ["bag", "info", str(resolved)], ["rosbag", "info", str(resolved)]
    )
    if record is None:
        return _result(
            "ros.bag.inspect",
            {"path": str(resolved), "ros_version": None, "details": ""},
            warnings=["Neither ROS 2 bag nor ROS 1 rosbag CLI is available"],
            status="UNAVAILABLE",
        )
    return _result(
        "ros.bag.inspect",
        {
            "path": str(resolved),
            "ros_version": version,
            "details": record.get("stdout", ""),
        },
        evidence=[record],
    )
