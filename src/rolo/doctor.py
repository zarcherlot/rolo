from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from rolo import __version__
from rolo.core.config import Settings, get_settings
from rolo.invocation_policy import validate_protected_file
from rolo.runtime import create_runtime
from rolo.stages.adapt.dependencies import CodexDependencyAdapter
from rolo.stages.adapt.service import coding_agent_config
from rolo.stages.diagnose.robot_use import create_robot_use_backend


def _probe_adapter_sandbox(launcher: Path) -> None:
    if sys.platform == "win32":
        return
    try:
        completed = subprocess.run(
            [str(launcher), "--self-test"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"sandbox self-test could not complete: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip()[:1000] or f"exit {completed.returncode}"
        raise ValueError(f"sandbox self-test failed: {detail}")


def build_doctor_report(
    settings: Settings | None = None,
    *,
    require_adapter_sandbox: bool = False,
) -> dict[str, object]:
    """Assess local runtime prerequisites without mutating the target software stack."""
    settings = settings or get_settings()
    errors: list[str] = []
    warnings: list[str] = []
    robot_manifests = (
        sorted(settings.robot_config_dir.glob("*.yaml"))
        if settings.robot_config_dir.is_dir()
        else []
    )
    robots = 0
    enrollment_status = "NOT_ENROLLED"
    if robot_manifests:
        try:
            runtime = create_runtime(settings)
            robots = len(runtime.registry)
            enrolled = runtime.registry.list()
            states = {
                str(robot.features.get("enrollment", {}).get("urdf_status", "REGISTERED"))
                for robot in enrolled
            }
            enrollment_status = states.pop() if len(states) == 1 else "REGISTERED"
        except Exception as exc:  # doctor must aggregate malformed robot configuration
            errors.append(str(exc))
            enrollment_status = "INVALID"
    else:
        warnings.append("No robot is registered; run 'uv run robotctl init --robot-id ...'")

    try:
        backend = create_robot_use_backend(settings).name
    except Exception as exc:  # doctor must aggregate malformed backend configuration
        errors.append(str(exc))
        backend = settings.robot_use_backend

    install_home = settings.coding_agent_install_home or Path.home()
    codex_executable = CodexDependencyAdapter().resolve(
        settings.coding_agent_executable, install_home
    )
    optional_tools = {
        "git": shutil.which("git"),
        "codex": str(codex_executable) if codex_executable else None,
        "docker": shutil.which("docker"),
        "ros2": shutil.which("ros2"),
        "ffmpeg": shutil.which("ffmpeg"),
    }
    for name in ("docker", "ros2", "ffmpeg"):
        if not optional_tools[name]:
            warnings.append(f"{name} is optional for mock mode and is not installed")
    if not optional_tools["codex"]:
        warnings.append("codex is not installed; adapt run will attempt installation")

    sandbox_launcher = settings.rolo_adapter_sandbox_launcher
    if settings.rolo_adapter_unsandboxed_dev:
        adapter_sandbox = "UNSANDBOXED_DEVELOPMENT"
        warnings.append(
            "ROLO_ADAPTER_UNSANDBOXED_DEV is enabled; generated adapters are not OS-isolated"
        )
    elif sandbox_launcher is None:
        adapter_sandbox = "NOT_CONFIGURED"
        message = (
            "ROLO_ADAPTER_SANDBOX_LAUNCHER is not configured; generated adapter execution "
            "will fail closed"
        )
        (errors if require_adapter_sandbox else warnings).append(message)
    else:
        try:
            protected_launcher = validate_protected_file(
                sandbox_launcher,
                label="adapter sandbox launcher",
            )
            if sys.platform != "win32" and not protected_launcher.stat().st_mode & 0o111:
                raise ValueError("adapter sandbox launcher must be executable")
            _probe_adapter_sandbox(protected_launcher)
        except (OSError, ValueError) as exc:
            adapter_sandbox = "INVALID"
            message = f"adapter sandbox launcher is invalid: {exc}"
            (errors if require_adapter_sandbox else warnings).append(message)
        else:
            adapter_sandbox = "CONFIGURED"

    if backend == "openai":
        if not settings.openai_api_key:
            errors.append("OPENAI_API_KEY is required when ROBOT_USE_BACKEND=openai")
        if not settings.openai_model:
            errors.append("OPENAI_MODEL is required when ROBOT_USE_BACKEND=openai")
    elif not settings.openai_api_key:
        warnings.append("OPENAI_API_KEY is not set; robot_use will remain on the mock backend")

    return {
        "status": "READY" if not errors else "NOT_READY",
        "version": __version__,
        "python": {"version": sys.version.split()[0], "executable": sys.executable},
        "config_dir": str(settings.rolo_config_dir),
        "artifact_dir": str(settings.rolo_artifact_dir),
        "robots": robots,
        "enrollment_status": enrollment_status,
        "robot_use_backend": backend,
        "coding_agent": coding_agent_config(settings).model_dump(mode="json"),
        "adapter_sandbox": {
            "status": adapter_sandbox,
            "launcher": str(sandbox_launcher) if sandbox_launcher is not None else None,
            "required": require_adapter_sandbox,
        },
        "local_visual_detection": False,
        "optional_tools": optional_tools,
        "warnings": warnings,
        "errors": errors,
    }
