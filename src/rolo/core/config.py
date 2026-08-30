from __future__ import annotations

import os
import shutil
import stat
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

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


def _default_invocation_policy() -> Path:
    return _platform_home("XDG_CONFIG_HOME", Path.home() / ".config", "config") / (
        "invocation-policy.yaml"
    )


def _default_invocation_audit_log() -> Path:
    return _platform_home("XDG_STATE_HOME", Path.home() / ".local" / "state", "state") / (
        "invocation-audit.jsonl"
    )


def _default_adapter_sandbox_launcher() -> Path | None:
    if os.name != "posix" or shutil.which("bwrap") is None:
        return None
    candidate = Path(__file__).resolve().parents[3] / "scripts" / "rolo-adapter-sandbox"
    return candidate if candidate.is_file() else None


_YAML_SECTIONS: dict[str, dict[str, str]] = {
    "storage": {
        "config_dir": "rolo_config_dir",
        "artifact_dir": "rolo_artifact_dir",
        "output_dir": "rolo_output_dir",
        "scratch_dir": "rolo_scratch_dir",
    },
    "agent": {
        "provider": "coding_agent_provider",
        "executor": "coding_agent_executor",
        "base_url": "coding_agent_base_url",
        "model": "coding_agent_model",
        "api_key_env": "coding_agent_api_key_env",
        "executable": "coding_agent_executable",
        "timeout_s": "coding_agent_timeout_s",
        "preflight_url": "coding_agent_preflight_url",
        "connect_timeout_s": "coding_agent_connect_timeout_s",
        "auto_install": "coding_agent_auto_install",
        "require_auth": "coding_agent_require_auth",
    },
    "ros": {
        "auto_source": "ros_auto_source",
        "setup_files": "ros_setup_files",
        "domain_id": "ros_domain_id",
        "rmw_implementation": "ros_rmw_implementation",
    },
    "adapter_runtime": {
        "max_address_space_bytes": "rolo_adapter_max_address_space_bytes",
        "max_processes": "rolo_adapter_max_processes",
    },
    "agent_native": {
        "mode": "adapt_native_tool_mode",
        "robot_ids": "adapt_native_tool_robot_ids",
        "run_ids": "adapt_native_tool_run_ids",
        "max_calls": "adapt_native_tool_max_calls",
        "max_elapsed_s": "adapt_native_tool_max_elapsed_s",
        "max_result_bytes": "adapt_native_tool_max_result_bytes",
    },
    "workbench": {
        "plugin_dir": "rolo_workbench_plugin_dir",
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


class _RosEnvironmentSettingsSource(PydanticBaseSettingsSource):
    """Map standard ROS environment names into Rolo's settings model."""

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
    rolo_invocation_policy: Path = Field(default_factory=_default_invocation_policy)
    rolo_invocation_audit_log: Path = Field(default_factory=_default_invocation_audit_log)
    rolo_r3_authorizer: Path | None = None
    rolo_quiescence_provider: Path | None = None
    rolo_hardware_evidence_provider: Path | None = None
    rolo_adapter_sandbox_launcher: Path | None = Field(
        default_factory=_default_adapter_sandbox_launcher
    )
    rolo_adapter_unsandboxed_dev: bool = False
    rolo_adapter_max_address_space_bytes: int = Field(
        default=4 * 1024 * 1024 * 1024,
        ge=512 * 1024 * 1024,
        le=16 * 1024 * 1024 * 1024,
    )
    rolo_adapter_max_processes: int = Field(default=128, ge=16, le=512)
    rolo_host: str = "127.0.0.1"
    rolo_port: int = 8080
    rolo_api_token: str | None = None
    rolo_api_token_scopes: str = ""
    rolo_api_max_body_bytes: int = Field(default=16 * 1024 * 1024, ge=1024, le=64 * 1024 * 1024)
    rolo_workbench_plugin_dir: Path | None = None
    coding_agent_provider: str = "codex"
    coding_agent_executor: str = "codex"
    coding_agent_base_url: str | None = None
    coding_agent_api_key: str | None = None
    coding_agent_api_key_env: str = "CODING_AGENT_API_KEY"
    coding_agent_model: str | None = None
    coding_agent_executable: str = "codex"
    # Agent runs are interactive; only impose a deadline when explicitly set.
    coding_agent_timeout_s: int | None = None
    coding_agent_preflight_url: str | None = None
    coding_agent_connect_timeout_s: float = Field(default=3.0, gt=0, le=30)
    coding_agent_auto_install: bool = True
    coding_agent_require_auth: bool = True
    coding_agent_install_timeout_s: int = 300
    coding_agent_install_home: Path | None = None
    coding_agent_home: Path | None = None
    ros_auto_source: bool = True
    ros_setup_files: list[Path] = Field(default_factory=list)
    ros_domain_id: str | None = None
    ros_rmw_implementation: str | None = None
    adapt_operation_slice_mode: Literal["shadow", "canary"] = "shadow"
    adapt_operation_slice_robot_ids: str = ""
    adapt_operation_slice_run_ids: str = ""
    adapt_operation_slice_max_operations: int = Field(default=20, gt=0, le=50)
    adapt_native_tool_mode: Literal["off", "shadow", "canary", "active"] = "off"
    adapt_native_tool_robot_ids: str = ""
    adapt_native_tool_run_ids: str = ""
    adapt_native_tool_max_calls: int = Field(default=64, ge=1, le=10_000)
    adapt_native_tool_max_elapsed_s: float = Field(default=600, gt=0, le=86_400)
    adapt_native_tool_max_result_bytes: int = Field(default=8_000_000, ge=1, le=1_000_000_000)
    adapt_heuristic_agent_mode: Literal["disabled", "shadow", "enabled"] = "shadow"
    adapt_heuristic_agent_provider_enabled: bool = True
    adapt_heuristic_agent_timeout_s: int = Field(default=240, gt=0, le=3_600)
    adapt_heuristic_agent_batch_operations: int = Field(default=4, gt=0, le=64)
    adapt_heuristic_agent_parallelism: int = Field(default=2, gt=0, le=8)
    adapt_heuristic_agent_max_actions: int = Field(default=8, ge=0, le=32)
    adapt_heuristic_agent_max_operations: int = Field(default=20, gt=0, le=256)
    adapt_discovery_skill_path: Path = Path("skills/rolo-adapt-discovery/SKILL.md")
    adapt_mapping_skill_path: Path = Path("skills/rolo-operation-mapping/SKILL.md")
    robot_use_backend: str = "mock"
    openai_api_key: str | None = None
    openai_model: str | None = None
    wiki_polish_enabled: bool = True
    wiki_polish_model: str | None = None
    wiki_polish_timeout_s: int = 60
    wiki_insights_agent_enabled: bool = True
    wiki_insights_agent_timeout_s: int = 120
    wiki_insights_skill_path: Path = Path("skills/rolo-wiki-authoring/SKILL.md")

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
            _RosEnvironmentSettingsSource(settings_cls),
            _YamlSettingsSource(settings_cls),
            dotenv_settings,
            file_secret_settings,
        )

    @property
    def robot_config_dir(self) -> Path:
        return self.rolo_config_dir / "robots"

    @property
    def resolved_coding_agent_api_key(self) -> str | None:
        """Resolve the selected provider key without requiring it in YAML/config files."""
        if self.coding_agent_api_key:
            return self.coding_agent_api_key
        name = self.coding_agent_api_key_env.strip()
        return os.environ.get(name) if name else None


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
        "agent": {
            "provider": defaults.coding_agent_provider,
            "executor": defaults.coding_agent_executor,
            "base_url": defaults.coding_agent_base_url,
            "model": defaults.coding_agent_model,
            "api_key_env": defaults.coding_agent_api_key_env,
            "executable": defaults.coding_agent_executable,
            "timeout_s": defaults.coding_agent_timeout_s,
            "auto_install": defaults.coding_agent_auto_install,
            "require_auth": defaults.coding_agent_require_auth,
        },
        "ros": {
            "auto_source": defaults.ros_auto_source,
            "setup_files": [],
            "domain_id": None,
            "rmw_implementation": None,
        },
        "agent_native": {
            "mode": defaults.adapt_native_tool_mode,
            "robot_ids": defaults.adapt_native_tool_robot_ids,
            "run_ids": defaults.adapt_native_tool_run_ids,
            "max_calls": defaults.adapt_native_tool_max_calls,
            "max_elapsed_s": defaults.adapt_native_tool_max_elapsed_s,
            "max_result_bytes": defaults.adapt_native_tool_max_result_bytes,
        },
        "workbench": {
            "plugin_dir": None,
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
