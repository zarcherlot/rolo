from __future__ import annotations

from pathlib import Path

import pytest

from rolo.stages.plugin_manifest import (
    StageAgentPluginManifest,
    load_plugin_manifest,
    plugin_manifest_json,
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

