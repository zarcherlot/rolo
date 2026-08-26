from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from rolo.core.models import ProbeResult
from rolo.stages.adapt.target_evidence import (
    EvidenceDeploymentMode,
    collect_target_evidence,
    configure_deployment,
    initialize_collector,
    load_collector_state,
    new_request,
    verify_evidence_bundle,
)
from rolo.targets import (
    CollectorConfigurationV4,
    CollectorEnrollmentPinRegistry,
    CollectorEnrollmentPinV4,
    LocalTargetExecutor,
    TargetEnrollmentOperation,
    TargetEnrollmentRequest,
    TargetEnrollmentService,
    TargetEvidenceCollectionRequestV4,
    TargetExecutionStatus,
    collect_target_evidence_v4,
    verify_target_evidence_v4,
)

NOW = datetime(2026, 8, 25, 9, 0, tzinfo=timezone.utc)
APPROVAL_ID = "approval-" + "1" * 32


def _stub_probes(monkeypatch: pytest.MonkeyPatch) -> None:
    class Hardware:
        def run(self, *, robot_id: str):  # type: ignore[no-untyped-def]
            return ProbeResult(layer="hw", status="SUCCEEDED", data={"robot": robot_id})

    class Linux:
        def run(self):  # type: ignore[no-untyped-def]
            return ProbeResult(layer="linux", status="SUCCEEDED", data={"arch": "arm64"})

    class Ros:
        def run(self):  # type: ignore[no-untyped-def]
            return ProbeResult(
                layer="ros",
                status="SUCCEEDED",
                data={"nodes": [], "topics": [], "services": [], "actions": []},
            )

    monkeypatch.setattr("rolo.stages.adapt.target_evidence.HardwareProbe", Hardware)
    monkeypatch.setattr("rolo.stages.adapt.target_evidence.LinuxProbe", Linux)
    monkeypatch.setattr("rolo.stages.adapt.target_evidence.RosProbe", Ros)


def _enrollment_request(
    *,
    operation: TargetEnrollmentOperation = TargetEnrollmentOperation.ENROLL,
    expected_collector_id: str | None = None,
) -> TargetEnrollmentRequest:
    configuration = CollectorConfigurationV4()
    return TargetEnrollmentRequest(
        request_id=(
            "evidence-v4-rotate" if operation == TargetEnrollmentOperation.ROTATE
            else "evidence-v4-enroll"
        ),
        operation=operation,
        target_id="wheeltec-target",
        robot_id="wheeltec",
        challenge_nonce="2" * 32,
        issued_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
        configuration_sha256=configuration.canonical_sha256(),
        configuration=configuration,
        expected_collector_id=expected_collector_id,
        approval_id=APPROVAL_ID,
    )


def _enrolled(
    tmp_path: Path,
) -> tuple[
    TargetEnrollmentService,
    CollectorEnrollmentPinRegistry,
    CollectorEnrollmentPinV4,
]:
    service = TargetEnrollmentService(
        tmp_path / "target-enrollment",
        host_fingerprint_provider=lambda: "a" * 64,
        clock=lambda: NOW,
    )
    registry = CollectorEnrollmentPinRegistry(tmp_path / "controller-enrollment")
    request = _enrollment_request()
    result = service.execute(request)
    pin = registry.apply(request, result, now=NOW)
    return service, registry, pin


def test_v4_bundle_is_ed25519_signed_pinned_and_request_bound(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_probes(monkeypatch)
    service, _, pin = _enrolled(tmp_path)
    request = new_request("wheeltec", now=NOW)

    bundle = collect_target_evidence_v4(request, service, now=NOW)
    probes = verify_target_evidence_v4(
        bundle,
        pin=pin,
        request=request,
        deployment_mode=EvidenceDeploymentMode.LOCAL,
        now=NOW,
    )

    assert bundle.schema_version == "robot-target-evidence-bundle/v4"
    assert bundle.access == "READ_ONLY"
    assert "private" not in bundle.model_dump_json().casefold()
    assert set(probes) == {"hw", "linux", "ros"}
    binding = probes["hw"].data["target_evidence"]
    assert binding["schema_version"] == "robot-target-evidence-binding/v4"
    assert binding["target_id"] == "wheeltec-target"
    assert binding["bundle_payload_sha256"] == bundle.payload_sha256


def test_local_executor_collects_v4_from_same_enrollment_state_machine(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_probes(monkeypatch)
    monkeypatch.setattr(
        "rolo.stages.adapt.target_evidence.target_host_fingerprint",
        lambda: "a" * 64,
    )
    _, _, pin = _enrolled(tmp_path)
    observed_at = datetime.now(timezone.utc)
    evidence_request = new_request("wheeltec", now=observed_at)
    request = TargetEvidenceCollectionRequestV4(
        request_id="local-v4-collection",
        target_id="wheeltec-target",
        evidence_request=evidence_request,
    )

    result = LocalTargetExecutor(
        enrollment_root=tmp_path / "target-enrollment"
    ).collect_evidence_v4(request)

    assert result.execution_status == TargetExecutionStatus.SUCCEEDED
    assert result.bundle is not None
    verify_target_evidence_v4(
        result.bundle,
        pin=pin,
        request=evidence_request,
        deployment_mode=EvidenceDeploymentMode.LOCAL,
        now=datetime.now(timezone.utc),
    )


def test_v4_verifier_rejects_tamper_replay_expiry_and_wrong_pin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_probes(monkeypatch)
    service, _, pin = _enrolled(tmp_path)
    request = new_request("wheeltec", now=NOW)
    bundle = collect_target_evidence_v4(request, service, now=NOW)

    changed_probe = bundle.probes["linux"].model_copy(update={"data": {"arch": "x86"}})
    tampered = bundle.model_copy(
        update={"probes": {**bundle.probes, "linux": changed_probe}}
    )
    with pytest.raises(ValueError, match="payload digest mismatch"):
        verify_target_evidence_v4(
            tampered,
            pin=pin,
            request=request,
            deployment_mode=EvidenceDeploymentMode.LOCAL,
            now=NOW,
        )

    replay = new_request("wheeltec", now=NOW + timedelta(seconds=1))
    with pytest.raises(ValueError, match="does not answer"):
        verify_target_evidence_v4(
            bundle,
            pin=pin,
            request=replay,
            deployment_mode=EvidenceDeploymentMode.LOCAL,
            now=NOW,
        )

    with pytest.raises(ValueError, match="stale"):
        verify_target_evidence_v4(
            bundle,
            pin=pin,
            request=request,
            deployment_mode=EvidenceDeploymentMode.LOCAL,
            now=NOW + timedelta(minutes=8),
        )

    other_service, _, other_pin = _enrolled(tmp_path / "other")
    assert other_service is not None
    with pytest.raises(ValueError, match="pin mismatch"):
        verify_target_evidence_v4(
            bundle,
            pin=other_pin,
            request=request,
            deployment_mode=EvidenceDeploymentMode.LOCAL,
            now=NOW,
        )


def test_rotation_switches_controller_pin_and_rejects_old_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_probes(monkeypatch)
    service, registry, old_pin = _enrolled(tmp_path)
    evidence_request = new_request("wheeltec", now=NOW)
    old_bundle = collect_target_evidence_v4(evidence_request, service, now=NOW)
    old_descriptor = old_pin.descriptor
    rotation_request = _enrollment_request(
        operation=TargetEnrollmentOperation.ROTATE,
        expected_collector_id=old_descriptor.collector_id,
    )
    rotated = service.execute(rotation_request)
    new_pin = registry.apply(rotation_request, rotated, now=NOW)

    with pytest.raises(ValueError, match="pin mismatch"):
        verify_target_evidence_v4(
            old_bundle,
            pin=new_pin,
            request=evidence_request,
            deployment_mode=EvidenceDeploymentMode.LOCAL,
            now=NOW,
        )
    evidence_after_rotation = new_request("wheeltec", now=NOW)
    new_bundle = collect_target_evidence_v4(
        evidence_after_rotation,
        service,
        now=NOW,
    )
    verify_target_evidence_v4(
        new_bundle,
        pin=new_pin,
        request=evidence_after_rotation,
        deployment_mode=EvidenceDeploymentMode.LOCAL,
        now=NOW,
    )


def test_legacy_hmac_bundle_remains_read_only_compatible(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_probes(monkeypatch)
    monkeypatch.setattr(
        "rolo.stages.adapt.target_evidence.target_host_fingerprint",
        lambda: "a" * 64,
    )
    state_path = tmp_path / "legacy-collector.json"
    secret_path = tmp_path / "legacy-collector.key"
    descriptor = initialize_collector(
        robot_id="wheeltec",
        state_path=state_path,
        secret_path=secret_path,
    )
    deployment = configure_deployment(
        robot_id="wheeltec",
        mode=EvidenceDeploymentMode.LOCAL,
        descriptor=descriptor,
        verification_secret_path=secret_path,
        output_path=tmp_path / "legacy-deployment.json",
        local_collector_state_path=state_path,
    )
    request = new_request("wheeltec", now=NOW)
    bundle = collect_target_evidence(
        request,
        load_collector_state(state_path),
        now=NOW,
    )

    probes = verify_evidence_bundle(
        bundle,
        deployment=deployment,
        request=request,
        now=NOW,
    )

    assert bundle.schema_version == "robot-target-evidence-bundle/v2"
    assert set(probes) == {"hw", "linux", "ros"}
