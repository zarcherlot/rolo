"""Versioned manifest and compatibility checks for external Stage Agent plugins."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version
from pydantic import BaseModel, ConfigDict, Field

from rolo import __version__

PLUGIN_SCHEMA = "rolo-stage-agent-plugin/v1"


class StageAgentPluginManifest(BaseModel):
    """Secret-free metadata shipped beside an external Stage Agent executor."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-stage-agent-plugin/v1"] = PLUGIN_SCHEMA
    plugin_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
    plugin_version: str = Field(min_length=1, max_length=64)
    api_version: Literal["stage-agent/v1"] = "stage-agent/v1"
    requires_rolo: str = Field(min_length=1, max_length=128)
    stages: list[Literal["diagnose", "verify"]] = Field(min_length=1)
    executor_entrypoint: str = Field(min_length=3, max_length=512)
    harness_entrypoint: str | None = Field(default=None, max_length=512)
    release_authority: Literal[False] = False


def validate_plugin_manifest(
    manifest: StageAgentPluginManifest,
    *,
    rolo_version: str = __version__,
) -> StageAgentPluginManifest:
    """Reject incompatible plugin metadata before importing its entry points."""

    if len(manifest.stages) != len(set(manifest.stages)):
        raise ValueError("plugin stages must be unique")
    try:
        specifier = SpecifierSet(manifest.requires_rolo)
        version = Version(rolo_version)
    except (InvalidSpecifier, InvalidVersion) as exc:
        raise ValueError("plugin version compatibility declaration is invalid") from exc
    if version not in specifier:
        raise ValueError(
            f"plugin {manifest.plugin_id!r} requires Rolo {manifest.requires_rolo}, "
            f"but running {rolo_version}"
        )
    return manifest


def load_plugin_manifest(
    path: Path, *, rolo_version: str = __version__
) -> StageAgentPluginManifest:
    """Load and validate a plugin manifest without loading plugin code."""

    try:
        manifest = StageAgentPluginManifest.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"invalid Stage Agent plugin manifest: {path}") from exc
    return validate_plugin_manifest(manifest, rolo_version=rolo_version)


def plugin_manifest_json(manifest: StageAgentPluginManifest) -> str:
    """Render deterministic JSON for packaging and digest checks."""

    return json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"
