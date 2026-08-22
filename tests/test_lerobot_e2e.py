"""Opt-in end-to-end acceptance against a real Hugging Face LeRobot checkout.

LeRobot is intentionally not a dependency of the rolo test environment. Set
``ROLO_RUN_LEROBOT_E2E=1`` and ``LEROBOT_ROOT`` in a Python 3.12+ environment
that has installed LeRobot to run this test.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from rolo.core.artifacts import ArtifactStore
from rolo.core.registry import RobotRegistry
from rolo.stages.adapt.active_discovery import ActiveDiscoveryInputs, ActiveProbeMode
from rolo.stages.adapt.discovery import DiscoveryService, load_latest_report

pytestmark = [
    pytest.mark.lerobot,
    pytest.mark.skipif(
        os.environ.get("ROLO_RUN_LEROBOT_E2E") != "1",
        reason="set ROLO_RUN_LEROBOT_E2E=1 to run the opt-in LeRobot integration test",
    ),
]


def _lerobot_root() -> Path:
    raw_root = os.environ.get("LEROBOT_ROOT")
    if not raw_root:
        pytest.fail("LEROBOT_ROOT must point to a checked-out LeRobot repository")
    root = Path(raw_root).expanduser().resolve()
    if not (root / "pyproject.toml").is_file() or not (root / "src" / "lerobot").is_dir():
        pytest.fail(f"LEROBOT_ROOT is not a LeRobot source checkout: {root}")
    return root


def _lerobot_info_executable() -> str:
    executable = os.environ.get("LEROBOT_INFO") or shutil.which("lerobot-info")
    if not executable:
        pytest.fail("lerobot-info is not installed; install LeRobot in the integration environment")
    return executable


def test_lerobot_cli_to_rolo_discovery_e2e(tmp_path: Path) -> None:
    """Exercise a real LeRobot CLI and ingest its source as bounded rolo evidence."""
    root = _lerobot_root()
    info = _lerobot_info_executable()

    info_run = subprocess.run(
        [info],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert info_run.returncode == 0, info_run.stderr[-4_000:]
    assert info_run.stdout.strip(), "lerobot-info returned no diagnostic output"

    artifact_root = tmp_path / "artifacts"
    registry = RobotRegistry(Path("tests/fixtures/robots"))
    registry.load()
    report, artifact = DiscoveryService(ArtifactStore(artifact_root)).run(
        robot=registry.get("demo_diff"),
        active_inputs=ActiveDiscoveryInputs(
            source_roots=[root],
            active_probe=ActiveProbeMode.NONE,
        ),
    )

    assert report.status.value != "FAILED"
    assert artifact.is_file()
    persisted = load_latest_report(artifact_root, "demo_diff")
    assert persisted.discovery_id == report.discovery_id
    assert persisted.review_ref.endswith("/robot_wiki.md")

    application_probe = report.probes["application"]
    assert application_probe.status in {"SUCCEEDED", "DEGRADED"}
    projects = application_probe.data.get("projects", [])
    project = next(item for item in projects if item.get("root") == str(root))
    assert "python/pyproject" in project["build_systems"]
    assert "lerobot" in project["packages"]
    assert project["entrypoints"]

    # A source checkout may produce candidates, but it cannot prove target
    # runtime route availability or publish a verified Tool Catalog.
    assert all(candidate.status != "VERIFIED" for candidate in report.operation_candidates)
