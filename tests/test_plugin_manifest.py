from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from rolo.stages.plugin_manifest import (
    StageAgentPluginManifest,
    discover_entrypoint_plugins,
    discover_plugins,
    install_plugin,
    load_plugin_manifest,
    plugin_manifest_json,
    uninstall_plugin,
    validate_plugin_manifest,
)


def _manifest(**updates: object) -> StageAgentPluginManifest:
    payload: dict[str, object] = {
        "plugin_id": "claude-code-reference",
        "plugin_version": "0.1.0",
        "requires_rolo": ">=0.1,<0.2",
        "stages": ["diagnose", "verify"],
        "executor_entrypoint": "rolo_stage_plugin_template.executor:factory",
        "harness_entrypoint": "rolo_stage_plugin_template.harness:factory",
    }
    payload.update(updates)
    return StageAgentPluginManifest.model_validate(payload)


def test_plugin_manifest_is_compatible_and_deterministic() -> None:
    manifest = validate_plugin_manifest(_manifest(), rolo_version="0.1.0")
    assert manifest.release_authority is False
    assert '"schema_version": "rolo-stage-agent-plugin/v1"' in plugin_manifest_json(manifest)


def test_plugin_manifest_rejects_incompatible_rolo_version() -> None:
    with pytest.raises(ValueError, match="requires Rolo"):
        validate_plugin_manifest(_manifest(), rolo_version="0.2.0")


def test_plugin_manifest_rejects_duplicate_stages(tmp_path: Path) -> None:
    path = tmp_path / "plugin.json"
    path.write_text(
        _manifest(stages=["diagnose", "diagnose"]).model_dump_json(), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="stages must be unique"):
        load_plugin_manifest(path)


def test_plugin_install_discover_and_uninstall_are_manifest_only(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    source.write_text(plugin_manifest_json(_manifest()), encoding="utf-8")
    root = tmp_path / "plugins"

    installed = install_plugin(source, root, rolo_version="0.1.0")
    assert installed.plugin_id == "claude-code-reference"
    assert [item.plugin_id for item in discover_plugins(root, rolo_version="0.1.0")] == [
        "claude-code-reference"
    ]
    with pytest.raises(FileExistsError):
        install_plugin(source, root, rolo_version="0.1.0")
    assert uninstall_plugin(root, "claude-code-reference") is True
    assert discover_plugins(root, rolo_version="0.1.0") == ()
    assert uninstall_plugin(root, "claude-code-reference") is False


def test_plugin_discovery_skips_incompatible_or_mismatched_manifests(tmp_path: Path) -> None:
    root = tmp_path / "plugins"
    root.mkdir()
    incompatible = _manifest()
    incompatible.requires_rolo = ">=9.0.0"
    (root / incompatible.plugin_id).mkdir()
    (root / incompatible.plugin_id / "plugin-manifest.json").write_text(
        plugin_manifest_json(incompatible), encoding="utf-8"
    )
    (root / "wrong-name").mkdir()
    (root / "wrong-name" / "plugin-manifest.json").write_text(
        plugin_manifest_json(_manifest()), encoding="utf-8"
    )
    assert discover_plugins(root, rolo_version="0.1.0") == ()


def test_entrypoint_discovery_requires_packaged_compatible_manifest(
    tmp_path: Path, monkeypatch
) -> None:
    manifest = _manifest()
    (tmp_path / "plugin-manifest.json").write_text(plugin_manifest_json(manifest), encoding="utf-8")
    distribution = SimpleNamespace(locate_file=lambda name: tmp_path / name)
    entrypoint = SimpleNamespace(
        name=manifest.plugin_id,
        value=manifest.executor_entrypoint,
        dist=distribution,
    )
    monkeypatch.setattr(
        "rolo.stages.plugin_manifest.entry_points", lambda **_: [entrypoint]
    )
    discovered = discover_entrypoint_plugins(rolo_version="0.1.0")
    assert discovered[0][0].plugin_id == manifest.plugin_id
