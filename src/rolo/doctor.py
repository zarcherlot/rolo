from __future__ import annotations

import shutil
import sys
from pathlib import Path

from rolo import __version__
from rolo.core.config import Settings, get_settings
from rolo.runtime import create_runtime
from rolo.stages.adapt.dependencies import CodexDependencyAdapter
from rolo.stages.adapt.service import coding_agent_config
from rolo.stages.diagnose.robot_use import create_robot_use_backend


def build_doctor_report(settings: Settings | None = None) -> dict[str, object]:
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
        "local_visual_detection": False,
        "optional_tools": optional_tools,
        "warnings": warnings,
        "errors": errors,
    }
