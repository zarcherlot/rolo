from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from rolo.core.models import DiscoveryReport, OperationCandidate, ProbeResult, RouteEvidence
from rolo.stages.adapt.active_discovery import HelpProbeResult, HelpProbeStatus
from rolo.stages.adapt.application_cli_mapping import (
    infer_application_cli_operations,
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
from rolo.stages.adapt.target_fingerprint import runtime_environment_from_report

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


def test_target_runtime_path_is_derived_from_observed_cli_directory(
    tmp_path: Path,
) -> None:
    target_bin = tmp_path / "target-venv/bin"
    target_bin.mkdir(parents=True)
    executable = target_bin / "generic-find-cameras"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    linux_probe = _bound_linux(_help_record(str(executable)))
    report = DiscoveryReport(
        discovery_id="disc-cli-path",
        robot_id="demo",
        status="SUCCEEDED",
        platform={},
        capability_manifest={},
        probes={"linux": linux_probe},
        operation_candidates=[
            OperationCandidate(
                operation="app.camera.list",
                evidence=[str(executable)],
                route_evidence=probe_routes(linux_probe),
            )
        ],
    )

    assert runtime_environment_from_report(report) == {
        "PATH": str(target_bin.resolve())
    }


def test_target_runtime_path_is_scoped_to_selected_operations(tmp_path: Path) -> None:
    selected_bin = tmp_path / "selected/bin"
    unrelated_bin = tmp_path / "unrelated/bin"
    selected_bin.mkdir(parents=True)
    unrelated_bin.mkdir(parents=True)
    selected = selected_bin / "camera-list"
    unrelated = unrelated_bin / "camera-record"
    selected.write_text("#!/bin/sh\n", encoding="utf-8")
    unrelated.write_text("#!/bin/sh\n", encoding="utf-8")

    def candidate(operation: str, endpoint: Path) -> OperationCandidate:
        return OperationCandidate(
            operation=operation,
            evidence=[str(endpoint)],
            route_evidence=[
                RouteEvidence(
                    resource_id=f"cli:{endpoint}",
                    kind="cli",
                    endpoint=str(endpoint),
                    evidence_origin="OBSERVED_RUNTIME",
                    source="target-help:test",
                )
            ],
        )

    report = DiscoveryReport(
        discovery_id="disc-cli-scope",
        robot_id="demo",
        status="SUCCEEDED",
        platform={},
        capability_manifest={},
        probes={},
        operation_candidates=[
            candidate("app.camera.list", selected),
            candidate("app.camera.snapshot", unrelated),
        ],
    )

    assert runtime_environment_from_report(
        report,
        operations={"app.camera.list"},
    ) == {"PATH": str(selected_bin.resolve())}


def test_editable_python_root_is_explicit_in_runtime_context(tmp_path: Path) -> None:
    target_bin = tmp_path / "target-venv/bin"
    target_bin.mkdir(parents=True)
    (target_bin.parent / "pyvenv.cfg").write_text("home = /usr/bin\n", encoding="utf-8")
    site_packages = target_bin.parent / "lib/python3.12/site-packages"
    site_packages.mkdir(parents=True)
    editable_source = tmp_path / "lerobot"
    editable_source.mkdir()
    (editable_source / "pyproject.toml").write_text(
        "[project]\nname='lerobot'\nversion='0.0.0'\n",
        encoding="utf-8",
    )
    (site_packages / "lerobot.pth").write_text(str(editable_source), encoding="utf-8")
    executable = target_bin / "lerobot-find-cameras"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    route = RouteEvidence(
        resource_id=f"cli:{executable}",
        kind="cli",
        endpoint=str(executable),
        evidence_origin="OBSERVED_RUNTIME",
        source="target-help:test",
    )
    report = DiscoveryReport(
        discovery_id="disc-editable-runtime",
        robot_id="demo",
        status="SUCCEEDED",
        platform={},
        capability_manifest={},
        probes={},
        operation_candidates=[
            OperationCandidate(
                operation="app.camera.list",
                evidence=[str(executable)],
                route_evidence=[route],
            )
        ],
    )

    assert runtime_environment_from_report(report) == {
        "PATH": str(target_bin.resolve()),
        "PYTHONPATH": str(editable_source.resolve()),
    }


def test_editable_python_root_rejects_home_or_ancestor_mounts(
    tmp_path: Path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    target_bin = tmp_path / "target-venv/bin"
    target_bin.mkdir(parents=True)
    (target_bin.parent / "pyvenv.cfg").write_text("home = /usr/bin\n", encoding="utf-8")
    site_packages = target_bin.parent / "lib/python3.12/site-packages"
    site_packages.mkdir(parents=True)
    broad_home = tmp_path / "home"
    broad_home.mkdir()
    (broad_home / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    (site_packages / "unsafe.pth").write_text(str(broad_home), encoding="utf-8")
    executable = target_bin / "lerobot-find-cameras"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(Path, "home", lambda: broad_home)
    route = RouteEvidence(
        resource_id=f"cli:{executable}",
        kind="cli",
        endpoint=str(executable),
        evidence_origin="OBSERVED_RUNTIME",
        source="target-help:test",
    )
    report = DiscoveryReport(
        discovery_id="disc-unsafe-editable-runtime",
        robot_id="demo",
        status="SUCCEEDED",
        platform={},
        capability_manifest={},
        probes={},
        operation_candidates=[
            OperationCandidate(
                operation="app.camera.list",
                evidence=[str(executable)],
                route_evidence=[route],
            )
        ],
    )

    assert runtime_environment_from_report(report) == {
        "PATH": str(target_bin.resolve())
    }


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


def test_cli_operation_inference_uses_help_semantics_not_only_name() -> None:
    camera = infer_application_cli_operations(
        "robot-tool",
        usage=["usage: robot-tool [--camera front]"],
        subcommands=["find-cameras"],
        help_text="Find all available cameras and print their metadata.",
    )
    calibration = infer_application_cli_operations(
        "robot-tool",
        usage=["usage: robot-tool --motor-id MOTOR"],
        help_text="Calibrate one actuator motor and report its limits.",
    )

    assert [item.operation for item in camera] == ["app.camera.list"]
    assert [item.operation for item in calibration] == ["hw.actuator.calibrate"]


def test_cli_operation_inference_does_not_treat_package_info_as_robot_health() -> None:
    matches = infer_application_cli_operations(
        "lerobot-info",
        help_text="Use this script to get a quick summary of your system config and package versions.",
    )

    assert matches == []


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
