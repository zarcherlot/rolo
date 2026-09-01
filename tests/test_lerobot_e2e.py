"""Opt-in end-to-end acceptance against a real Hugging Face LeRobot checkout.

LeRobot is intentionally not a dependency of the rolo test environment. Set
``ROLO_RUN_LEROBOT_E2E=1`` and ``LEROBOT_ROOT`` in a Python 3.12+ environment
that has installed LeRobot to run this test.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from rolo.adapter_runner import BoundedAdapterRunner
from rolo.core.artifacts import ArtifactStore
from rolo.core.models import (
    DiscoveryReport,
    DiscoveryStatus,
    OperationCandidate,
    RouteEvidence,
)
from rolo.core.registry import RobotRegistry
from rolo.stages.adapt.active_discovery import ActiveDiscoveryInputs, ActiveProbeMode
from rolo.stages.adapt.discovery import DiscoveryService, load_latest_report
from rolo.stages.adapt.routes import probe_routes
from rolo.stages.adapt.target_fingerprint import runtime_environment_from_report

pytestmark = [
    pytest.mark.lerobot,
    pytest.mark.skipif(
        os.environ.get("ROLO_RUN_LEROBOT_E2E") != "1",
        reason="set ROLO_RUN_LEROBOT_E2E=1 to run the opt-in LeRobot integration test",
    ),
]


def _manifest() -> dict:
    path = Path(__file__).resolve().parents[1] / ".ci" / "integrations" / "lerobot.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _lerobot_root() -> Path:
    raw_root = os.environ.get("LEROBOT_ROOT")
    if not raw_root:
        pytest.fail("LEROBOT_ROOT must point to a checked-out LeRobot repository")
    root = Path(raw_root).expanduser().resolve()
    if not (root / "pyproject.toml").is_file() or not (root / "src" / "lerobot").is_dir():
        pytest.fail(f"LEROBOT_ROOT is not a LeRobot source checkout: {root}")
    return root


def _lerobot_info_executable() -> str:
    name = _manifest()["entrypoints"]["info"]
    executable = os.environ.get("LEROBOT_INFO") or shutil.which(name)
    if not executable:
        pytest.fail(f"{name} is not installed; install LeRobot in the integration environment")
    return executable


def _lerobot_find_cameras_executable() -> Path:
    name = _manifest()["entrypoints"]["find_cameras"]
    raw = os.environ.get("LEROBOT_FIND_CAMERAS") or shutil.which(name)
    if not raw:
        pytest.fail(f"{name} is unavailable in the integration environment")
    executable = Path(raw).expanduser().resolve()
    if not executable.is_file():
        pytest.fail(f"lerobot-find-cameras is not an executable file: {executable}")
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
    wiki = (artifact.parent / "robot_wiki.md").read_text(encoding="utf-8")
    assert "## 目标主机与软件栈" in wiki
    assert "lerobot | python | python/pyproject" in wiki
    assert "## 运行时与通信接口" in wiki
    assert "lerobot-info" in wiki
    assert "### ROS 运行时与拓扑" not in wiki
    assert "ROS 发行版" not in wiki
    assert "ROS_RUNTIME_GRAPH" not in wiki
    assert "ROS" not in wiki

    application_probe = report.probes["application"]
    assert application_probe.status in {"SUCCEEDED", "DEGRADED"}
    projects = application_probe.data.get("projects", [])
    project = next(item for item in projects if item.get("root") == str(root))
    assert "python/pyproject" in project["build_systems"]
    assert "lerobot" in project["packages"]
    assert project["entrypoints"]

    declared_cli_routes = {route.resource_id: route for route in probe_routes(application_probe)}
    assert "cli:lerobot-info" in declared_cli_routes
    assert "cli:lerobot-find-cameras" in declared_cli_routes
    assert all(not route.observed for route in declared_cli_routes.values())

    # A source checkout may produce candidates, but it cannot prove target
    # runtime route availability or publish a verified Tool Catalog.
    assert all(candidate.status != "VERIFIED" for candidate in report.operation_candidates)
    assert "app.camera.list" not in {
        candidate.operation for candidate in report.operation_candidates
    }


@pytest.mark.skipif(
    sys.platform != "linux" or shutil.which("bwrap") is None,
    reason="the LeRobot runtime acceptance requires Linux bubblewrap",
)
def test_lerobot_editable_cli_runs_in_production_sandbox(tmp_path: Path) -> None:
    """Bind one real editable LeRobot CLI to a scoped, sandboxed runtime context."""
    root = _lerobot_root()
    find_cameras = _lerobot_find_cameras_executable()
    help_run = subprocess.run(
        [str(find_cameras), "--help"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert help_run.returncode == 0, help_run.stderr[-4_000:]
    assert "camera" in help_run.stdout.casefold()

    route = RouteEvidence(
        resource_id=f"cli:{find_cameras}",
        kind="cli",
        endpoint=str(find_cameras),
        evidence_origin="OBSERVED_RUNTIME",
        source="lerobot-e2e:verified-help",
    )
    report = DiscoveryReport(
        discovery_id="lerobot-runtime-e2e",
        robot_id="demo_diff",
        status=DiscoveryStatus.SUCCEEDED,
        platform={},
        capability_manifest={},
        probes={},
        operation_candidates=[
            OperationCandidate(
                operation="app.camera.list",
                evidence=[str(find_cameras)],
                route_evidence=[route],
            )
        ],
    )
    runtime = runtime_environment_from_report(
        report,
        operations={"app.camera.list"},
    )
    assert runtime["PATH"] == str(find_cameras.parent)
    assert "PYTHONPATH" in runtime
    editable_paths = map(Path, runtime["PYTHONPATH"].split(os.pathsep))
    assert all(root == path or root in path.parents for path in editable_paths)

    release = tmp_path / "release"
    release.mkdir()
    launcher = Path(__file__).resolve().parents[1] / "scripts" / "rolo-adapter-sandbox"
    completed = BoundedAdapterRunner(
        sandbox_launcher=launcher,
        allow_unsandboxed_development=False,
    ).run(
        [str(find_cameras), "--help"],
        cwd=release,
        timeout_s=60,
        max_stdout_bytes=200_000,
        max_stderr_bytes=200_000,
        runtime_environment=runtime,
    )

    assert completed.returncode == 0, completed.stderr[-4_000:]
    assert completed.timed_out is False
    assert completed.output_limited is False
    assert "camera" in completed.stdout.casefold()
