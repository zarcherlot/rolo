from datetime import datetime, timedelta, timezone

import pytest

from rolo.core.models import DiscoveryReport, DiscoveryStatus, ProbeResult
from rolo.discovery_history_read_models import build_discovery_snapshot_collection
from rolo.stages.artifact_paths import ArtifactLayout

NOW = datetime(2026, 8, 20, tzinfo=timezone.utc)


def _report(discovery_id: str, created_at: datetime) -> DiscoveryReport:
    return DiscoveryReport(
        discovery_id=discovery_id,
        robot_id="demo",
        status=DiscoveryStatus.PARTIAL,
        platform={},
        capability_manifest={},
        probes={
            "hw": ProbeResult(
                layer="hw",
                status=DiscoveryStatus.SUCCEEDED,
                warnings=["bounded warning"],
            ),
            "ros": ProbeResult(layer="ros", status=DiscoveryStatus.PARTIAL),
            "application": ProbeResult(
                layer="application",
                status=DiscoveryStatus.UNAVAILABLE,
                errors=["probe unavailable"],
            ),
        },
        semantic_bindings={"cmd_vel": {"topic": "/cmd_vel"}},
        operation_candidates=[],
        discovery_mode="ARTIFACT DOC",
        created_at=created_at,
    )


def test_discovery_history_is_manifest_bounded_and_marks_latest(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reports = {
        "disc-old": _report("disc-old", NOW - timedelta(minutes=5)),
        "disc-new": _report("disc-new", NOW),
    }
    runs_root = ArtifactLayout(tmp_path).discovery_latest("demo").parent / "runs"
    for discovery_id in [*reports, "disc-unverified"]:
        (runs_root / discovery_id).mkdir(parents=True)

    monkeypatch.setattr(
        "rolo.discovery_history_read_models.load_latest_report",
        lambda root, robot_id: reports["disc-new"],
    )

    def load_report(root, robot_id, discovery_id):
        if discovery_id == "disc-unverified":
            raise ValueError("manifest mismatch")
        return reports[discovery_id]

    monkeypatch.setattr(
        "rolo.discovery_history_read_models.load_report",
        load_report,
    )

    history = build_discovery_snapshot_collection(
        tmp_path,
        "demo",
        limit=1,
    )

    assert history.schema_version == "rolo-discovery-snapshot-collection/v1"
    assert history.total == 2
    assert history.next_offset == 1
    assert history.excluded_unverified == 1
    assert history.items[0].discovery_id == "disc-new"
    assert history.items[0].is_latest is True
    assert history.items[0].probe_total == 3
    assert history.items[0].observed_probes == 1
    assert history.items[0].partial_probes == 1
    assert history.items[0].unavailable_probes == 1
    assert history.items[0].semantic_bindings == 1
    assert history.items[0].warning_count == 2
    assert history.items[0].discovery_mode == "ARTIFACT_DOC"
    assert history.integrity_status == "verified"
    assert "physical outcomes" in " ".join(history.limitations)


def test_discovery_history_returns_an_explicit_empty_verified_view(tmp_path) -> None:
    history = build_discovery_snapshot_collection(tmp_path, "demo")

    assert history.items == []
    assert history.total == 0
    assert history.excluded_unverified == 0
    assert any("latest discovery commit marker" in item for item in history.limitations)
