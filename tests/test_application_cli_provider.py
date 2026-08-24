from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from rolo.core.models import DiscoveryReport, ProbeResult
from rolo.stages.adapt.active_discovery import HelpProbeResult, HelpProbeStatus
from rolo.stages.adapt.application_cli_mapping import (
    load_application_cli_operation_rules,
    matching_application_cli_rules,
)
from rolo.stages.adapt.discovery import (
    ApplicationProbe,
    _build_operation_candidates,
    _semantic_bindings,
)
from rolo.stages.adapt.operation_registry import (
    adapter_operation_eligibility,
    canonical_operation_registry,
)
from rolo.stages.adapt.proposal_orchestration import (
    RegistrySnapshot,
    build_discovery_skill_request,
)
from rolo.stages.adapt.routes import candidate_route_observed, probe_routes
from rolo.stages.adapt.target_evidence import (
    TargetExecutableHelpEvidence,
    bind_target_executable_routes,
)

NOW = datetime(2026, 8, 24, tzinfo=timezone.utc)


def _application_probe(tmp_path: Path, name: str) -> ProbeResult:
    (tmp_path / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "generic-robot-app"',
                'version = "1.0.0"',
                "[project.scripts]",
                f'{name} = "generic_robot.cli:main"',
            ]
        ),
        encoding="utf-8",
    )
    return ApplicationProbe().run([tmp_path])


def _help_record(path: str, *, status: HelpProbeStatus = HelpProbeStatus.SUCCEEDED):
    output = "usage: generic-camera [--format FORMAT]\n"
    return TargetExecutableHelpEvidence(
        executable_id="target-exe-" + "a" * 24,
        path=path,
        executable_sha256="b" * 64,
        help_probe=HelpProbeResult(
            status=status,
            exit_code=0 if status == HelpProbeStatus.SUCCEEDED else 1,
            output_bytes=len(output),
        ),
        output_text=output,
        output_sha256=hashlib.sha256(output.encode("utf-8")).hexdigest(),
        usage=["generic-camera [--format FORMAT]"],
        parameters=["--format"],
    )


def _bound_linux(record: TargetExecutableHelpEvidence) -> ProbeResult:
    return bind_target_executable_routes(
        ProbeResult(layer="linux", status="SUCCEEDED", data={"route_evidence": []}),
        [record],
        bundle_payload_sha256="c" * 64,
        observed_at=NOW,
    )


def test_source_manifest_declares_cli_route_without_observing_it(tmp_path: Path) -> None:
    probe = _application_probe(tmp_path, "acme-find-cameras")

    routes = probe_routes(probe)

    assert [item.resource_id for item in routes] == ["cli:acme-find-cameras"]
    assert routes[0].evidence_origin == "DECLARED_STATIC"
    assert routes[0].interface_type == "application/cli"


def test_verified_help_derives_exact_name_and_path_routes() -> None:
    record = _help_record("/opt/acme/bin/acme-find-cameras")

    routes = probe_routes(_bound_linux(record))

    assert {item.resource_id for item in routes} == {
        "cli:/opt/acme/bin/acme-find-cameras",
        "cli:acme-find-cameras",
    }
    assert all(item.observed for item in routes)
    assert all(item.provider_id == record.executable_id for item in routes)
    assert all(item.runtime_revision == record.executable_sha256 for item in routes)
    assert len({item.interface_schema_sha256 for item in routes}) == 1


def test_generic_camera_inventory_cli_becomes_a_gateable_candidate(tmp_path: Path) -> None:
    application = _application_probe(tmp_path, "acme-find-cameras")
    linux = _bound_linux(_help_record("/opt/acme/bin/acme-find-cameras"))
    probes = {
        "application": application,
        "linux": linux,
        "ros": ProbeResult(layer="ros", status="UNAVAILABLE", data={"topics": []}),
    }

    bindings = _semantic_bindings(probes)
    candidates = _build_operation_candidates(bindings)
    candidate = next(item for item in candidates if item.operation == "app.camera.list")
    report = DiscoveryReport(
        discovery_id="discovery-non-ros",
        robot_id="generic-robot",
        status="SUCCEEDED",
        platform={"os": "linux"},
        capability_manifest={},
        probes=probes,
        semantic_bindings=bindings,
        operation_candidates=candidates,
    )

    assert candidate.origin == "DETERMINISTIC"
    assert candidate.route_evidence[0].kind == "cli"
    assert candidate_route_observed(candidate, probes)
    eligible, deferred = adapter_operation_eligibility(report)
    assert "app.camera.list" in eligible
    assert "app.camera.list" not in deferred


def test_cli_mapping_requires_both_source_declaration_and_successful_target_help(
    tmp_path: Path,
) -> None:
    application = _application_probe(tmp_path, "acme-find-cameras")
    failed_linux = _bound_linux(
        _help_record(
            "/opt/acme/bin/acme-find-cameras",
            status=HelpProbeStatus.FAILED,
        )
    )
    undeclared_linux = _bound_linux(_help_record("/opt/acme/bin/other-find-cameras"))
    ros = ProbeResult(layer="ros", status="UNAVAILABLE", data={"topics": []})

    assert not _semantic_bindings({"application": application, "linux": failed_linux, "ros": ros})
    assert not _semantic_bindings(
        {"application": application, "linux": undeclared_linux, "ros": ros}
    )


def test_rules_are_project_neutral_and_do_not_map_diagnostic_info() -> None:
    rules = load_application_cli_operation_rules()

    assert rules.schema_version == "rolo-application-cli-operation-rules/v1"
    assert [
        operation
        for item in matching_application_cli_rules("vendor-list-camera")
        for operation in item.operations
    ] == ["app.camera.list"]
    assert matching_application_cli_rules("lerobot-info") == []
    assert matching_application_cli_rules("lerobot-record") == []


def test_static_application_route_is_available_to_agent_but_not_runtime_gate(
    tmp_path: Path,
) -> None:
    application = _application_probe(tmp_path, "acme-find-cameras")
    report = DiscoveryReport(
        discovery_id="discovery-static-cli",
        robot_id="generic-robot",
        status="SUCCEEDED",
        platform={"os": "linux"},
        capability_manifest={},
        probes={"application": application},
    )
    registry = RegistrySnapshot(canonical_operation_registry(), registry_version="294-test")

    request = build_discovery_skill_request(
        report,
        registry,
        target_operations=["app.camera.list"],
        target_fingerprint_sha256="d" * 64,
    )

    route = request.discovery_evidence.route_resources["cli:acme-find-cameras"]
    assert route.evidence_origin == "DECLARED_STATIC"
    assert request.discovery_evidence.deterministic_bindings == {}
