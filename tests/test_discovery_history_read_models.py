from datetime import datetime, timedelta, timezone

import pytest

from rolo.core.models import DiscoveryReport, DiscoveryStatus, ProbeResult
from rolo.discovery_history_read_models import build_discovery_snapshot_collection
from rolo.stages.artifact_paths import ArtifactLayout

NOW = datetime(2026, 8, 20, tzinfo=timezone.utc)


def _report(
    discovery_id: str,
    created_at: datetime,
    *,
    heuristic_mode: str = "disabled",
    heuristic_status: str = "DISABLED",
    inferred_operation_count: int = 0,
    missing_evidence_count: int = 0,
) -> DiscoveryReport:
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
        heuristic_analysis_ref="artifact://private/heuristic/summary.json",
        heuristic_mode=heuristic_mode,
        heuristic_status=heuristic_status,
        heuristic_inferred_operation_count=inferred_operation_count,
        heuristic_missing_evidence_count=missing_evidence_count,
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

    assert history.schema_version == "rolo-discovery-snapshot-collection/v2"
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
    assert history.items[0].heuristic_summary.mode == "disabled"
    assert history.items[0].heuristic_summary.status == "DISABLED"
    assert history.items[0].heuristic_summary.influences_release is False
    assert history.integrity_status == "verified"
    assert "physical outcomes" in " ".join(history.limitations)
    assert "heuristic_analysis_ref" not in history.model_dump_json()
    assert "artifact://private" not in history.model_dump_json()


def test_discovery_history_returns_an_explicit_empty_verified_view(tmp_path) -> None:
    history = build_discovery_snapshot_collection(tmp_path, "demo")

    assert history.items == []
    assert history.total == 0
    assert history.excluded_unverified == 0
    assert any("latest discovery commit marker" in item for item in history.limitations)


@pytest.mark.parametrize(
    ("mode", "status", "inferred", "missing"),
    [
        ("shadow", "AGENT_COMPLETED", 4, 2),
        ("enabled", "FALLBACK", 1, 3),
        ("disabled", "DISABLED", 0, 0),
    ],
)
def test_discovery_history_exposes_only_the_safe_heuristic_summary(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    status: str,
    inferred: int,
    missing: int,
) -> None:
    report = _report(
        "disc-safe",
        NOW,
        heuristic_mode=mode,
        heuristic_status=status,
        inferred_operation_count=inferred,
        missing_evidence_count=missing,
    )
    runs_root = ArtifactLayout(tmp_path).discovery_latest("demo").parent / "runs"
    (runs_root / report.discovery_id).mkdir(parents=True)
    monkeypatch.setattr(
        "rolo.discovery_history_read_models.load_latest_report",
        lambda root, robot_id: report,
    )
    monkeypatch.setattr(
        "rolo.discovery_history_read_models.load_report",
        lambda root, robot_id, discovery_id: report,
    )

    history = build_discovery_snapshot_collection(tmp_path, "demo")

    safe = history.items[0].heuristic_summary
    assert safe.mode == mode
    assert safe.status == status
    assert safe.inferred_operation_count == inferred
    assert safe.missing_evidence_count == missing
    assert safe.influences_release is False
    assert "heuristic_analysis_ref" not in history.model_dump_json()


@pytest.mark.parametrize(
    ("mode", "status", "inferred", "missing"),
    [
        ("experimental", "AGENT_COMPLETED", 1, 0),
        ("shadow", "UNKNOWN", 1, 0),
        ("disabled", "DISABLED", 1, 0),
        ("shadow", "DISABLED", 0, 0),
    ],
)
def test_discovery_history_excludes_unsafe_heuristic_states(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    status: str,
    inferred: int,
    missing: int,
) -> None:
    report = _report(
        "disc-invalid",
        NOW,
        heuristic_mode=mode,
        heuristic_status=status,
        inferred_operation_count=inferred,
        missing_evidence_count=missing,
    )
    runs_root = ArtifactLayout(tmp_path).discovery_latest("demo").parent / "runs"
    (runs_root / report.discovery_id).mkdir(parents=True)
    monkeypatch.setattr(
        "rolo.discovery_history_read_models.load_latest_report",
        lambda root, robot_id: report,
    )
    monkeypatch.setattr(
        "rolo.discovery_history_read_models.load_report",
        lambda root, robot_id, discovery_id: report,
    )

    history = build_discovery_snapshot_collection(tmp_path, "demo")

    assert history.items == []
    assert history.total == 0
    assert history.excluded_unverified == 1
    assert any("excluded" in item for item in history.limitations)
