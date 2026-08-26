from __future__ import annotations

import json
import os
import re
import stat
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from rolo.core.persistence import atomic_write_text
from rolo.targets.models import TargetConnectionProfile, TargetProfile, TargetTransport

_SECRET_FIELD_PARTS = {
    "access_token",
    "api_key",
    "key_material",
    "password",
    "private_key",
    "secret",
}
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def _validate_identifier(value: str, *, field_name: str) -> str:
    if _IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"invalid {field_name}")
    return value


def _assert_secret_free(value: Any, *, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).casefold().replace("-", "_")
            if normalized in _SECRET_FIELD_PARTS or normalized.endswith("_password"):
                raise ValueError(
                    f"secret-bearing field is forbidden in profile storage: {path}.{key}"
                )
            _assert_secret_free(item, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _assert_secret_free(item, path=f"{path}[{index}]")


def _serialized(model: BaseModel) -> str:
    payload = model.model_dump(mode="json")
    _assert_secret_free(payload)
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _restrict_file(path: Path) -> None:
    if os.name == "posix":
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)


class TargetProfileRegistry:
    """Atomic, strict, secret-free storage for target and connection profiles."""

    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()
        self.targets_dir = self.root / "targets"
        self.connections_dir = self.root / "connections"

    def _target_path(self, target_id: str) -> Path:
        _validate_identifier(target_id, field_name="target_id")
        return self.targets_dir / f"{target_id}.json"

    def _connection_path(self, connection_profile_id: str) -> Path:
        _validate_identifier(
            connection_profile_id,
            field_name="connection_profile_id",
        )
        return self.connections_dir / f"{connection_profile_id}.json"

    @staticmethod
    def _load(path: Path, model: type[BaseModel]) -> BaseModel:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid profile file {path}: {exc}") from exc
        _assert_secret_free(payload)
        return model.model_validate(payload)

    def save_connection(self, profile: TargetConnectionProfile) -> Path:
        path = self._connection_path(profile.connection_profile_id)
        atomic_write_text(path, _serialized(profile))
        _restrict_file(path)
        return path

    def save_target(self, profile: TargetProfile) -> Path:
        if profile.transport == TargetTransport.SSH:
            connection = self.get_connection(profile.connection_profile_id or "")
            if connection.trust_level != profile.trust_level:
                raise ValueError("target and SSH connection trust levels must match")
        path = self._target_path(profile.target_id)
        atomic_write_text(path, _serialized(profile))
        _restrict_file(path)
        return path

    def get_target(self, target_id: str) -> TargetProfile:
        profile = self._load(self._target_path(target_id), TargetProfile)
        assert isinstance(profile, TargetProfile)
        if profile.target_id != target_id:
            raise ValueError(f"target profile filename does not match target_id: {target_id}")
        return profile

    def get_connection(self, connection_profile_id: str) -> TargetConnectionProfile:
        profile = self._load(
            self._connection_path(connection_profile_id),
            TargetConnectionProfile,
        )
        assert isinstance(profile, TargetConnectionProfile)
        if profile.connection_profile_id != connection_profile_id:
            raise ValueError(
                "connection profile filename does not match connection_profile_id: "
                f"{connection_profile_id}"
            )
        return profile

    def list_targets(self) -> list[TargetProfile]:
        if not self.targets_dir.exists():
            return []
        return [self.get_target(path.stem) for path in sorted(self.targets_dir.glob("*.json"))]

    def list_connections(self) -> list[TargetConnectionProfile]:
        if not self.connections_dir.exists():
            return []
        return [
            self.get_connection(path.stem)
            for path in sorted(self.connections_dir.glob("*.json"))
        ]
