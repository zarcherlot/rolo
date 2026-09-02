from __future__ import annotations

import os
import stat
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


def _platform_home(environment_name: str, fallback: Path, windows_leaf: str) -> Path:
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "rolo" / windows_leaf
    configured = os.environ.get(environment_name)
    return Path(configured).expanduser() / "rolo" if configured else fallback / "rolo"


def default_settings_path() -> Path:
    return Path(
        os.environ.get(
            "ROLO_SETTINGS_FILE",
            _platform_home("XDG_CONFIG_HOME", Path.home() / ".config", "config") / "config.yaml",
        )
    ).expanduser()


def _default_config_dir() -> Path:
    return _platform_home("XDG_STATE_HOME", Path.home() / ".local" / "state", "state") / "config"


def _default_artifact_dir() -> Path:
    return _platform_home("XDG_DATA_HOME", Path.home() / ".local" / "share", "data") / "artifacts"


def _default_output_dir() -> Path:
    return _platform_home("XDG_DATA_HOME", Path.home() / ".local" / "share", "data") / "output"


_YAML_SECTIONS: dict[str, dict[str, str]] = {
    "storage": {
        "config_dir": "rolo_config_dir",
        "artifact_dir": "rolo_artifact_dir",
        "output_dir": "rolo_output_dir",
        "scratch_dir": "rolo_scratch_dir",
    },
    "middleware": {
        "auto_source": "ros_auto_source",
        "setup_files": "ros_setup_files",
        "domain_id": "ros_domain_id",
        "rmw_implementation": "ros_rmw_implementation",
    },
}


def _read_yaml_settings() -> dict[str, Any]:
    path = default_settings_path()
    if not path.is_file():
        return {}
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"invalid Rolo settings file {path}: {exc}") from exc
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"Rolo settings file must contain a YAML object: {path}")
    version = raw.pop("schema_version", "rolo-config/v1")
    if version != "rolo-config/v1":
        raise ValueError(f"unsupported Rolo settings schema: {version}")
    unknown_sections = sorted(set(raw) - set(_YAML_SECTIONS))
    if unknown_sections:
        raise ValueError(f"unknown Rolo settings sections: {unknown_sections}")
    values: dict[str, Any] = {}
    for section_name, section in raw.items():
        if not isinstance(section, dict):
            raise ValueError(f"Rolo settings section must be an object: {section_name}")
        mapping = _YAML_SECTIONS[section_name]
        unknown = sorted(set(section) - set(mapping))
        if unknown:
            raise ValueError(f"unknown Rolo settings keys in {section_name}: {unknown}")
        values.update({mapping[key]: value for key, value in section.items()})
    return values


class _YamlSettingsSource(PydanticBaseSettingsSource):
    def get_field_value(
        self,
        field: FieldInfo,
        field_name: str,
    ) -> tuple[Any, str, bool]:
        value = _read_yaml_settings().get(field_name)
        return value, field_name, False

    def __call__(self) -> dict[str, Any]:
        return _read_yaml_settings()


class _MiddlewareEnvironmentSettingsSource(PydanticBaseSettingsSource):
    """Map the active Middleware provider's environment into settings."""

    def get_field_value(
        self,
        field: FieldInfo,
        field_name: str,
    ) -> tuple[Any, str, bool]:
        if field_name != "ros_rmw_implementation":
            return None, field_name, False
        value = os.environ.get("RMW_IMPLEMENTATION")
        return value, field_name, False

    def __call__(self) -> dict[str, Any]:
        value = os.environ.get("RMW_IMPLEMENTATION")
        if not value:
            return {}
        return {"ros_rmw_implementation": value}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    rolo_config_dir: Path = Field(default_factory=_default_config_dir)
    rolo_artifact_dir: Path = Field(default_factory=_default_artifact_dir)
    rolo_output_dir: Path = Field(default_factory=_default_output_dir)
    rolo_scratch_dir: Path | None = None
    ros_auto_source: bool = True
    ros_setup_files: list[Path] = Field(default_factory=list)
    ros_domain_id: str | None = None
    ros_rmw_implementation: str | None = None

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            _MiddlewareEnvironmentSettingsSource(settings_cls),
            _YamlSettingsSource(settings_cls),
            dotenv_settings,
            file_secret_settings,
        )

def settings_template() -> dict[str, Any]:
    defaults = Settings(_env_file=None)
    return {
        "schema_version": "rolo-config/v1",
        "storage": {
            "config_dir": str(defaults.rolo_config_dir),
            "artifact_dir": str(defaults.rolo_artifact_dir),
            "output_dir": str(defaults.rolo_output_dir),
            "scratch_dir": None,
        },
        "middleware": {
            "auto_source": defaults.ros_auto_source,
            "setup_files": [],
            "domain_id": None,
            "rmw_implementation": None,
        },
    }


def prepare_runtime_directories(
    settings: Settings,
    *,
    include_scratch: bool = False,
) -> list[Path]:
    prepared: list[Path] = []
    configured_paths = [
        settings.rolo_config_dir,
        settings.rolo_artifact_dir,
        settings.rolo_output_dir,
    ]
    if include_scratch and settings.rolo_scratch_dir is not None:
        configured_paths.append(settings.rolo_scratch_dir)
    for configured in configured_paths:
        expanded = configured.expanduser()
        if expanded.is_symlink():
            raise ValueError(f"Rolo runtime directory must not be a symlink: {expanded}")
        path = expanded.resolve()
        path.mkdir(parents=True, exist_ok=True)
        if not path.is_dir():
            raise ValueError(f"Rolo runtime path is not a directory: {path}")
        if os.name == "posix":
            if path.stat().st_uid != os.geteuid():
                raise ValueError(f"Rolo runtime directory is owned by another user: {path}")
            path.chmod(stat.S_IRWXU)
        prepared.append(path)
    return prepared


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream)
    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML object in {path}")
    return data


@lru_cache
def get_settings() -> Settings:
    return Settings()
