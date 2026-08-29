"""Versioned manifest and compatibility checks for external Stage Agent plugins."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from importlib.metadata import EntryPoint, entry_points
from pathlib import Path
from typing import Literal

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version
from pydantic import BaseModel, ConfigDict, Field

from rolo import __version__
from rolo.core.persistence import atomic_write_text, interprocess_lock

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


def _plugin_dir(plugin_root: Path, plugin_id: str) -> Path:
    """Resolve one validated plugin directory without accepting path traversal."""

    # Parsing through the model applies the same identifier rule used by manifests.
    StageAgentPluginManifest(
        plugin_id=plugin_id,
        plugin_version="0.0.0",
        requires_rolo=f">={__version__}",
        stages=["diagnose"],
        executor_entrypoint="plugin:factory",
    )
    root = plugin_root.expanduser().resolve()
    path = (root / plugin_id).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:  # pragma: no cover - defensive after model validation
        raise ValueError("plugin directory escapes plugin root") from exc
    return path


def install_plugin(
    manifest_path: Path,
    plugin_root: Path,
    *,
    rolo_version: str = __version__,
    replace: bool = False,
) -> StageAgentPluginManifest:
    """Install a validated manifest into a local plugin index.

    Code is intentionally not copied or imported here: package installation remains the
    caller's responsibility, while Rolo atomically records only the secret-free manifest.
    """

    manifest = load_plugin_manifest(manifest_path, rolo_version=rolo_version)
    destination = _plugin_dir(plugin_root, manifest.plugin_id)
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / "plugin-manifest.json"
    with interprocess_lock(target):
        if target.exists() and not replace:
            raise FileExistsError(f"plugin is already installed: {manifest.plugin_id}")
        atomic_write_text(target, plugin_manifest_json(manifest), acquire_lock=False)
        atomic_write_text(
            destination / "installation.json",
            json.dumps(
                {
                    "schema_version": "rolo-plugin-installation/v1",
                    "plugin_id": manifest.plugin_id,
                    "plugin_version": manifest.plugin_version,
                    "installed_at": datetime.now(timezone.utc).isoformat(),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            acquire_lock=False,
        )
    return manifest


def discover_plugins(
    plugin_root: Path, *, rolo_version: str = __version__
) -> tuple[StageAgentPluginManifest, ...]:
    """Discover compatible installed manifests without importing plugin code."""

    root = plugin_root.expanduser().resolve()
    if not root.is_dir():
        return ()
    discovered: list[StageAgentPluginManifest] = []
    for manifest_path in sorted(root.glob("*/plugin-manifest.json")):
        try:
            manifest = load_plugin_manifest(manifest_path, rolo_version=rolo_version)
        except ValueError:
            continue
        if manifest.plugin_id != manifest_path.parent.name:
            continue
        discovered.append(manifest)
    return tuple(discovered)


def discover_entrypoint_plugins(
    *,
    rolo_version: str = __version__,
    group: str = "rolo.agent_executors",
) -> tuple[tuple[StageAgentPluginManifest, EntryPoint], ...]:
    """Discover distribution plugins and validate their packaged manifest first."""

    try:
        candidates = entry_points(group=group)
    except TypeError:  # pragma: no cover - Python 3.10 compatibility
        candidates = entry_points().select(group=group)
    discovered: list[tuple[StageAgentPluginManifest, EntryPoint]] = []
    for item in candidates:
        distribution = item.dist
        if distribution is None:
            continue
        try:
            manifest_path = Path(distribution.locate_file("plugin-manifest.json"))
            manifest = load_plugin_manifest(manifest_path, rolo_version=rolo_version)
        except (OSError, ValueError):
            continue
        if item.name != manifest.plugin_id and item.value != manifest.executor_entrypoint:
            continue
        discovered.append((manifest, item))
    return tuple(discovered)


def uninstall_plugin(plugin_root: Path, plugin_id: str) -> bool:
    """Remove one manifest-only installation and report whether it existed."""

    destination = _plugin_dir(plugin_root, plugin_id)
    if not destination.exists():
        return False
    if not destination.is_dir():
        raise ValueError(f"plugin installation is not a directory: {plugin_id}")
    shutil.rmtree(destination)
    return True
