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

    robot_loop_env: str = "development"
    robot_loop_config_dir: Path = Path("configs/local")
    robot_loop_artifact_dir: Path = Path("artifacts")
    robot_loop_host: str = "127.0.0.1"
    robot_loop_port: int = 8080
    robot_use_backend: str = "mock"
    openai_api_key: str | None = None
    openai_model: str | None = None

    @property
    def robot_config_dir(self) -> Path:
        return self.robot_loop_config_dir / "robots"


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream)
    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML object in {path}")
    return data


@lru_cache
def get_settings() -> Settings:
    return Settings()
