from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from rolo.core.models import DiscoveryStatus
from rolo.targets.runtime_deployment import TargetWorkspaceRef
from rolo.targets.source_discovery import (
    TargetSourceDiscoveryRequest,
    TargetSourceDiscoverySnapshot,
    discover_target_source,
)

NOW = datetime(2026, 8, 26, 9, 0, tzinfo=timezone.utc)
APPROVAL_ID = "approval-" + "a" * 32


def _workspace(root: Path) -> TargetWorkspaceRef:
    return TargetWorkspaceRef(
        workspace_id="wheeltec-source",
        target_id="wheeltec-target",
        robot_id="wheeltec",
        root=str(root.resolve()),
    )


def _request(root: Path, *, scan_roots: list[str] | None = None) -> TargetSourceDiscoveryRequest:
    return TargetSourceDiscoveryRequest(
        request_id="source-discovery-wheeltec",
        workspace=_workspace(root),
        scan_roots=scan_roots or ["."],
        approval_id=APPROVAL_ID,
    )


def test_target_source_discovery_returns_only_strict_relative_structured_facts(
    tmp_path: Path,
) -> None:
    root = tmp_path / "workspace"
    (root / "src").mkdir(parents=True)
    (root / "config").mkdir()
    (root / "pyproject.toml").write_text(
        """
[project]
name = "wheeltec-driver"
dependencies = ["pyserial>=3.5"]

[project.scripts]
wheeltec-drive = "driver:main"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (root / "src" / "driver.py").write_text(
        "self.publisher = self.create_publisher(Twist, '/cmd_vel', 10)\n",
        encoding="utf-8",
    )
    (root / "config" / "limits.yaml").write_text(
        "max_linear_velocity: 0.45\ncommand_topic: /cmd_vel\n",
        encoding="utf-8",
    )
    secret = "SECRET-README-TEXT-MUST-NOT-CROSS-SSH"
    (root / "README.md").write_text(secret, encoding="utf-8")

    snapshot = discover_target_source(_request(root), observed_at=NOW)

    assert snapshot.status == DiscoveryStatus.SUCCEEDED
    assert len(snapshot.projects) == 1
    project = snapshot.projects[0]
    assert project.root == "."
    assert project.packages == ["wheeltec-driver"]
    assert project.readmes == ["README.md"]
    assert project.dependency_declarations[0].source == "pyproject.toml"
    assert project.ros_interfaces[0].source == "src/driver.py"
    assert project.semantic_candidates[0].source_path == "config/limits.yaml"
    assert snapshot.route_evidence[0].source.startswith("source:.#entrypoint/")

    encoded = snapshot.model_dump_json()
    assert secret not in encoded
    assert str(root.resolve()) not in encoded
    assert TargetSourceDiscoverySnapshot.model_validate_json(encoded) == snapshot


def test_target_source_discovery_binds_digest_and_rejects_scope_ambiguity(
    tmp_path: Path,
) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        "[project]\nname='digest-test'\n",
        encoding="utf-8",
    )
    snapshot = discover_target_source(_request(root), observed_at=NOW)
    payload = snapshot.model_dump(mode="json")
    payload["projects"][0]["packages"] = ["tampered"]
    with pytest.raises(ValidationError, match="summary digest mismatch"):
        TargetSourceDiscoverySnapshot.model_validate(payload)

    with pytest.raises(ValidationError, match="cannot be combined"):
        _request(root, scan_roots=[".", "src"])
    with pytest.raises(ValidationError, match="unique and sorted"):
        _request(root, scan_roots=["src", "config"])
    with pytest.raises(ValidationError, match="normalized and relative"):
        _request(root, scan_roots=["../outside"])


def test_target_source_discovery_rejects_symlinked_scan_root(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    real = root / "real"
    real.mkdir(parents=True)
    (real / "pyproject.toml").write_text("[project]\nname='real'\n", encoding="utf-8")
    link = root / "linked"
    try:
        link.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlink creation is unavailable on this host")

    with pytest.raises(ValueError, match="symbolic link"):
        discover_target_source(_request(root, scan_roots=["linked"]), observed_at=NOW)


def test_target_source_discovery_schema_rejects_unstructured_extra_output(
    tmp_path: Path,
) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='strict'\n", encoding="utf-8")
    snapshot = discover_target_source(_request(root), observed_at=NOW)
    payload = json.loads(snapshot.model_dump_json())
    payload["projects"][0]["source_text"] = "not allowed"

    with pytest.raises(ValidationError, match="extra_forbidden"):
        TargetSourceDiscoverySnapshot.model_validate(payload)
