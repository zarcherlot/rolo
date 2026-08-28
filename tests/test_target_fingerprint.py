import json
from pathlib import Path

from rolo.core.artifacts import ArtifactStore
from rolo.core.models import (
    DiscoveryReport,
    DiscoveryStatus,
    OperationCandidate,
    ProbeResult,
    RouteEvidence,
)
from rolo.core.registry import RobotRegistry
from rolo.stages.adapt.active_discovery import ActiveDiscoveryInputs
from rolo.stages.adapt.discovery import DiscoveryService
from rolo.stages.adapt.target_fingerprint import (
    runtime_environment_from_report,
    target_fingerprint_sha256,
)
from rolo.stages.artifact_paths import resolve_artifact_ref


def test_target_fingerprint_binds_primary_executable_digest(tmp_path: Path) -> None:
    executable = tmp_path / "robot-driver.bin"
    executable.write_bytes(b"deployed-driver-v1")
    registry = RobotRegistry(Path("tests/fixtures/robots"))
    registry.load()
    artifact_root = tmp_path / "artifacts"
    report, _ = DiscoveryService(ArtifactStore(artifact_root)).run(
        robot=registry.get("demo_diff"),
        active_inputs=ActiveDiscoveryInputs(executables=[executable]),
    )
    before = target_fingerprint_sha256(report, artifact_root)
    active_path = resolve_artifact_ref(artifact_root, report.active_discovery_report_ref)
    active = json.loads(active_path.read_text(encoding="utf-8"))
    active["executables"][0]["sha256"] = "f" * 64
    active_path.write_text(json.dumps(active), encoding="utf-8")

    after = target_fingerprint_sha256(report, artifact_root)

    assert after != before


def _scoped_report() -> DiscoveryReport:
    camera = RouteEvidence(
        resource_id="ros_topic:/camera/image_raw",
        kind="ros_topic",
        endpoint="/camera/image_raw",
        evidence_origin="OBSERVED_RUNTIME",
        source="runtime_probe:ros",
    )
    return DiscoveryReport(
        discovery_id="disc-1",
        robot_id="demo",
        status=DiscoveryStatus.SUCCEEDED,
        platform={"architecture": "x86_64"},
        capability_manifest={},
        probes={
            "ros": ProbeResult(
                layer="ros",
                status=DiscoveryStatus.SUCCEEDED,
                data={
                    "route_evidence": [camera.model_dump(mode="json")],
                    "runtime_environment": {"ROS_DOMAIN_ID": "7"},
                },
            ),
            "hw": ProbeResult(
                layer="hw",
                status=DiscoveryStatus.SUCCEEDED,
                data={
                    "components": [
                        {
                            "resource_id": "hardware_path:/dev/video0",
                            "kind": "sensor",
                            "name": "front_camera",
                            "modality": "camera",
                            "driver": "camera_driver_v1",
                        },
                        {
                            "resource_id": "hardware_component:power:main_battery",
                            "kind": "power",
                            "name": "main_battery",
                            "model": "battery_v1",
                        },
                    ]
                },
            ),
        },
        operation_candidates=[
            OperationCandidate(
                operation="app.camera.snapshot",
                route_evidence=[camera],
                hardware_resource_ids=["hardware_path:/dev/video0"],
            )
        ],
    )


def test_scoped_fingerprint_ignores_unrelated_discovery_growth() -> None:
    report = _scoped_report()
    before = target_fingerprint_sha256(
        report, operations=["app.camera.snapshot"]
    )
    unrelated = RouteEvidence(
        resource_id="ros_topic:/diagnostics",
        kind="ros_topic",
        endpoint="/diagnostics",
        evidence_origin="OBSERVED_RUNTIME",
        source="runtime_probe:ros",
    )
    ros_probe = report.probes["ros"].model_copy(
        update={
            "data": {
                **report.probes["ros"].data,
                "route_evidence": [
                    *report.probes["ros"].data["route_evidence"],
                    unrelated.model_dump(mode="json"),
                ],
            }
        }
    )
    expanded = report.model_copy(
        update={
            "probes": {**report.probes, "ros": ros_probe},
            "operation_candidates": [
                *report.operation_candidates,
                OperationCandidate(
                    operation="app.diagnostics.summary",
                    route_evidence=[unrelated],
                ),
            ],
        }
    )

    after = target_fingerprint_sha256(
        expanded, operations=["app.camera.snapshot"]
    )

    assert after == before


def test_scoped_fingerprint_binds_runtime_context() -> None:
    report = _scoped_report()
    before = target_fingerprint_sha256(
        report, operations=["app.camera.snapshot"]
    )
    changed_probe = report.probes["ros"].model_copy(
        update={
            "data": {
                **report.probes["ros"].data,
                "runtime_environment": {"ROS_DOMAIN_ID": "8"},
            }
        }
    )
    changed = report.model_copy(
        update={"probes": {**report.probes, "ros": changed_probe}}
    )

    after = target_fingerprint_sha256(
        changed, operations=["app.camera.snapshot"]
    )

    assert after != before


def test_runtime_environment_resolves_normalized_cli_from_target_help(
    tmp_path: Path,
) -> None:
    executable = tmp_path / ".venv/bin/lerobot-find-cameras"
    executable.parent.mkdir(parents=True)
    executable.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    route = RouteEvidence(
        resource_id="cli:lerobot-find-cameras",
        kind="cli",
        endpoint="lerobot-find-cameras",
        interface_type="application/cli",
        provider_id="target-exe-camera",
        evidence_origin="OBSERVED_RUNTIME",
        source="target-evidence:fixture",
    )
    report = DiscoveryReport(
        discovery_id="disc-cli",
        robot_id="lerobot",
        status=DiscoveryStatus.SUCCEEDED,
        platform={},
        capability_manifest={},
        probes={
            "linux": ProbeResult(
                layer="linux",
                status=DiscoveryStatus.SUCCEEDED,
                data={
                    "target_evidence": {
                        "executable_help": [
                            {
                                "executable_id": "target-exe-camera",
                                "path": str(executable),
                            }
                        ]
                    }
                },
            )
        },
        operation_candidates=[
            OperationCandidate(
                operation="app.camera.list",
                route_evidence=[route],
            )
        ],
    )

    environment = runtime_environment_from_report(
        report, operations={"app.camera.list"}
    )

    assert environment["PATH"] == str(executable.parent.resolve())


def test_scoped_fingerprint_binds_only_relevant_hardware() -> None:
    report = _scoped_report()
    before = target_fingerprint_sha256(
        report, operations=["app.camera.snapshot"]
    )
    unrelated_probe = report.probes["hw"].model_copy(
        update={
            "data": {
                "components": [
                    report.probes["hw"].data["components"][0],
                    {
                        **report.probes["hw"].data["components"][1],
                        "model": "battery_v2",
                    },
                ]
            }
        }
    )
    unrelated = report.model_copy(
        update={"probes": {**report.probes, "hw": unrelated_probe}}
    )
    relevant_probe = report.probes["hw"].model_copy(
        update={
            "data": {
                "components": [
                    {
                        **report.probes["hw"].data["components"][0],
                        "driver": "camera_driver_v2",
                    },
                    report.probes["hw"].data["components"][1],
                ]
            }
        }
    )
    relevant = report.model_copy(
        update={"probes": {**report.probes, "hw": relevant_probe}}
    )

    assert (
        target_fingerprint_sha256(
            unrelated, operations=["app.camera.snapshot"]
        )
        == before
    )
    assert (
        target_fingerprint_sha256(
            relevant, operations=["app.camera.snapshot"]
        )
        != before
    )
