from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import ValidationError

from rolo.core.artifacts import ArtifactStore
from rolo.core.models import (
    DiscoveryReport,
    DiscoveryStatus,
    OperationCandidate,
    ProbeResult,
    RouteEvidence,
)
from rolo.stages.adapt.agent_contracts import (
    AgentArtifactProvenance,
    AgentBudgetUsage,
    AgentDisposition,
    AgentEvidenceToolReceipt,
    AgentOperationProposal,
    AgentRouteDisposition,
    AgentStopReason,
    OperationProposalBundle,
    ProposalConfidence,
)
from rolo.stages.adapt.mapping_evidence_tool import evaluate as evaluate_mapping_evidence
from rolo.stages.adapt.operation_registry import canonical_operation_registry
from rolo.stages.adapt.proposal_orchestration import (
    CodexOperationMappingProvider,
    DiscoverySkillRequest,
    DiscoverySkillRunner,
    OperationMappingProvider,
    ProposalArtifactSource,
    ProposalFallbackReason,
    ProposalIssueCode,
    RegistrySnapshot,
    _codex_event_usage,
    _evidence_aliases,
    _mapping_output_schema,
    _resolve_provider_evidence_aliases,
    apply_validated_semantic_dispositions,
    build_discovery_skill_request,
    persist_proposal_artifacts,
)

TARGET_FINGERPRINT = "a" * 64


class FixtureProvider(OperationMappingProvider):
    def __init__(
        self,
        factory: Callable[[DiscoverySkillRequest], OperationProposalBundle],
    ) -> None:
        self.factory = factory

    def propose(self, request: DiscoverySkillRequest) -> OperationProposalBundle:
        return self.factory(request)


def test_codex_mapping_provider_is_read_only_bounded_and_schema_driven(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    discovery_skill = tmp_path / "discovery-SKILL.md"
    mapping_skill = tmp_path / "mapping-SKILL.md"
    discovery_skill.write_text("Discover from frozen evidence only.", encoding="utf-8")
    mapping_skill.write_text("Map only canonical target Operations.", encoding="utf-8")
    _report_value, _registry, request = _request()
    expected = _bundle(request, [_proposal()])
    captured: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        captured["input"] = kwargs["input"]
        captured["environment"] = kwargs["env"]
        schema = Path(command[command.index("--output-schema") + 1])
        captured["schema"] = json.loads(schema.read_text(encoding="utf-8"))
        output = Path(command[command.index("--output-last-message") + 1])
        payload = expected.model_dump(mode="json")
        proposal_variant = captured["schema"]["properties"]["proposals"]["items"][
            "anyOf"
        ][0]
        evidence_alias = proposal_variant["properties"]["evidence_refs"]["items"][
            "enum"
        ][0]
        payload["proposals"][0]["evidence_refs"] = [evidence_alias, evidence_alias]
        payload["proposals"][0]["counter_evidence_refs"] = [evidence_alias]
        output.write_text(json.dumps(payload), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(
        "rolo.stages.adapt.proposal_orchestration.shutil.which",
        lambda _value: "codex",
    )
    monkeypatch.setattr(
        "rolo.stages.adapt.proposal_orchestration.subprocess.run",
        fake_run,
    )
    monkeypatch.setenv("ALL_PROXY", "http://proxy.example:7897")
    provider = CodexOperationMappingProvider(
        discovery_skill_path=discovery_skill,
        mapping_skill_path=mapping_skill,
        model="fixture-model",
        api_key="fixture-secret",
    )

    actual = provider.propose(request)

    assert actual == expected
    command = captured["command"]
    assert isinstance(command, list)
    assert "--skip-git-repo-check" in command
    assert command[command.index("--sandbox") + 1] == "read-only"
    assert "fixture-secret" not in json.dumps(command)
    assert "UNTRUSTED FROZEN DISCOVERY REQUEST" in str(captured["input"])
    schema = captured["schema"]
    assert isinstance(schema, dict)
    proposal_schema = schema["properties"]["proposals"]["items"]["anyOf"][0]
    assert proposal_schema["properties"]["operation"]["enum"] == [
        "app.camera.snapshot"
    ]
    evidence_enums = proposal_schema["properties"]["evidence_refs"]["items"]["enum"]
    assert len(evidence_enums) == 1
    assert evidence_enums[0].startswith("ev:")
    assert "runtime_probe:camera" not in evidence_enums
    assert proposal_schema["properties"]["route_resource_ids"]["items"]["enum"] == [
        "ros_topic:/camera/image_raw"
    ]
    assert proposal_schema["properties"]["executable_ids"]["items"]["enum"] == [
        "exe-camera"
    ]
    assert proposal_schema["properties"]["hardware_resource_ids"]["maxItems"] == 0
    prompt = str(captured["input"])
    assert '"evidence_catalog"' in prompt
    assert f'"{evidence_enums[0]}":"runtime_probe:camera"' in prompt
    environment = captured["environment"]
    assert isinstance(environment, dict)
    assert environment["CODEX_API_KEY"] == "fixture-secret"
    assert environment["ALL_PROXY"] == "http://proxy.example:7897"


def test_mapping_schema_binds_each_operation_to_its_own_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    discovery_skill = tmp_path / "discovery-SKILL.md"
    mapping_skill = tmp_path / "mapping-SKILL.md"
    discovery_skill.write_text("Discover from frozen evidence only.", encoding="utf-8")
    mapping_skill.write_text("Map only canonical target Operations.", encoding="utf-8")
    _report_value, _registry, request = _request(
        targets=("app.camera.snapshot", "app.localization.status")
    )
    captured: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        schema = Path(command[command.index("--output-schema") + 1])
        captured["schema"] = json.loads(schema.read_text(encoding="utf-8"))
        output = Path(command[command.index("--output-last-message") + 1])
        output.write_text(
            json.dumps(_bundle(request, []).model_dump(mode="json")),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(
        "rolo.stages.adapt.proposal_orchestration.shutil.which", lambda _value: "codex"
    )
    monkeypatch.setattr(
        "rolo.stages.adapt.proposal_orchestration.subprocess.run", fake_run
    )
    provider = CodexOperationMappingProvider(
        discovery_skill_path=discovery_skill,
        mapping_skill_path=mapping_skill,
    )

    provider.propose(request)

    schema = captured["schema"]
    assert isinstance(schema, dict)
    variants = schema["properties"]["proposals"]["items"]["anyOf"]
    by_operation = {
        variant["properties"]["operation"]["enum"][0]: variant for variant in variants
    }
    assert by_operation["app.camera.snapshot"]["properties"]["route_resource_ids"][
        "items"
    ]["enum"] == ["ros_topic:/camera/image_raw"]
    assert by_operation["app.localization.status"]["properties"]["route_resource_ids"][
        "items"
    ]["enum"] == ["ros_topic:/odom"]
    assert by_operation["app.camera.snapshot"]["properties"]["counter_evidence_refs"][
        "maxItems"
    ] == 0


def test_codex_event_usage_reads_largest_cumulative_jsonl_record() -> None:
    stdout = "\n".join(
        [
            "not-json",
            json.dumps({"usage": {"input_tokens": 120, "output_tokens": 30}}),
            json.dumps(
                {
                    "type": "turn.completed",
                    "usage": {"input_tokens": 900, "output_tokens": 125},
                }
            ),
            json.dumps({"input_tokens": True, "output_tokens": 4}),
        ]
    )

    assert _codex_event_usage(stdout) == (900, 125)


def test_mapping_schema_excludes_context_contracts_without_deterministic_bindings() -> None:
    _report_value, _registry, request = _request(
        targets=("app.camera.snapshot", "app.camera.status")
    )

    aliases = _evidence_aliases(request)
    schema = _mapping_output_schema(request, aliases)
    operations = [
        variant["properties"]["operation"]["enum"][0]
        for variant in schema["properties"]["proposals"]["items"]["anyOf"]
    ]

    assert operations == ["app.camera.snapshot"]
    assert {item.operation for item in request.target_contracts} == {
        "app.camera.snapshot",
        "app.camera.status",
    }


def test_windows_source_reference_round_trips_through_short_evidence_id() -> None:
    report, registry, _request_value = _request()
    source_ref = (
        "source:C:\\Users\\zarch\\Desktop\\adapt-validation-data\\"
        "wheeltec_drivers\\usb_cam_launcher"
    )
    camera = report.operation_candidates[0]
    route = camera.route_evidence[0].model_copy(update={"source": source_ref})
    report = report.model_copy(
        update={
            "operation_candidates": [
                camera.model_copy(
                    update={"evidence": [source_ref], "route_evidence": [route]}
                ),
                report.operation_candidates[1],
            ]
        }
    )
    request = build_discovery_skill_request(
        report,
        registry,
        target_operations={"app.camera.snapshot"},
        target_fingerprint_sha256=TARGET_FINGERPRINT,
    )

    aliases = _evidence_aliases(request)
    schema = _mapping_output_schema(request, aliases)
    evidence_id = aliases[source_ref]
    payload = _bundle(request, [_proposal(evidence_ref=source_ref)]).model_dump(mode="json")
    payload["proposals"][0]["evidence_refs"] = [evidence_id]

    resolved = _resolve_provider_evidence_aliases(payload, aliases)

    assert evidence_id.startswith("ev:")
    assert len(evidence_id) == 27
    assert schema["properties"]["proposals"]["items"]["anyOf"][0]["properties"][
        "evidence_refs"
    ]["items"]["enum"] == [evidence_id]
    assert resolved["proposals"][0]["evidence_refs"] == [source_ref]


def _route(endpoint: str, source: str) -> RouteEvidence:
    return RouteEvidence(
        resource_id=f"ros_topic:{endpoint}",
        kind="ros_topic",
        endpoint=endpoint,
        interface_type="sensor_msgs/msg/Image" if "camera" in endpoint else None,
        evidence_origin="OBSERVED_RUNTIME",
        source=source,
    )


def _report() -> DiscoveryReport:
    camera = _route("/camera/image_raw", "runtime_probe:camera")
    odom = _route("/odom", "runtime_probe:odom")
    return DiscoveryReport(
        discovery_id="discovery-fixture",
        robot_id="robot-fixture",
        status=DiscoveryStatus.SUCCEEDED,
        platform={"os": "linux"},
        capability_manifest={},
        probes={
            "ros": ProbeResult(
                layer="ros",
                status=DiscoveryStatus.SUCCEEDED,
                data={
                    "route_evidence": [
                        camera.model_dump(mode="json"),
                        odom.model_dump(mode="json"),
                    ]
                },
            )
        },
        operation_candidates=[
            OperationCandidate(
                operation="app.camera.snapshot",
                evidence=["runtime_probe:camera"],
                route_evidence=[camera],
                executable_ids=["exe-camera"],
            ),
            OperationCandidate(
                operation="app.localization.status",
                evidence=["runtime_probe:odom"],
                route_evidence=[odom],
                executable_ids=["exe-localization"],
            ),
        ],
    )


def _request(
    *,
    targets: tuple[str, ...] = ("app.camera.snapshot",),
) -> tuple[DiscoveryReport, RegistrySnapshot, DiscoverySkillRequest]:
    report = _report()
    registry = RegistrySnapshot(canonical_operation_registry(), registry_version="294-fixture")
    request = build_discovery_skill_request(
        report,
        registry,
        target_operations=targets,
        target_fingerprint_sha256=TARGET_FINGERPRINT,
    )
    return report, registry, request


def _proposal(
    operation: str = "app.camera.snapshot",
    *,
    evidence_ref: str = "runtime_probe:camera",
    route_resource_id: str = "ros_topic:/camera/image_raw",
    executable_id: str = "exe-camera",
) -> AgentOperationProposal:
    return AgentOperationProposal(
        operation=operation,
        evidence_refs=[evidence_ref],
        route_resource_ids=[route_resource_id],
        executable_ids=[executable_id],
        confidence=ProposalConfidence.MEDIUM,
        rationale="Observed route and executable match the requested contract.",
    )


def _bundle(
    request: DiscoverySkillRequest,
    proposals: list[AgentOperationProposal],
    *,
    registry_sha256: str | None = None,
    skill_name: str | None = None,
    skill_version: str | None = None,
) -> OperationProposalBundle:
    return OperationProposalBundle(
        robot_id=request.robot_id,
        discovery_id=request.discovery_id,
        target_fingerprint_sha256=request.target_fingerprint_sha256,
        registry_version=request.registry_version,
        registry_sha256=registry_sha256 or request.registry_sha256,
        contract_catalog_sha256=request.contract_catalog_sha256,
        registry_operation_count=request.registry_operation_count,
        proposals=proposals,
        budget_usage=AgentBudgetUsage(
            rounds=2,
            input_tokens=120,
            output_tokens=45,
            elapsed_ms=18,
            result_bytes=512,
            stop_reason=AgentStopReason.COMPLETED,
        ),
        provenance=AgentArtifactProvenance(
            skill_name=skill_name or request.mapping_skill_name,
            skill_version=skill_version or request.mapping_skill_version,
            model_id="fixture-model",
            input_artifact_sha256=request.input_artifact_sha256,
        ),
    )


def test_codex_mapping_provider_batches_operations_and_aggregates_usage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    discovery_skill = tmp_path / "discovery-SKILL.md"
    mapping_skill = tmp_path / "mapping-SKILL.md"
    discovery_skill.write_text("Read frozen evidence only.", encoding="utf-8")
    mapping_skill.write_text("Return bounded mappings only.", encoding="utf-8")
    _report_value, _registry, request = _request(
        targets=("app.camera.snapshot", "app.localization.status")
    )
    seen: list[str] = []

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        workspace = Path(command[command.index("--cd") + 1])
        child = DiscoverySkillRequest.model_validate_json(
            (workspace / "frozen-request.json").read_text(encoding="utf-8")
        )
        operation = sorted(child.target_operations)[0]
        seen.append(operation)
        proposal = (
            _proposal()
            if operation == "app.camera.snapshot"
            else _proposal(
                operation,
                evidence_ref="runtime_probe:odom",
                route_resource_id="ros_topic:/odom",
                executable_id="exe-localization",
            )
        )
        output = Path(command[command.index("--output-last-message") + 1])
        output.write_text(
            _bundle(child, [proposal]).model_dump_json(),
            encoding="utf-8",
        )
        stdout = json.dumps(
            {
                "type": "turn.completed",
                "usage": {"input_tokens": 1_000, "output_tokens": 100},
            }
        )
        return subprocess.CompletedProcess(command, 0, stdout, "")

    monkeypatch.setattr(
        "rolo.stages.adapt.proposal_orchestration.shutil.which", lambda _value: "codex"
    )
    monkeypatch.setattr(
        "rolo.stages.adapt.proposal_orchestration.subprocess.run", fake_run
    )
    provider = CodexOperationMappingProvider(
        discovery_skill_path=discovery_skill,
        mapping_skill_path=mapping_skill,
        batch_operations=1,
        parallelism=1,
    )

    actual = provider.propose(request)

    assert seen == ["app.camera.snapshot", "app.localization.status"]
    assert [item.operation for item in actual.proposals] == seen
    assert actual.budget_usage.input_tokens == 2_000
    assert actual.budget_usage.output_tokens == 200
    assert actual.provenance.input_artifact_sha256 == request.input_artifact_sha256


def test_registry_snapshot_and_request_use_full_294_registry_with_bounded_slice() -> None:
    _report_value, registry, request = _request()

    assert registry.operation_count == 294
    assert request.registry_operation_count == 294
    assert [item.operation for item in request.target_contracts] == [
        "app.camera.snapshot"
    ]
    assert request.target_contracts[0].input_schema
    assert request.input_artifact_sha256["registry"] == registry.registry_sha256
    assert request.mapping_skill_name == "rolo-operation-mapping"
    assert request.mapping_skill_version == "1.1.0"
    assert request.discovery_evidence.deterministic_bindings[
        "app.camera.snapshot"
    ].evidence_refs == ["runtime_probe:camera"]


def test_explicit_trusted_mapping_skill_version_is_accepted() -> None:
    report = _report()
    registry = RegistrySnapshot(canonical_operation_registry())
    request = build_discovery_skill_request(
        report,
        registry,
        target_operations={"app.camera.snapshot"},
        target_fingerprint_sha256=TARGET_FINGERPRINT,
        mapping_skill_version="2.3.0",
    )
    runner = DiscoverySkillRunner(
        registry,
        FixtureProvider(lambda value: _bundle(value, [_proposal()])),
    )

    _bundle_value, artifact = runner.run(
        request,
        deterministic_candidates=report.operation_candidates,
    )

    assert request.mapping_skill_version == "2.3.0"
    assert artifact.source == ProposalArtifactSource.AGENT


def test_request_prefers_observed_route_when_candidate_has_same_declared_resource() -> None:
    report = _report()
    declared = report.operation_candidates[0].route_evidence[0].model_copy(
        update={
            "evidence_origin": "DECLARED_STATIC",
            "source": "launch:camera",
            "interface_type": None,
        }
    )
    report = report.model_copy(
        update={
            "operation_candidates": [
                report.operation_candidates[0].model_copy(
                    update={"route_evidence": [declared]}
                ),
                report.operation_candidates[1],
            ]
        }
    )
    registry = RegistrySnapshot(canonical_operation_registry())

    request = build_discovery_skill_request(
        report,
        registry,
        target_operations={"app.camera.snapshot"},
        target_fingerprint_sha256=TARGET_FINGERPRINT,
    )

    selected = request.discovery_evidence.route_resources[
        "ros_topic:/camera/image_raw"
    ]
    assert selected.observed is True
    assert selected.interface_type == "sensor_msgs/msg/Image"
    assert "launch:camera" in request.discovery_evidence.evidence_refs


def test_runner_accepts_valid_proposal_as_discovered_unverified_and_persists_artifacts(
    tmp_path: Path,
) -> None:
    report, registry, request = _request()
    runner = DiscoverySkillRunner(
        registry,
        FixtureProvider(lambda value: _bundle(value, [_proposal()])),
    )

    bundle, artifact = runner.run(
        request,
        deterministic_candidates=report.operation_candidates,
    )

    assert bundle is not None
    assert artifact.source == ProposalArtifactSource.AGENT
    assert artifact.operation_candidates[0].status == "DISCOVERED_UNVERIFIED"
    assert artifact.operation_candidates[0].operation == "app.camera.snapshot"
    assert artifact.influences_release is False
    assert artifact.metrics.valid_proposal_rate == 1.0
    assert artifact.metrics.input_tokens == 120
    refs = persist_proposal_artifacts(
        ArtifactStore(tmp_path),
        "adapt/robot-fixture/proposals/run-1",
        bundle=bundle,
        validation=artifact,
    )
    assert set(refs) == {"bundle", "validation"}
    assert Path(refs["bundle"]).is_file()
    assert Path(refs["validation"]).is_file()


def test_semantic_accept_requires_and_validates_read_only_tool_receipt() -> None:
    report, registry, _request_value = _request()
    candidate = report.operation_candidates[0].model_copy(
        update={"semantic_review_required": True}
    )
    report = report.model_copy(update={"operation_candidates": [candidate]})
    request = build_discovery_skill_request(
        report,
        registry,
        target_operations={candidate.operation},
        target_fingerprint_sha256=TARGET_FINGERPRINT,
    )
    receipt = AgentEvidenceToolReceipt.model_validate(
        evaluate_mapping_evidence(
            request.model_dump(mode="json"),
            operation=candidate.operation,
            route_resource_id=candidate.route_evidence[0].resource_id,
            condition="BINDING_MATCH",
        )
    )
    proposal = _proposal().model_copy(
        update={
            "disposition": AgentDisposition.ACCEPT,
            "route_dispositions": [
                AgentRouteDisposition(
                    route_resource_id=candidate.route_evidence[0].resource_id,
                    disposition=AgentDisposition.ACCEPT,
                    rationale="The frozen route is bound to this exact candidate.",
                    tool_receipt_ids=[receipt.receipt_id],
                )
            ],
            "tool_receipts": [receipt],
        }
    )
    _bundle_value, artifact = DiscoverySkillRunner(
        registry,
        FixtureProvider(lambda value: _bundle(value, [proposal])),
    ).run(request, deterministic_candidates=report.operation_candidates)

    reviewed, applied = apply_validated_semantic_dispositions(
        report.operation_candidates,
        artifact,
    )

    assert artifact.source == ProposalArtifactSource.AGENT
    assert artifact.validated_dispositions[0].disposition == AgentDisposition.ACCEPT
    assert applied == [candidate.operation]
    assert reviewed[0].semantic_review_disposition == "ACCEPT"
    assert reviewed[0].route_review_dispositions == {
        candidate.route_evidence[0].resource_id: "ACCEPT"
    }


def test_semantic_any_of_accept_slices_rejected_routes_from_candidate() -> None:
    report, registry, _request_value = _request()
    camera = report.operation_candidates[0]
    odom = report.operation_candidates[1].route_evidence[0]
    candidate = camera.model_copy(
        update={
            "evidence": ["runtime_probe:camera", "runtime_probe:odom"],
            "route_evidence": [camera.route_evidence[0], odom],
            "route_binding_mode": "ANY_OF",
            "semantic_review_required": True,
            "limitations": [
                "Heuristic mapping is ambiguous; explicit operation evidence is required"
            ],
        }
    )
    report = report.model_copy(update={"operation_candidates": [candidate]})
    request = build_discovery_skill_request(
        report,
        registry,
        target_operations={candidate.operation},
        target_fingerprint_sha256=TARGET_FINGERPRINT,
    )
    accepted_route = candidate.route_evidence[0]
    rejected_route = candidate.route_evidence[1]
    receipt = AgentEvidenceToolReceipt.model_validate(
        evaluate_mapping_evidence(
            request.model_dump(mode="json"),
            operation=candidate.operation,
            route_resource_id=accepted_route.resource_id,
            condition="BINDING_MATCH",
        )
    )
    proposal = _proposal().model_copy(
        update={
            "evidence_refs": candidate.evidence,
            "route_resource_ids": [
                accepted_route.resource_id,
                rejected_route.resource_id,
            ],
            # The effective disposition is derived from route decisions, not trusted
            # from this untrusted summary field.
            "disposition": AgentDisposition.REJECT,
            "route_dispositions": [
                AgentRouteDisposition(
                    route_resource_id=accepted_route.resource_id,
                    disposition=AgentDisposition.ACCEPT,
                    rationale="The read-only binding check passed.",
                    tool_receipt_ids=[receipt.receipt_id],
                ),
                AgentRouteDisposition(
                    route_resource_id=rejected_route.resource_id,
                    disposition=AgentDisposition.REJECT,
                    rationale="The route does not satisfy this operation.",
                ),
            ],
            "tool_receipts": [receipt],
        }
    )
    _bundle_value, artifact = DiscoverySkillRunner(
        registry,
        FixtureProvider(lambda value: _bundle(value, [proposal])),
    ).run(request, deterministic_candidates=report.operation_candidates)

    reviewed, applied = apply_validated_semantic_dispositions(
        report.operation_candidates,
        artifact,
    )

    decision = artifact.validated_dispositions[0]
    assert decision.reported_disposition == AgentDisposition.REJECT
    assert decision.disposition == AgentDisposition.ACCEPT
    assert decision.route_binding_mode == "ANY_OF"
    assert applied == [candidate.operation]
    assert [item.resource_id for item in reviewed[0].route_evidence] == [
        accepted_route.resource_id
    ]
    assert reviewed[0].route_review_dispositions == {
        accepted_route.resource_id: "ACCEPT"
    }
    assert not any(
        "Heuristic mapping is ambiguous" in item for item in reviewed[0].limitations
    )


def test_semantic_accept_with_forged_or_missing_receipt_fails_closed() -> None:
    report, registry, _request_value = _request()
    candidate = report.operation_candidates[0].model_copy(
        update={"semantic_review_required": True}
    )
    report = report.model_copy(update={"operation_candidates": [candidate]})
    request = build_discovery_skill_request(
        report,
        registry,
        target_operations={candidate.operation},
        target_fingerprint_sha256=TARGET_FINGERPRINT,
    )
    proposal = _proposal().model_copy(
        update={
            "route_dispositions": [
                AgentRouteDisposition(
                    route_resource_id=candidate.route_evidence[0].resource_id,
                    disposition=AgentDisposition.ACCEPT,
                    rationale="The route looks compatible but was not tool-checked.",
                )
            ]
        }
    )
    _bundle_value, artifact = DiscoverySkillRunner(
        registry,
        FixtureProvider(lambda value: _bundle(value, [proposal])),
    ).run(request, deterministic_candidates=report.operation_candidates)

    assert artifact.source == ProposalArtifactSource.DETERMINISTIC_FALLBACK
    assert ProposalIssueCode.ACCEPT_WITHOUT_SATISFIED_BINDING in (
        artifact.rejected_proposals[0].issue_codes
    )


@pytest.mark.parametrize("disposition", [AgentDisposition.DEFER, AgentDisposition.REJECT])
def test_semantic_defer_and_reject_are_validated_without_execution_authority(
    disposition: AgentDisposition,
) -> None:
    report, registry, _request_value = _request()
    candidate = report.operation_candidates[0].model_copy(update={"semantic_review_required": True})
    report = report.model_copy(update={"operation_candidates": [candidate]})
    request = build_discovery_skill_request(
        report,
        registry,
        target_operations={candidate.operation},
        target_fingerprint_sha256=TARGET_FINGERPRINT,
    )
    proposal = _proposal().model_copy(
        update={
            "disposition": disposition,
            "route_dispositions": [
                AgentRouteDisposition(
                    route_resource_id=candidate.route_evidence[0].resource_id,
                    disposition=disposition,
                    rationale="The available evidence does not justify semantic acceptance.",
                )
            ],
        }
    )
    _bundle_value, artifact = DiscoverySkillRunner(
        registry,
        FixtureProvider(lambda value: _bundle(value, [proposal])),
    ).run(request, deterministic_candidates=report.operation_candidates)

    reviewed, applied = apply_validated_semantic_dispositions(
        report.operation_candidates,
        artifact,
    )

    assert artifact.source == ProposalArtifactSource.AGENT
    assert artifact.operation_candidates == []
    assert artifact.validated_dispositions[0].disposition == disposition
    assert applied == [candidate.operation]
    assert reviewed[0].semantic_review_disposition == disposition.value


def test_outside_slice_proposal_falls_back_and_records_false_positive() -> None:
    report, registry, request = _request()
    proposal = _proposal(
        "app.localization.status",
        evidence_ref="runtime_probe:odom",
        route_resource_id="ros_topic:/odom",
        executable_id="exe-localization",
    )
    runner = DiscoverySkillRunner(
        registry,
        FixtureProvider(lambda value: _bundle(value, [proposal])),
    )

    _bundle_value, artifact = runner.run(
        request,
        deterministic_candidates=report.operation_candidates,
    )

    assert artifact.source == ProposalArtifactSource.DETERMINISTIC_FALLBACK
    assert artifact.metrics.fallback_reason == ProposalFallbackReason.NO_VALID_PROPOSALS
    assert artifact.metrics.false_positive_rate == 1.0
    assert artifact.rejected_proposals[0].issue_codes == [
        ProposalIssueCode.OPERATION_OUTSIDE_TARGET_SLICE
    ]
    assert [item.operation for item in artifact.operation_candidates] == [
        "app.camera.snapshot"
    ]


def test_unknown_reference_is_rejected_and_measured() -> None:
    report, registry, request = _request()
    proposal = _proposal(evidence_ref="runtime_probe:invented")
    runner = DiscoverySkillRunner(
        registry,
        FixtureProvider(lambda value: _bundle(value, [proposal])),
    )

    _bundle_value, artifact = runner.run(
        request,
        deterministic_candidates=report.operation_candidates,
    )

    assert artifact.metrics.erroneous_reference_rate == 1.0
    assert ProposalIssueCode.UNKNOWN_EVIDENCE_REF in (
        artifact.rejected_proposals[0].issue_codes
    )


@pytest.mark.parametrize("as_counter_evidence", [False, True])
def test_cross_operation_evidence_is_rejected_even_when_globally_frozen(
    as_counter_evidence: bool,
) -> None:
    report, registry, request = _request()
    assert "runtime_probe:odom" in request.discovery_evidence.evidence_refs
    proposal = (
        _proposal().model_copy(
            update={"counter_evidence_refs": ["runtime_probe:odom"]}
        )
        if as_counter_evidence
        else _proposal(evidence_ref="runtime_probe:odom")
    )
    runner = DiscoverySkillRunner(
        registry,
        FixtureProvider(lambda value: _bundle(value, [proposal])),
    )

    _bundle_value, artifact = runner.run(
        request,
        deterministic_candidates=report.operation_candidates,
    )

    assert artifact.metrics.erroneous_reference_rate == 0.0
    assert artifact.metrics.false_positive_rate == 1.0
    assert artifact.rejected_proposals[0].issue_codes == [
        ProposalIssueCode.EVIDENCE_MAPPING_NOT_REPRODUCIBLE
    ]


def test_known_but_non_reproducible_route_is_rejected() -> None:
    report, registry, request = _request()
    proposal = _proposal(
        route_resource_id="ros_topic:/odom",
        executable_id="exe-camera",
    )
    runner = DiscoverySkillRunner(
        registry,
        FixtureProvider(lambda value: _bundle(value, [proposal])),
    )

    _bundle_value, artifact = runner.run(
        request,
        deterministic_candidates=report.operation_candidates,
    )

    assert artifact.metrics.erroneous_reference_rate == 0.0
    assert artifact.metrics.false_positive_rate == 1.0
    assert ProposalIssueCode.ROUTE_MAPPING_NOT_REPRODUCIBLE in (
        artifact.rejected_proposals[0].issue_codes
    )


def test_stale_registry_bundle_fails_closed_to_deterministic_path() -> None:
    report, registry, request = _request()
    runner = DiscoverySkillRunner(
        registry,
        FixtureProvider(
            lambda value: _bundle(value, [_proposal()], registry_sha256="b" * 64)
        ),
    )

    _bundle_value, artifact = runner.run(
        request,
        deterministic_candidates=report.operation_candidates,
    )

    assert artifact.source == ProposalArtifactSource.DETERMINISTIC_FALLBACK
    assert artifact.metrics.fallback_reason == ProposalFallbackReason.BUNDLE_INVALID
    assert artifact.accepted_proposals == []
    assert "Registry identity" in (artifact.fallback_detail or "")


@pytest.mark.parametrize(
    ("skill_name", "skill_version"),
    [
        ("rolo-adapt-discovery", "1.0.0"),
        ("rolo-operation-mapping", "1.0.1"),
    ],
)
def test_untrusted_mapping_skill_identity_or_version_fails_closed(
    skill_name: str,
    skill_version: str,
) -> None:
    report, registry, request = _request()
    runner = DiscoverySkillRunner(
        registry,
        FixtureProvider(
            lambda value: _bundle(
                value,
                [_proposal()],
                skill_name=skill_name,
                skill_version=skill_version,
            )
        ),
    )

    _bundle_value, artifact = runner.run(
        request,
        deterministic_candidates=report.operation_candidates,
    )

    assert artifact.source == ProposalArtifactSource.DETERMINISTIC_FALLBACK
    assert artifact.metrics.fallback_reason == ProposalFallbackReason.BUNDLE_INVALID
    assert "provenance skill" in (artifact.fallback_detail or "")


def test_provider_failure_and_unconfigured_provider_have_explicit_fallback_reasons() -> None:
    report, registry, request = _request()

    def fail(_request_value: DiscoverySkillRequest) -> OperationProposalBundle:
        raise RuntimeError("provider unavailable")

    _bundle_value, failed = DiscoverySkillRunner(
        registry,
        FixtureProvider(fail),
    ).run(request, deterministic_candidates=report.operation_candidates)
    _bundle_value, unconfigured = DiscoverySkillRunner(registry, None).run(
        request,
        deterministic_candidates=report.operation_candidates,
    )

    assert failed.metrics.fallback_reason == ProposalFallbackReason.PROVIDER_FAILURE
    assert failed.fallback_detail == "provider unavailable"
    assert (
        unconfigured.metrics.fallback_reason
        == ProposalFallbackReason.PROVIDER_NOT_CONFIGURED
    )


def test_schema_failure_is_classified_without_exposing_provider_authority() -> None:
    report, registry, request = _request()

    def invalid(_request_value: DiscoverySkillRequest) -> OperationProposalBundle:
        try:
            return OperationProposalBundle.model_validate({})
        except ValidationError:
            raise

    _bundle_value, artifact = DiscoverySkillRunner(
        registry,
        FixtureProvider(invalid),
    ).run(request, deterministic_candidates=report.operation_candidates)

    assert artifact.metrics.fallback_reason == ProposalFallbackReason.SCHEMA_INVALID
    assert artifact.source == ProposalArtifactSource.DETERMINISTIC_FALLBACK
    assert artifact.influences_release is False
