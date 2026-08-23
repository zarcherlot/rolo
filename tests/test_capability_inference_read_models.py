from datetime import datetime, timezone

import pytest

from rolo.capability_read_models import _summary, get_capability_detail
from rolo.core.models import (
    DiscoveryReport,
    DiscoveryStatus,
    OperationCandidate,
    RobotCapability,
    RouteEvidence,
)
from rolo.stages.adapt.operation_registry import canonical_operation_registry

NOW = datetime(2026, 8, 23, tzinfo=timezone.utc)
ROBOT = RobotCapability(
    schema_version="robot-capability/v1",
    robot_id="demo",
    adapter="test-adapter",
    platform={},
    geometry={},
    sensors={},
    features={},
)


def _heuristic_report(operation: str) -> DiscoveryReport:
    return DiscoveryReport(
        discovery_id="disc-agent",
        robot_id=ROBOT.robot_id,
        status=DiscoveryStatus.PARTIAL,
        platform={},
        capability_manifest={},
        probes={},
        operation_candidates=[
            OperationCandidate(
                operation=operation,
                origin="HEURISTIC_AGENT",
                route_evidence=[
                    RouteEvidence(
                        resource_id="ros_topic:/agent_route",
                        kind="ros_topic",
                        endpoint="/agent_route",
                        evidence_origin="OBSERVED_RUNTIME",
                        source="artifact://private/agent-analysis.json",
                        observed_at=NOW,
                    )
                ],
            )
        ],
        created_at=NOW,
    )


def test_agent_candidate_does_not_promote_capability_readiness() -> None:
    definition = canonical_operation_registry().operations[0]
    summary = _summary(
        definition,
        builtins=set(),
        discovery=_heuristic_report(definition.operation),
        release_discovery_id=None,
        active=None,
        published_at=None,
        evidence_ids=["evidence-agent-only"],
    )

    assert summary.schema_version == "rolo-capability-summary/v2"
    assert summary.applicability == "NOT_OBSERVED"
    assert summary.availability == "UNAVAILABLE"
    assert summary.registration == "NOT_REGISTERED"
    assert summary.binding_count == 0
    assert summary.inferred_binding_count == 1
    assert summary.candidate_origin == "HEURISTIC_AGENT"
    assert summary.candidate_verification_status == "DISCOVERED_UNVERIFIED"
    assert summary.evidence_ids == []
    assert any("does not establish" in item for item in summary.limitations)


def test_agent_routes_are_returned_only_as_unverified_inferences(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    definition = canonical_operation_registry().operations[0]
    discovery = _heuristic_report(definition.operation)
    monkeypatch.setattr(
        "rolo.capability_read_models._context",
        lambda robot, artifact_root, output_root: (
            [definition],
            set(),
            discovery,
            None,
            None,
            {},
            {definition.operation: ["evidence-agent-only"]},
        ),
    )

    detail = get_capability_detail(
        ROBOT,
        tmp_path / "artifacts",
        tmp_path / "output",
        definition.operation,
        observed_at=NOW,
    )

    assert detail is not None
    assert detail.schema_version == "rolo-capability-detail/v2"
    assert detail.bindings == []
    assert len(detail.inferred_bindings) == 1
    inferred = detail.inferred_bindings[0]
    assert inferred.origin == "HEURISTIC_AGENT"
    assert inferred.verification_status == "DISCOVERED_UNVERIFIED"
    assert inferred.authority == "OBSERVED"
    assert "artifact://private" not in detail.model_dump_json()
