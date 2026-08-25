from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

_MAX_VALUE_CHARS = 32_768
_MAX_PATHS = 128


def _scalar(name: str, value: str) -> str:
    if not value or len(value) > _MAX_VALUE_CHARS:
        raise ValueError(f"invalid runtime environment value for {name}")
    forbidden = ("\x00",) if name == "CYCLONEDDS_URI" else ("\x00", "\r", "\n")
    if any(character in value for character in forbidden):
        raise ValueError(f"runtime environment value contains control characters: {name}")
    return value


def _path_list(name: str, value: str, *, drop_unavailable: bool) -> str | None:
    if len(value) > _MAX_VALUE_CHARS:
        raise ValueError(f"invalid runtime path environment value for {name}")
    paths: list[str] = []
    for item in value.split(os.pathsep):
        if not item:
            continue
        if any(character in item for character in ("\x00", "\r", "\n")):
            raise ValueError(f"runtime path contains control characters: {name}")
        candidate = Path(item).expanduser()
        try:
            available = candidate.is_absolute() and candidate.exists()
        except OSError:
            available = False
        if not available:
            if drop_unavailable:
                continue
            raise ValueError(f"runtime path is not an available absolute path: {name}")
        try:
            resolved = str(candidate.resolve())
        except OSError as exc:
            if drop_unavailable:
                continue
            raise ValueError(
                f"runtime path is not an available absolute path: {name}"
            ) from exc
        if resolved not in paths:
            paths.append(resolved)
        if len(paths) > _MAX_PATHS:
            raise ValueError(f"runtime path environment contains too many entries: {name}")
    return os.pathsep.join(paths) if paths else None


def _file(name: str, value: str, *, drop_unavailable: bool) -> str | None:
    if len(value) > _MAX_VALUE_CHARS:
        raise ValueError(f"invalid runtime file environment value for {name}")
    if any(character in value for character in ("\x00", "\r", "\n")):
        raise ValueError(f"runtime file contains control characters: {name}")
    candidate = Path(value).expanduser()
    if not candidate.is_absolute() or not candidate.is_file():
        if drop_unavailable:
            return None
        raise ValueError(f"runtime file is not an available absolute file: {name}")
    return str(candidate.resolve())


class AdapterRuntimeContext(BaseModel):
    """Bounded, non-secret host context admitted to generated adapters."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    cyclonedds_uri: str | None = Field(default=None, alias="CYCLONEDDS_URI")
    ros_automatic_discovery_range: str | None = Field(
        default=None, alias="ROS_AUTOMATIC_DISCOVERY_RANGE"
    )
    ros_discovery_server: str | None = Field(default=None, alias="ROS_DISCOVERY_SERVER")
    ros_distro: str | None = Field(default=None, alias="ROS_DISTRO")
    ros_domain_id: str | None = Field(default=None, alias="ROS_DOMAIN_ID")
    ros_localhost_only: str | None = Field(default=None, alias="ROS_LOCALHOST_ONLY")
    ros_static_peers: str | None = Field(default=None, alias="ROS_STATIC_PEERS")
    ros_version: str | None = Field(default=None, alias="ROS_VERSION")
    rmw_implementation: str | None = Field(default=None, alias="RMW_IMPLEMENTATION")
    fastdds_profiles_file: str | None = Field(
        default=None, alias="FASTRTPS_DEFAULT_PROFILES_FILE"
    )
    ament_prefix_path: str | None = Field(default=None, alias="AMENT_PREFIX_PATH")
    cmake_prefix_path: str | None = Field(default=None, alias="CMAKE_PREFIX_PATH")
    colcon_prefix_path: str | None = Field(default=None, alias="COLCON_PREFIX_PATH")
    dyld_library_path: str | None = Field(default=None, alias="DYLD_LIBRARY_PATH")
    ld_library_path: str | None = Field(default=None, alias="LD_LIBRARY_PATH")
    pythonpath: str | None = Field(default=None, alias="PYTHONPATH")
    executable_path: str | None = Field(default=None, alias="PATH")

    @field_validator(
        "cyclonedds_uri",
        "ros_automatic_discovery_range",
        "ros_discovery_server",
        "ros_distro",
        "ros_domain_id",
        "ros_localhost_only",
        "ros_static_peers",
        "ros_version",
        "rmw_implementation",
    )
    @classmethod
    def validate_scalar(cls, value: str | None, info: ValidationInfo) -> str | None:
        if value is None:
            return None
        field_name = info.field_name
        alias = cls.model_fields[field_name].alias or field_name
        return _scalar(alias, value)

    @field_validator(
        "ament_prefix_path",
        "cmake_prefix_path",
        "colcon_prefix_path",
        "dyld_library_path",
        "ld_library_path",
        "pythonpath",
        "executable_path",
    )
    @classmethod
    def validate_path_list(cls, value: str | None, info: ValidationInfo) -> str | None:
        if value is None:
            return None
        field_name = info.field_name
        alias = cls.model_fields[field_name].alias or field_name
        return _path_list(alias, value, drop_unavailable=False)

    @field_validator("fastdds_profiles_file")
    @classmethod
    def validate_file(cls, value: str | None) -> str | None:
        return None if value is None else _file(
            "FASTRTPS_DEFAULT_PROFILES_FILE", value, drop_unavailable=False
        )

    @classmethod
    def capture(
        cls,
        source: Mapping[str, str],
        *,
        include_executable_path: bool = False,
    ) -> AdapterRuntimeContext:
        """Capture known keys; unavailable overlay paths are intentionally omitted."""
        values: dict[str, str] = {}
        for field in cls.model_fields.values():
            name = field.alias
            if name is None or (raw := source.get(name)) is None:
                continue
            if name == "PATH" and not include_executable_path:
                continue
            if not isinstance(raw, str):
                raise ValueError(f"invalid runtime environment value for {name}")
            if name == "FASTRTPS_DEFAULT_PROFILES_FILE":
                value = _file(name, raw, drop_unavailable=True)
            elif name.endswith("PATH"):
                value = _path_list(name, raw, drop_unavailable=True)
            else:
                value = _scalar(name, raw)
            if value is not None:
                values[name] = value
        return cls.model_validate(values)

    def as_environment(self) -> dict[str, str]:
        return self.model_dump(by_alias=True, exclude_none=True)


def admitted_runtime_environment(
    source: Mapping[str, str],
    *,
    include_executable_path: bool = False,
) -> dict[str, str]:
    """Compatibility API returning Runtime Context with environment-style keys."""
    return AdapterRuntimeContext.capture(
        source,
        include_executable_path=include_executable_path,
    ).as_environment()
