from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from rolo.agentd import create_agentd_app, create_bootstrap_agentd_app
from rolo.cli import app
from rolo.core.artifacts import ArtifactStore
from rolo.core.config import get_settings
from rolo.core.registry import RobotRegistry
from rolo.stages.adapt.discovery import DiscoveryService


def test_bootstrap_agentd_exposes_only_non_motion_readiness() -> None:
    with TestClient(create_bootstrap_agentd_app("demo_diff")) as client:
        health = client.get("/health")
        bootstrap = client.get("/v1/bootstrap")
        discovery = client.get("/v1/discovery")

    assert health.json()["phase"] == "BOOTSTRAP_READY"
    assert bootstrap.json()["motion_enabled"] is False
    assert bootstrap.json()["discovery_ready"] is True
    assert bootstrap.json()["clock"]["status"] == "LOCAL_CLOCK_AVAILABLE"
    assert discovery.status_code == 404


def test_bootstrap_wait_requires_matching_ready_daemon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *_args, **_kwargs: httpx.Response(
            200,
            json={"robot_id": "demo_diff", "phase": "BOOTSTRAP_READY"},
        ),
    )

    result = CliRunner().invoke(
        app,
        [
            "bootstrap-wait",
            "--robot",
            "demo_diff",
            "--url",
            "http://127.0.0.1:8100",
            "--timeout",
            "0.1",
        ],
    )

    assert result.exit_code == 0, result.output
    assert '"status": "READY"' in result.output


def test_full_agentd_waits_for_discovery(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROLO_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    get_settings.cache_clear()

    with TestClient(create_agentd_app("demo_diff")) as client:
        health = client.get("/health")
        capability = client.get("/v1/capability")
        snapshot = client.get("/v1/state/snapshot")

    get_settings.cache_clear()
    assert health.json()["robot_id"] == "demo_diff"
    assert health.json()["status"] == "DEGRADED"
    assert health.json()["phase"] == "DISCOVERY_PENDING"
    assert capability.json()["platform"]["drive_model"] == "differential"
    assert snapshot.json()["observation_status"] == "UNOBSERVED"
    assert snapshot.json()["safety"]["watchdog"] == "UNKNOWN"
    assert snapshot.json()["application"]["navigation"] == "UNKNOWN"


def test_full_agentd_observes_discovery_result_without_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact_root = tmp_path / "artifacts"
    monkeypatch.setenv("ROLO_ARTIFACT_DIR", str(artifact_root))
    get_settings.cache_clear()
    registry = RobotRegistry(Path("tests/fixtures/robots"))
    registry.load()
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "agentd-demo"\n', encoding="utf-8")

    with TestClient(create_agentd_app("demo_diff")) as client:
        before = client.get("/health")
        DiscoveryService(ArtifactStore(artifact_root)).run(
            robot=registry.get("demo_diff"),
            urdf_path=Path("tests/fixtures/profiles/differential_drive.urdf"),
            source_roots=[tmp_path],
        )
        after = client.get("/health")

    get_settings.cache_clear()
    assert before.json()["phase"] == "DISCOVERY_PENDING"
    assert after.json()["phase"] in {"DISCOVERY_PARTIAL", "AGENTD_READY"}
