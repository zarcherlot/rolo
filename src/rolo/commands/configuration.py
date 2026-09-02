from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Annotated, Any

import typer
import yaml

from rolo.commands.common import emit
from rolo.core.config import (
    Settings,
    default_settings_path,
    get_settings,
    prepare_runtime_directories,
    settings_template,
)

config_app = typer.Typer(help="Inspect, initialize, and validate Rolo user configuration.")


def _effective(settings: Settings) -> dict[str, Any]:
    return {
        "schema_version": "rolo-effective-config/v1",
        "settings_file": str(default_settings_path()),
        "settings_file_exists": default_settings_path().is_file(),
        "storage": {
            "config_dir": str(settings.rolo_config_dir),
            "artifact_dir": str(settings.rolo_artifact_dir),
            "output_dir": str(settings.rolo_output_dir),
            "scratch_dir": (
                str(settings.rolo_scratch_dir) if settings.rolo_scratch_dir is not None else None
            ),
        },
        "middleware": {
            "auto_source": settings.ros_auto_source,
            "setup_files": [str(path) for path in settings.ros_setup_files],
            "domain_id": settings.ros_domain_id,
            "rmw_implementation": settings.ros_rmw_implementation,
        },
    }


@config_app.command("show")
def show() -> None:
    """Show the effective non-secret configuration and its user file location."""
    emit(_effective(get_settings()))


@config_app.command("init")
def initialize(
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Override the default user config destination"),
    ] = None,
) -> None:
    """Write an editable user config without overwriting an existing file."""
    path = (output or default_settings_path()).expanduser().resolve()
    if path.exists():
        raise typer.BadParameter(f"Rolo settings file already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(settings_template(), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    if os.name == "posix":
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    emit({"status": "CREATED", "settings_file": str(path), "overwritten": False})


@config_app.command("validate")
def validate() -> None:
    """Validate configuration and securely prepare its runtime directories."""
    try:
        settings = get_settings()
        prepared = prepare_runtime_directories(settings, include_scratch=True)
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(
        {
            "status": "VALID",
            "settings_file": str(default_settings_path()),
            "prepared_directories": [str(path) for path in prepared],
            "effective": _effective(settings),
        }
    )
