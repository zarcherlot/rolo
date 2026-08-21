import json
from datetime import datetime, timezone
from hashlib import sha256

import pytest

from rolo.core.models import DiscoveryReport, DiscoveryStatus, ProbeResult
from rolo.stages.adapt.active_discovery import ActiveDiscoveryReport
from rolo.stages.adapt.wiki import WikiGenerationMetadata
from rolo.stages.adapt.wiki_diff import WikiDiscoveryChange, WikiDiscoveryDiff
from rolo.stages.adapt.wiki_insights import WikiHeuristicFinding, WikiInsightBundle
from rolo.stages.artifact_paths import ArtifactLayout
from rolo.wiki_read_models import build_robot_wiki, wiki_evidence_specs

NOW = datetime(2026, 8, 20, tzinfo=timezone.utc)


def _write_snapshot(tmp_path, monkeypatch: pytest.MonkeyPatch):
    report = DiscoveryReport(
        discovery_id="disc-wiki",
        robot_id="demo",
        status=DiscoveryStatus.PARTIAL,
        platform={},
        capability_manifest={},
        probes={
            "hw": ProbeResult(
                layer="hw",
                status=DiscoveryStatus.SUCCEEDED,
                data={"devices": [{"name": "camera"}], "architecture": "arm64"},
            ),
            "linux": ProbeResult(
                layer="linux",
                status=DiscoveryStatus.SUCCEEDED,
                data={"host": {"system": "Linux", "release": "6.6"}, "software": {}},
            ),
            "ros": ProbeResult(
                layer="ros",
                status=DiscoveryStatus.PARTIAL,
                data={"ros_distro": "humble", "nodes": [], "topics": ["/scan"]},
            ),
        },
        created_at=NOW,
    )
    active = ActiveDiscoveryReport.model_validate(
        {
            "discovery_id": report.discovery_id,
            "robot_id": report.robot_id,
            "technical_status": "PARTIAL",
            "discovery_mode": {
                "level": "ARTIFACT_DOC",
                "confidence": "MEDIUM",
                "reason": "test",
            },
            "inputs": {},
            "coverage": {},
            "executables": [],
            "unattributed_source_interfaces": [],
            "dependency_summary": {"missing": ["camera-driver"], "conflicting": []},
            "unknowns": ["configuration remains unresolved"],
            "warnings": [],
            "created_at": NOW,
        }
    )
    insights = WikiInsightBundle(
        robot_id=report.robot_id,
        discovery_id=report.discovery_id,
        findings=[
            WikiHeuristicFinding(
                category="MAINTENANCE",
                statement=r"Review C:\private\robot.yaml before deployment.",
                confidence="LOW",
                basis=["verified discovery"],
                verification="Confirm password=do-not-leak with the maintainer.",
            )
        ],
    )
    diff = WikiDiscoveryDiff(
        robot_id=report.robot_id,
        discovery_id=report.discovery_id,
        baseline_discovery_id="disc-before",
        status="CHANGED",
        changes=[
            WikiDiscoveryChange(
                category="APPLICATION",
                added=["navigation"],
                removed=["/home/robot/private/config.yaml"],
            )
        ],
    )
    wiki = (
        "# Robot Wiki\n\n## Summary\n\n"
        "- Latest discovery is partial.\n"
        "- artifact://discovery/demo/runs/disc-wiki/report.json\n"
        "- api_key=do-not-leak\n"
    )
    generation = WikiGenerationMetadata(
        status="DETERMINISTIC_FALLBACK",
        draft_sha256="a" * 64,
        generated_sha256=sha256(wiki.encode()).hexdigest(),
        fallback_reason="model polishing is not configured",
    )
    run_root = ArtifactLayout(tmp_path).discovery_run(report.robot_id, report.discovery_id)
    run_root.mkdir(parents=True)
    (run_root / "active_discovery_report.json").write_text(
        active.model_dump_json(), encoding="utf-8"
    )
    (run_root / "wiki_insights.json").write_text(
        insights.model_dump_json(), encoding="utf-8"
    )
    (run_root / "wiki_diff.json").write_text(diff.model_dump_json(), encoding="utf-8")
    (run_root / "wiki_generation.json").write_text(
        generation.model_dump_json(), encoding="utf-8"
    )
    wiki_path = run_root / "robot_wiki.md"
    wiki_path.write_text(wiki, encoding="utf-8")
    monkeypatch.setattr("rolo.wiki_read_models.load_latest_report", lambda root, robot: report)
    return wiki_path


def test_robot_wiki_separates_verified_machine_insights_from_sanitized_narrative(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wiki_path = _write_snapshot(tmp_path, monkeypatch)

    snapshot = build_robot_wiki(tmp_path, "demo")
    serialized = snapshot.model_dump_json()

    assert snapshot.schema_version == "rolo-robot-wiki/v1"
    assert snapshot.content_origin == "GENERATED_MATCH"
    assert snapshot.content_integrity == "validated"
    assert snapshot.diff_status == "CHANGED"
    assert len(snapshot.layers) == 5
    assert snapshot.insights[0].evidence_id.startswith("ev_")
    assert snapshot.changes[0].evidence_id.startswith("ev_")
    assert "do-not-leak" not in serialized
    assert "private\\robot.yaml" not in serialized
    assert "/home/robot" not in serialized
    assert "artifact://" not in serialized

    wiki_path.write_text("# Robot Wiki\n\nMaintainer note.\n", encoding="utf-8")
    edited = build_robot_wiki(tmp_path, "demo")
    assert edited.content_origin == "HUMAN_EDITED"
    assert edited.content_integrity == "unverified"


def test_wiki_evidence_specs_resolve_only_machine_evidence(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_snapshot(tmp_path, monkeypatch)

    specs = wiki_evidence_specs(tmp_path, "demo")

    assert {item.source_kind for item in specs.values()} == {"wiki_insight", "wiki_diff"}
    assert all(item.evidence_id.startswith("ev_") for item in specs.values())
    assert "robot_wiki.md" not in json.dumps(
        {key: value.model_dump(mode="json") for key, value in specs.items()},
        default=str,
    )
