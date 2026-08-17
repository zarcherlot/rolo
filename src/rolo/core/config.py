from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    rolo_env: str = "development"
    rolo_config_dir: Path = Path("configs/local")
    rolo_artifact_dir: Path = Path("artifacts")
    rolo_host: str = "127.0.0.1"
    rolo_port: int = 8080
    coding_agent_provider: str = "codex"
    coding_agent_executor: str = "codex"
    coding_agent_base_url: str | None = None
    coding_agent_api_key: str | None = None
    coding_agent_model: str | None = None
    coding_agent_executable: str = "codex"
    coding_agent_timeout_s: int = 1800
    coding_agent_auto_install: bool = True
    coding_agent_require_auth: bool = True
    coding_agent_install_timeout_s: int = 300
    coding_agent_install_home: Path | None = None
    coding_agent_home: Path | None = None
    robot_use_backend: str = "mock"
    openai_api_key: str | None = None
    openai_model: str | None = None

    @property
    def robot_config_dir(self) -> Path:
        return self.rolo_config_dir / "robots"


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream)
    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML object in {path}")
    return data


@lru_cache
def get_settings() -> Settings:
    return Settings()
