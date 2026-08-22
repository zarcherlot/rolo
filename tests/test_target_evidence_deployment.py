from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rolo.cli import app
from rolo.core.artifacts import ArtifactStore
from rolo.core.config import get_settings
from rolo.core.models import ProbeResult
from rolo.core.registry import RobotRegistry
from rolo.stages.adapt.active_discovery import ActiveDiscoveryInputs, ActiveProbeMode
from rolo.stages.adapt.discovery import DiscoveryService
from rolo.stages.adapt.target_evidence import (
    EvidenceDeploymentMode,
    collect_over_ssh,
    collect_target_evidence,
    configure_deployment,
    initialize_collector,
    load_collector_state,
    new_request,
    verify_evidence_bundle,
)


def _collector(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "rolo.stages.adapt.target_evidence.target_host_fingerprint", lambda: "a" * 64
    )
    state_path = tmp_path / "collector.json"
    secret_path = tmp_path / "collector.key"
    descriptor = initialize_collector(
        robot_id="wheeltec",
        state_path=state_path,
        secret_path=secret_path,
    )
    return descriptor, state_path, secret_path


def _stub_probes(monkeypatch: pytest.MonkeyPatch) -> None:
    class Hardware:
        def run(self, *, robot_id: str):
            return ProbeResult(layer="hw", status="SUCCEEDED", data={"robot": robot_id})

    class Linux:
        def run(self):
            return ProbeResult(layer="linux", status="SUCCEEDED", data={"arch": "arm64"})

    class Ros:
        def run(self):
            return ProbeResult(
                layer="ros",
                status="SUCCEEDED",
                data={"nodes": [], "topics": [], "services": [], "actions": []},
            )

    monkeypatch.setattr("rolo.stages.adapt.target_evidence.HardwareProbe", Hardware)
    monkeypatch.setattr("rolo.stages.adapt.target_evidence.LinuxProbe", Linux)
    monkeypatch.setattr("rolo.stages.adapt.target_evidence.RosProbe", Ros)


def test_local_bundle_is_target_bound_signed_and_read_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    descriptor, state_path, secret_path = _collector(tmp_path, monkeypatch)
    _stub_probes(monkeypatch)
    deployment = configure_deployment(
        robot_id="wheeltec",
        mode=EvidenceDeploymentMode.LOCAL,
        descriptor=descriptor,
        verification_secret_path=secret_path,
        output_path=tmp_path / "deployment.json",
        local_collector_state_path=state_path,
    )
    request = new_request("wheeltec")
    bundle = collect_target_evidence(request, load_collector_state(state_path))
    probes = verify_evidence_bundle(bundle, deployment=deployment, request=request)

    assert bundle.access == "READ_ONLY"
    assert set(probes) == {"hw", "linux", "ros"}
    assert probes["hw"].data["target_evidence"]["target_host_fingerprint"] == "a" * 64
    assert probes["hw"].data["target_evidence"]["bundle_payload_sha256"] == (
        bundle.payload_sha256
    )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("robot_id", "another", "robot identity mismatch"),
        ("collector_id", "collector-attacker", "collector identity mismatch"),
        ("target_host_fingerprint", "b" * 64, "target host fingerprint mismatch"),
    ],
)
def test_bundle_identity_mismatch_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: str,
    message: str,
) -> None:
    descriptor, state_path, secret_path = _collector(tmp_path, monkeypatch)
    _stub_probes(monkeypatch)
    deployment = configure_deployment(
        robot_id="wheeltec",
        mode=EvidenceDeploymentMode.LOCAL,
        descriptor=descriptor,
        verification_secret_path=secret_path,
        output_path=tmp_path / "deployment.json",
        local_collector_state_path=state_path,
    )
    request = new_request("wheeltec")
    bundle = collect_target_evidence(request, load_collector_state(state_path))
    tampered = bundle.model_copy(update={field: value})

    with pytest.raises(ValueError, match=message):
        verify_evidence_bundle(tampered, deployment=deployment, request=request)


def test_tampered_probe_payload_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    descriptor, state_path, secret_path = _collector(tmp_path, monkeypatch)
    _stub_probes(monkeypatch)
    deployment = configure_deployment(
        robot_id="wheeltec",
        mode=EvidenceDeploymentMode.LOCAL,
        descriptor=descriptor,
        verification_secret_path=secret_path,
        output_path=tmp_path / "deployment.json",
        local_collector_state_path=state_path,
    )
    request = new_request("wheeltec")
    bundle = collect_target_evidence(request, load_collector_state(state_path))
    altered_probes = dict(bundle.probes)
    altered_probes["linux"] = altered_probes["linux"].model_copy(
        update={"data": {"arch": "developer-host"}}
    )
    tampered = bundle.model_copy(update={"probes": altered_probes})

    with pytest.raises(ValueError, match="payload hash mismatch"):
        verify_evidence_bundle(tampered, deployment=deployment, request=request)


def test_expired_request_is_rejected_before_any_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, state_path, _ = _collector(tmp_path, monkeypatch)
    request = new_request(
        "wheeltec", now=datetime.now(timezone.utc) - timedelta(minutes=10)
    )

    with pytest.raises(ValueError, match="expired"):
        collect_target_evidence(request, load_collector_state(state_path))


def test_requestless_bundle_replay_is_rejected_after_freshness_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    descriptor, state_path, secret_path = _collector(tmp_path, monkeypatch)
    _stub_probes(monkeypatch)
    deployment = configure_deployment(
        robot_id="wheeltec",
        mode=EvidenceDeploymentMode.LOCAL,
        descriptor=descriptor,
        verification_secret_path=secret_path,
        output_path=tmp_path / "deployment.json",
        local_collector_state_path=state_path,
    )
    collected_at = datetime.now(timezone.utc)
    request = new_request("wheeltec", now=collected_at)
    bundle = collect_target_evidence(
        request,
        load_collector_state(state_path),
        now=collected_at,
    )

    with pytest.raises(ValueError, match="bundle is stale"):
        verify_evidence_bundle(
            bundle,
            deployment=deployment,
            request=None,
            now=collected_at + timedelta(minutes=8),
        )


def test_remote_transport_pins_known_hosts_and_invokes_only_collector(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    descriptor, state_path, secret_path = _collector(tmp_path, monkeypatch)
    _stub_probes(monkeypatch)
    known_hosts = tmp_path / "known_hosts"
    known_hosts.write_text("target ssh-ed25519 AAAA\n", encoding="utf-8")
    deployment = configure_deployment(
        robot_id="wheeltec",
        mode=EvidenceDeploymentMode.REMOTE,
        descriptor=descriptor,
        verification_secret_path=secret_path,
        output_path=tmp_path / "deployment.json",
        ssh_target="rolo@target",
        known_hosts_path=known_hosts,
    )
    request = new_request("wheeltec")
    bundle = collect_target_evidence(request, load_collector_state(state_path))
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["input"] = kwargs["input"]
        return subprocess.CompletedProcess(command, 0, bundle.model_dump_json(), "")

    monkeypatch.setattr("rolo.stages.adapt.target_evidence.subprocess.run", fake_run)
    received = collect_over_ssh(deployment, request)

    command = captured["command"]
    assert "StrictHostKeyChecking=yes" in command
    assert f"UserKnownHostsFile={known_hosts.resolve()}" in command
    assert command[-4:] == [
        "target-evidence",
        "collector-run",
        "--config",
        ".rolo/config/target-evidence-collector.json",
    ]
    assert received.request_nonce == request.nonce


def test_init_exposes_local_mode_as_install_time_choice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "rolo.stages.adapt.target_evidence.target_host_fingerprint", lambda: "c" * 64
    )
    get_settings.cache_clear()
    result = CliRunner().invoke(
        app,
        ["init", "--robot-id", "field-rover", "--evidence-mode", "local"],
        env={"ROLO_CONFIG_DIR": str(tmp_path / "config")},
    )
    get_settings.cache_clear()

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["target_evidence"]["mode"] == "local"
    assert payload["target_evidence"]["collector"]["target_host_fingerprint"] == "c" * 64
    assert (tmp_path / "config/target-evidence/field-rover.json").is_file()


def test_remote_configuration_rejects_unpinned_ssh_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    descriptor, _, secret_path = _collector(tmp_path, monkeypatch)

    with pytest.raises(ValueError, match="known_hosts_path"):
        configure_deployment(
            robot_id="wheeltec",
            mode=EvidenceDeploymentMode.REMOTE,
            descriptor=descriptor,
            verification_secret_path=secret_path,
            output_path=tmp_path / "deployment.json",
            ssh_target="rolo@target",
        )


def test_remote_configuration_rejects_collector_repin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    descriptor, _, secret_path = _collector(tmp_path, monkeypatch)
    known_hosts = tmp_path / "known_hosts"
    known_hosts.write_text("target ssh-ed25519 AAAA\n", encoding="utf-8")
    output = tmp_path / "deployment.json"
    first = configure_deployment(
        robot_id="wheeltec",
        mode=EvidenceDeploymentMode.REMOTE,
        descriptor=descriptor,
        verification_secret_path=secret_path,
        output_path=output,
        ssh_target="rolo@target",
        known_hosts_path=known_hosts,
    )

    repeated = configure_deployment(
        robot_id="wheeltec",
        mode=EvidenceDeploymentMode.REMOTE,
        descriptor=descriptor,
        verification_secret_path=secret_path,
        output_path=output,
        ssh_target="rolo@target",
        known_hosts_path=known_hosts,
    )
    assert repeated == first

    replacement = descriptor.model_copy(update={"collector_id": "collector-replacement"})
    with pytest.raises(ValueError, match="already pinned"):
        configure_deployment(
            robot_id="wheeltec",
            mode=EvidenceDeploymentMode.REMOTE,
            descriptor=replacement,
            verification_secret_path=secret_path,
            output_path=output,
            ssh_target="rolo@target",
            known_hosts_path=known_hosts,
        )


def test_local_init_is_idempotent_and_preserves_collector_pin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "rolo.stages.adapt.target_evidence.target_host_fingerprint", lambda: "d" * 64
    )
    environment = {"ROLO_CONFIG_DIR": str(tmp_path / "config")}
    runner = CliRunner()
    get_settings.cache_clear()
    first = runner.invoke(
        app,
        ["init", "--robot-id", "field-rover", "--evidence-mode", "local"],
        env=environment,
    )
    get_settings.cache_clear()
    repeated = runner.invoke(
        app,
        ["init", "--robot-id", "field-rover", "--evidence-mode", "local"],
        env=environment,
    )
    get_settings.cache_clear()

    assert first.exit_code == 0, first.output
    assert repeated.exit_code == 0, repeated.output
    first_payload = json.loads(first.output)
    repeated_payload = json.loads(repeated.output)
    assert first_payload["target_evidence"]["collector"] == (
        repeated_payload["target_evidence"]["collector"]
    )
    assert repeated_payload["registration"]["status"] == "ALREADY_REGISTERED"


def test_request_protocol_rejects_write_mode() -> None:
    payload = new_request("wheeltec").model_dump(mode="json")
    payload["mode"] = "WRITE"

    with pytest.raises(ValueError):
        from rolo.stages.adapt.target_evidence import TargetEvidenceRequest

        TargetEvidenceRequest.model_validate(payload)


def test_discovery_uses_bound_target_probes_not_controller_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "driver.py").write_text(
        'create_publisher(Twist, "/cmd_vel", 10)\n', encoding="utf-8"
    )
    target_binding = {
        "schema_version": "robot-target-evidence-binding/v1",
        "robot_id": "demo_diff",
        "collector_id": "collector-target",
        "target_host_fingerprint": "a" * 64,
        "bundle_payload_sha256": "b" * 64,
        "access": "READ_ONLY",
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }
    target_probes = {
        "hw": ProbeResult(
            layer="hw",
            status="SUCCEEDED",
            data={"components": [], "target_evidence": target_binding},
        ),
        "linux": ProbeResult(
            layer="linux", status="SUCCEEDED", data={"target_evidence": target_binding}
        ),
        "ros": ProbeResult(
            layer="ros",
            status="SUCCEEDED",
            data={
                "nodes": [],
                "topics": [],
                "services": [],
                "actions": [],
                "target_evidence": target_binding,
            },
        ),
    }
    monkeypatch.setattr(
        "rolo.stages.adapt.discovery.HardwareProbe.run",
        lambda *args, **kwargs: pytest.fail("controller hardware probe must not run"),
    )
    monkeypatch.setattr(
        "rolo.stages.adapt.discovery.LinuxProbe.run",
        lambda *args, **kwargs: pytest.fail("controller Linux probe must not run"),
    )
    monkeypatch.setattr(
        "rolo.stages.adapt.discovery.RosProbe.run",
        lambda *args, **kwargs: pytest.fail("controller ROS probe must not run"),
    )
    registry = RobotRegistry(Path("tests/fixtures/robots"))
    registry.load()

    report, _ = DiscoveryService(ArtifactStore(tmp_path / "artifacts")).run(
        robot=registry.get("demo_diff"),
        active_inputs=ActiveDiscoveryInputs(
            source_roots=[source], active_probe=ActiveProbeMode.RUNTIME_READONLY
        ),
        target_probes=target_probes,
    )

    assert report.probes["hw"].data["target_evidence"]["collector_id"] == "collector-target"
    assert report.probes["linux"].data["target_evidence"]["robot_id"] == "demo_diff"


def test_discovery_rejects_unbound_precollected_probes(tmp_path: Path) -> None:
    registry = RobotRegistry(Path("tests/fixtures/robots"))
    registry.load()
    probes = {
        layer: ProbeResult(layer=layer, status="SUCCEEDED", data={})
        for layer in ("hw", "linux", "ros")
    }

    with pytest.raises(ValueError, match="lack verified target binding"):
        DiscoveryService(ArtifactStore(tmp_path / "artifacts")).run(
            robot=registry.get("demo_diff"),
            active_inputs=ActiveDiscoveryInputs(active_probe=ActiveProbeMode.RUNTIME_READONLY),
            target_probes=probes,
        )
