from __future__ import annotations

import os
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

import pytest

from rolo.core.artifacts import ArtifactStore
from rolo.core.models import (
    DiscoveryReport,
    DiscoveryStatus,
    OperationCandidate,
    ProbeResult,
    RouteEvidence,
)
from rolo.core.registry import RobotRegistry
from rolo.stages.adapt.active_discovery import (
    ActiveDiscoveryInputs,
    ActiveDiscoveryReport,
    ActiveProbeMode,
    Confidence,
    CoverageRecord,
    CoverageStatus,
    DiscoveryMode,
    DiscoveryModeLevel,
)
from rolo.stages.adapt.agent_contracts import (
    AgentArtifactProvenance,
    AgentBudgetUsage,
    AgentOperationProposal,
    AgentStopReason,
    OperationProposalBundle,
    ProposalConfidence,
)
from rolo.stages.adapt.discovery import DiscoveryService
from rolo.stages.adapt.heuristic_discovery import (
    CodexDiscoveryPlanningProvider,
    DiscoveryActionDisposition,
    DiscoveryPlanningContext,
    DiscoveryPlanningProvider,
    EvidenceGapCode,
    HeuristicAdaptMode,
    HeuristicDiscoveryOrchestrator,
    HeuristicDiscoveryStatus,
    WhitelistedR0ProbeDispatcher,
    build_planning_context,
    derive_evidence_gaps,
    validate_and_evaluate_plan,
)
from rolo.stages.adapt.operation_registry import adapter_operation_eligibility
from rolo.stages.adapt.proposal_orchestration import (
    DiscoverySkillRequest,
    OperationMappingProvider,
)
from rolo.stages.adapt.skill_contracts import (
    AdaptDiscoveryPlan,
    DiscoveryPlanAction,
)


class FixturePlanningProvider(DiscoveryPlanningProvider):
    provider = "fixture:rolo-adapt-discovery"

    def plan(self, context: DiscoveryPlanningContext) -> AdaptDiscoveryPlan:
        return AdaptDiscoveryPlan(
            robot_id=context.robot_id,
            discovery_id=context.discovery_id,
            target_fingerprint_sha256=context.target_fingerprint_sha256,
            actions=[
                DiscoveryPlanAction(
                    action_id="collect-runtime-graph",
                    kind="PROBE",
                    definition_id="probe.ros.runtime_graph",
                    expected_evidence_types=["ros.runtime_graph"],
                    rationale="Resolve the missing online target ROS graph evidence.",
                )
            ],
            unknowns=["The target ROS graph has not been observed."],
            stop_conditions=["Stop when the target runtime context is unavailable."],
            remaining_budget=context.remaining_budget,
            budget_usage=AgentBudgetUsage(
                rounds=1,
                input_tokens=120,
                output_tokens=40,
                elapsed_ms=20,
                result_bytes=500,
                stop_reason=AgentStopReason.BLOCKED,
            ),
            provenance=AgentArtifactProvenance(
                skill_name=context.skill_name,
                skill_version=context.skill_version,
                model_id="fixture-model",
                input_artifact_sha256=context.input_artifact_sha256,
            ),
        )


class SourceRefreshPlanningProvider(FixturePlanningProvider):
    def plan(self, context: DiscoveryPlanningContext) -> AdaptDiscoveryPlan:
        plan = super().plan(context)
        return plan.model_copy(
            update={
                "actions": [
                    DiscoveryPlanAction(
                        action_id="refresh-source-interfaces",
                        kind="QUERY",
                        definition_id="query.application.source_interfaces",
                        expected_evidence_types=["application.source_interfaces"],
                        rationale=(
                            "Refresh bounded source-interface evidence before semantic mapping."
                        ),
                    )
                ]
            }
        )


class FixtureMappingProvider(OperationMappingProvider):
    def __init__(
        self,
        factory: Callable[[DiscoverySkillRequest], OperationProposalBundle],
    ) -> None:
        self.factory = factory

    def propose(self, request: DiscoverySkillRequest) -> OperationProposalBundle:
        return self.factory(request)


def _route() -> RouteEvidence:
    return RouteEvidence(
        resource_id="ros_topic:/camera/image_raw",
        kind="ros_topic",
        endpoint="/camera/image_raw",
        interface_type="sensor_msgs/msg/Image",
        evidence_origin="DECLARED_STATIC",
        source="source:camera-node",
    )


def _report() -> DiscoveryReport:
    route = _route()
    return DiscoveryReport(
        discovery_id="disc-static",
        robot_id="wheeltec-static",
        status=DiscoveryStatus.PARTIAL,
        platform={"os": "developer-host"},
        capability_manifest={},
        probes={
            "ros": ProbeResult(
                layer="ros",
                status=DiscoveryStatus.UNAVAILABLE,
                data={"route_evidence": []},
            ),
            "application": ProbeResult(
                layer="application",
                status=DiscoveryStatus.SUCCEEDED,
                data={"projects": ["wheeltec_drivers"], "topics": ["/camera/image_raw"]},
            ),
        },
        operation_candidates=[
            OperationCandidate(
                operation="app.camera.snapshot",
                evidence=["source:camera-node"],
                route_evidence=[route],
                executable_ids=["exe-camera-declared"],
                limitations=["Static declaration has not been observed on the target."],
            )
        ],
        source_roots=["C:/fixtures/wheeltec_drivers"],
    )


def _active() -> ActiveDiscoveryReport:
    return ActiveDiscoveryReport(
        discovery_id="disc-static",
        robot_id="wheeltec-static",
        technical_status="PARTIAL",
        discovery_mode=DiscoveryMode(
            level=DiscoveryModeLevel.SOURCE_FIRST,
            confidence=Confidence.LOW,
            reason="Only static source was supplied.",
        ),
        inputs={
            "source_roots": ["C:/fixtures/wheeltec_drivers"],
            "build_roots": [],
            "install_roots": [],
            "executables": [],
            "active_probe": ActiveProbeMode.NONE.value,
        },
        coverage={
            "source": CoverageRecord(status=CoverageStatus.COMPLETE, records=10),
            "build": CoverageRecord(status=CoverageStatus.NOT_PROVIDED),
            "install": CoverageRecord(status=CoverageStatus.NOT_PROVIDED),
        },
        unknowns=["Target runtime and hardware identity are unavailable."],
        created_at=datetime.now(timezone.utc),
    )


def _bundle(request: DiscoverySkillRequest) -> OperationProposalBundle:
    return OperationProposalBundle(
        robot_id=request.robot_id,
        discovery_id=request.discovery_id,
        target_fingerprint_sha256=request.target_fingerprint_sha256,
        registry_version=request.registry_version,
        registry_sha256=request.registry_sha256,
        contract_catalog_sha256=request.contract_catalog_sha256,
        registry_operation_count=request.registry_operation_count,
        proposals=[
            AgentOperationProposal(
                operation="app.camera.snapshot",
                evidence_refs=["source:camera-node"],
                route_resource_ids=["ros_topic:/camera/image_raw"],
                executable_ids=["exe-camera-declared"],
                confidence=ProposalConfidence.LOW,
                rationale="Static camera route suggests the snapshot contract but is unverified.",
            )
        ],
        unknowns=["Target camera provider and runtime revision are unavailable."],
        budget_usage=AgentBudgetUsage(
            rounds=1,
            input_tokens=200,
            output_tokens=80,
            elapsed_ms=30,
            result_bytes=800,
            stop_reason=AgentStopReason.COMPLETED,
        ),
        provenance=AgentArtifactProvenance(
            skill_name=request.mapping_skill_name,
            skill_version=request.mapping_skill_version,
            model_id="fixture-model",
            input_artifact_sha256=request.input_artifact_sha256,
        ),
    )


def _dynamic_bundle(request: DiscoverySkillRequest) -> OperationProposalBundle:
    operation = next(
        operation
        for operation, binding in request.discovery_evidence.deterministic_bindings.items()
        if binding.evidence_refs
        and (binding.route_resource_ids or binding.executable_ids or binding.hardware_resource_ids)
    )
    binding = request.discovery_evidence.deterministic_bindings[operation]
    proposal = AgentOperationProposal(
        operation=operation,
        evidence_refs=[binding.evidence_refs[0]],
        route_resource_ids=binding.route_resource_ids[:1],
        executable_ids=binding.executable_ids[:1],
        hardware_resource_ids=binding.hardware_resource_ids[:1],
        confidence=ProposalConfidence.LOW,
        rationale="Frozen static evidence suggests this mapping but target evidence is missing.",
    )
    base = _bundle(request)
    return base.model_copy(
        update={
            "proposals": [proposal],
            "unknowns": ["Target runtime evidence is unavailable for the static mapping."],
        }
    )


def test_static_source_gaps_do_not_treat_developer_host_as_target() -> None:
    gaps = derive_evidence_gaps(_report(), _active())
    codes = {gap.code for gap in gaps}

    assert EvidenceGapCode.TARGET_HARDWARE_INVENTORY in codes
    assert EvidenceGapCode.ROS_RUNTIME_GRAPH in codes
    assert EvidenceGapCode.BUILD_ARTIFACTS in codes
    assert EvidenceGapCode.INSTALL_ARTIFACTS in codes
    assert EvidenceGapCode.TARGET_EXECUTABLE in codes
    assert all("RELEASE" in gap.blocks for gap in gaps)


def test_non_ros_cli_source_does_not_request_a_ros_runtime_graph() -> None:
    report = _report().model_copy(
        update={
            "operation_candidates": [
                OperationCandidate(
                    operation="app.runtime.info",
                    route_evidence=[
                        RouteEvidence(
                            resource_id="cli:lerobot-info",
                            kind="cli",
                            endpoint="lerobot-info",
                            evidence_origin="DECLARED_STATIC",
                            source="pyproject:lerobot-info",
                        )
                    ],
                )
            ]
        }
    )

    gaps = derive_evidence_gaps(report, _active())
    codes = {gap.code for gap in gaps}

    assert EvidenceGapCode.ROS_RUNTIME_GRAPH not in codes
    provider = next(gap for gap in gaps if gap.code == EvidenceGapCode.ROUTE_PROVIDER_IDENTITY)
    schema = next(gap for gap in gaps if gap.code == EvidenceGapCode.INTERFACE_SCHEMA)
    assert provider.collection_context == "TARGET_HOST"
    assert schema.collection_context == "TARGET_HOST"


def test_shadow_orchestrator_persists_agent_output_and_missing_evidence(
    tmp_path: Path,
) -> None:
    orchestrator = HeuristicDiscoveryOrchestrator(
        ArtifactStore(tmp_path),
        mode=HeuristicAdaptMode.SHADOW,
        planning_provider=FixturePlanningProvider(),
        mapping_provider=FixtureMappingProvider(_bundle),
        max_actions=4,
        max_operations=10,
    )

    summary, candidates = orchestrator.run(
        _report(),
        _active(),
        relative_root="discovery/wheeltec-static/runs/disc-static",
    )

    assert summary.status == HeuristicDiscoveryStatus.AGENT_COMPLETED
    assert summary.inferred_operations == ["app.camera.snapshot"]
    assert summary.applied_operations == []
    assert summary.influences_release is False
    assert {gap.code for gap in summary.missing_evidence} >= {
        EvidenceGapCode.ROS_RUNTIME_GRAPH,
        EvidenceGapCode.AGENT_REPORTED_UNKNOWN,
    }
    assert candidates == _report().operation_candidates
    assert summary.action_outcomes[0].disposition.value == ("BLOCKED_MISSING_TARGET_CONTEXT")
    summary_path = tmp_path / "discovery/wheeltec-static/runs/disc-static/heuristic/summary.json"
    assert summary_path.is_file()
    assert (summary_path.parent / "operation-proposal-bundle.json").is_file()
    assert (summary_path.parent / "operation-proposal-validation.json").is_file()


def test_mapping_fallback_does_not_report_agent_completed(tmp_path: Path) -> None:
    class InvalidMappingProvider(FixtureMappingProvider):
        def __init__(self) -> None:
            super().__init__(lambda request: _bundle(request).model_copy(
                update={"registry_sha256": "0" * 64}
            ))

    orchestrator = HeuristicDiscoveryOrchestrator(
        ArtifactStore(tmp_path),
        mode=HeuristicAdaptMode.SHADOW,
        planning_provider=FixturePlanningProvider(),
        mapping_provider=InvalidMappingProvider(),
        max_probe_rounds=0,
    )

    summary, _ = orchestrator.run(
        _report(),
        _active(),
        relative_root="discovery/wheeltec-static/runs/disc-invalid-mapping",
    )

    assert summary.status == HeuristicDiscoveryStatus.FALLBACK
    assert summary.mapping_fallback_reason.startswith("BUNDLE_INVALID:")
    assert "Registry identity" in summary.mapping_fallback_reason


def test_heuristic_candidate_can_never_be_adapter_eligible_without_verification() -> None:
    report = _report()
    heuristic = report.operation_candidates[0].model_copy(update={"origin": "HEURISTIC_AGENT"})
    report = report.model_copy(update={"operation_candidates": [heuristic]})

    eligible, deferred = adapter_operation_eligibility(report)

    assert not eligible
    assert deferred == {"app.camera.snapshot": "HEURISTIC_MAPPING_REQUIRES_VERIFICATION"}


def test_discovery_plan_rejects_stale_provenance() -> None:
    report = _report()
    active = _active()
    orchestrator = HeuristicDiscoveryOrchestrator(
        ArtifactStore(Path("unused")),
        mode=HeuristicAdaptMode.SHADOW,
        planning_provider=None,
        mapping_provider=None,
    )
    fingerprint = "a" * 64
    from rolo.stages.adapt.heuristic_discovery import build_planning_context

    context = build_planning_context(
        report,
        active,
        target_fingerprint=fingerprint,
        gaps=derive_evidence_gaps(report, active),
        max_actions=orchestrator.max_actions,
    )
    plan = FixturePlanningProvider().plan(context)
    stale = plan.model_copy(
        update={
            "provenance": plan.provenance.model_copy(
                update={"input_artifact_sha256": {"discovery": "b" * 64}}
            )
        }
    )

    try:
        validate_and_evaluate_plan(stale, context)
    except ValueError as exc:
        assert "frozen inputs" in str(exc)
    else:
        raise AssertionError("stale provenance was accepted")


def test_plan_rejects_agent_parameters_before_read_only_dispatch() -> None:
    report = _report()
    active = _active()
    from rolo.stages.adapt.heuristic_discovery import build_planning_context

    context = build_planning_context(
        report,
        active,
        target_fingerprint="a" * 64,
        gaps=derive_evidence_gaps(report, active),
        max_actions=4,
    )
    plan = FixturePlanningProvider().plan(context)
    unsafe_action = plan.actions[0].model_copy(
        update={"parameters": {"command": "ros2 topic pub /cmd_vel"}}
    )
    plan = plan.model_copy(update={"actions": [unsafe_action]})

    outcomes = validate_and_evaluate_plan(plan, context)

    assert outcomes[0].disposition == DiscoveryActionDisposition.REJECTED_INVALID_PARAMETERS


def test_probe_loop_freezes_evidence_rehashes_and_replans_once(tmp_path: Path) -> None:
    report = _report()
    report.probes["ros"] = ProbeResult(
        layer="ros",
        status=DiscoveryStatus.SUCCEEDED,
        data={"route_evidence": []},
    )
    active = _active().model_copy(deep=True)
    active.inputs["active_probe"] = ActiveProbeMode.RUNTIME_READONLY.value
    contexts: list[DiscoveryPlanningContext] = []

    class RecordingProvider(FixturePlanningProvider):
        def plan(self, context: DiscoveryPlanningContext) -> AdaptDiscoveryPlan:
            contexts.append(context)
            return super().plan(context)

    def observe_runtime(
        current_report: DiscoveryReport,
        current_active: ActiveDiscoveryReport,
    ) -> tuple[DiscoveryReport, ActiveDiscoveryReport]:
        updated = current_report.model_copy(deep=True)
        route = RouteEvidence(
            resource_id="ros_topic:/camera/image_raw",
            kind="ros_topic",
            endpoint="/camera/image_raw",
            interface_type="sensor_msgs/msg/Image",
            interface_schema_sha256="d" * 64,
            provider_id="ros-node:camera",
            runtime_revision="pkg:camera-driver@1.0.0",
            observed_at=datetime.now(timezone.utc),
            evidence_origin="OBSERVED_RUNTIME",
            source="runtime_probe:ros",
        )
        updated.probes["ros"] = ProbeResult(
            layer="ros",
            status=DiscoveryStatus.SUCCEEDED,
            data={
                "nodes": ["/camera"],
                "topics": ["/camera/image_raw"],
                "route_evidence": [route.model_dump(mode="json")],
            },
        )
        return updated, current_active

    dispatcher = WhitelistedR0ProbeDispatcher(
        {"probe.ros.runtime_graph": observe_runtime}
    )
    orchestrator = HeuristicDiscoveryOrchestrator(
        ArtifactStore(tmp_path),
        mode=HeuristicAdaptMode.SHADOW,
        planning_provider=RecordingProvider(),
        mapping_provider=FixtureMappingProvider(_dynamic_bundle),
        max_actions=4,
        max_operations=10,
        max_probe_rounds=1,
    )

    summary, _ = orchestrator.run(
        report,
        active,
        relative_root="discovery/wheeltec-static/runs/disc-static",
        probe_dispatcher=dispatcher,
    )

    assert len(contexts) == 2
    assert contexts[0].input_artifact_sha256 != contexts[1].input_artifact_sha256
    assert contexts[1].remaining_budget.rounds == 0
    assert report.probes["ros"].data["nodes"] == ["/camera"]
    assert [outcome.disposition for outcome in summary.action_outcomes] == [
        DiscoveryActionDisposition.EXECUTED_READ_ONLY,
        DiscoveryActionDisposition.SATISFIED_BY_FROZEN_EVIDENCE,
    ]
    frozen = (
        tmp_path
        / "discovery/wheeltec-static/runs/disc-static/heuristic"
        / "probe-loop/round-1/frozen-evidence"
    )
    assert (frozen / "discovery.json").is_file()
    assert (frozen / "active-discovery.json").is_file()
    assert (frozen / "target-fingerprint.json").is_file()


def test_probe_failure_remains_an_explicit_evidence_gap(tmp_path: Path) -> None:
    report = _report()
    report.probes["ros"] = ProbeResult(
        layer="ros", status=DiscoveryStatus.SUCCEEDED, data={"route_evidence": []}
    )
    active = _active().model_copy(deep=True)
    active.inputs["active_probe"] = ActiveProbeMode.RUNTIME_READONLY.value

    def fail_probe(
        current_report: DiscoveryReport,
        current_active: ActiveDiscoveryReport,
    ) -> tuple[DiscoveryReport, ActiveDiscoveryReport]:
        raise RuntimeError("target ROS daemon unavailable")

    summary, _ = HeuristicDiscoveryOrchestrator(
        ArtifactStore(tmp_path),
        mode=HeuristicAdaptMode.SHADOW,
        planning_provider=FixturePlanningProvider(),
        mapping_provider=None,
        max_probe_rounds=1,
    ).run(
        report,
        active,
        relative_root="discovery/wheeltec-static/runs/disc-static",
        probe_dispatcher=WhitelistedR0ProbeDispatcher(
            {"probe.ros.runtime_graph": fail_probe}
        ),
    )

    assert summary.action_outcomes[0].disposition == (
        DiscoveryActionDisposition.FAILED_READ_ONLY_PROBE
    )
    assert any(
        gap.subject_ref == "probe:probe.ros.runtime_graph"
        for gap in summary.missing_evidence
    )


def test_codex_planning_provider_is_exposed_as_the_real_agent_boundary(
    monkeypatch,
    tmp_path: Path,
) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    monkeypatch.delenv("HOME", raising=False)
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.delenv("HTTPS_PROXY", raising=False)
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("https_proxy", "http://proxy.example:7897")
    assert CodexDiscoveryPlanningProvider.provider.endswith("rolo-adapt-discovery")
    provider = CodexDiscoveryPlanningProvider(
        skill_path=Path("skill.md"), preflight_enabled=False
    )
    command = provider._command(Path("workspace"), Path("schema.json"), Path("output.json"))
    assert "--skip-git-repo-check" in command
    assert command[command.index("--sandbox") + 1] == "read-only"
    assert 'model_reasoning_effort="low"' in command
    assert provider._environment()["HOME"] == str(tmp_path)
    assert provider._environment()["CODEX_HOME"] == str(codex_home)
    assert provider._environment()["HTTPS_PROXY"] == "http://proxy.example:7897"


@pytest.mark.skipif(os.name == "nt", reason="POSIX process-group regression")
def test_codex_planning_timeout_reaps_descendants(tmp_path: Path) -> None:
    skill = tmp_path / "discovery-SKILL.md"
    skill.write_text("Read frozen evidence only.", encoding="utf-8")
    descendant_marker = tmp_path / "planning-descendant-survived"
    executable = tmp_path / "blocking-planning-agent"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        "import subprocess, sys, time\n"
        "subprocess.Popen([sys.executable, '-c', "
        + repr(
            "import pathlib, time; time.sleep(1.5); "
            f"pathlib.Path({str(descendant_marker)!r}).write_text('alive')"
        )
        + "])\n"
        "time.sleep(30)\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    report = _report()
    active = _active()
    context = build_planning_context(
        report,
        active,
        target_fingerprint="a" * 64,
        gaps=derive_evidence_gaps(report, active),
        max_actions=4,
    )
    provider = CodexDiscoveryPlanningProvider(
        skill_path=skill,
        executable=str(executable),
        timeout_s=1,
        preflight_enabled=False,
    )

    started = time.monotonic()
    with pytest.raises(TimeoutError, match="planning Agent timed out"):
        provider.plan(context)

    assert time.monotonic() - started < 2.0
    time.sleep(0.7)
    assert not descendant_marker.exists()


def test_discovery_service_wires_heuristic_artifacts_into_report_wiki_and_plan_inputs(
    tmp_path: Path,
) -> None:
    project = tmp_path / "source-only"
    project.mkdir()
    (project / "camera_node.py").write_text(
        "node.create_publisher(Image, '/camera/image_raw', 10)\n",
        encoding="utf-8",
    )
    (project / "README.md").write_text(
        "Static camera driver source; target runtime is not included.\n",
        encoding="utf-8",
    )
    artifacts = ArtifactStore(tmp_path / "artifacts")
    orchestrator = HeuristicDiscoveryOrchestrator(
        artifacts,
        mode=HeuristicAdaptMode.SHADOW,
        planning_provider=SourceRefreshPlanningProvider(),
        mapping_provider=FixtureMappingProvider(_dynamic_bundle),
        max_operations=20,
    )
    registry = RobotRegistry(Path("tests/fixtures/robots"))
    registry.load()

    report, run_path = DiscoveryService(
        artifacts,
        heuristic_orchestrator=orchestrator,
    ).run(
        robot=registry.get("demo_diff"),
        active_inputs=ActiveDiscoveryInputs(
            source_roots=[project],
            active_probe=ActiveProbeMode.NONE,
        ),
    )

    assert report.heuristic_status == "AGENT_COMPLETED"
    assert report.heuristic_mode == "shadow"
    assert report.heuristic_inferred_operation_count >= 1
    assert report.heuristic_missing_evidence_count >= 4
    assert report.heuristic_analysis_ref.endswith("/heuristic/summary.json")
    assert (run_path.parent / "heuristic/summary.json").is_file()
    summary = (run_path.parent / "heuristic/summary.json").read_text(encoding="utf-8")
    assert '"disposition": "EXECUTED_READ_ONLY"' in summary
    assert (
        run_path.parent
        / "heuristic/probe-loop/round-1/frozen-evidence/target-fingerprint.json"
    ).is_file()
    assert "Heuristic Adapt analysis" in (run_path.parent / "robot_wiki.md").read_text(
        encoding="utf-8"
    )
    adapt_inputs = (tmp_path / "artifacts/adapt/demo_diff/latest/inputs.json").read_text(
        encoding="utf-8"
    )
    assert report.heuristic_analysis_ref in adapt_inputs
