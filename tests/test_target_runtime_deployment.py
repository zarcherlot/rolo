from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from rolo.adapter_runner import AdapterProcessResult
from rolo.core.hashing import sha256_file
from rolo.stages.adapt.models import (
    AdapterBundleManifest,
    AdapterReleaseManifest,
    PublishedAdapterFile,
)
from rolo.targets.enrollment import (
    CollectorConfigurationV4,
    CollectorEnrollmentPinRegistry,
    TargetEnrollmentOperation,
    TargetEnrollmentRequest,
    TargetEnrollmentService,
)
from rolo.targets.runtime_deployment import (
    LocatedRuntimeContext,
    TargetDescribeRequest,
    TargetObservedRuntimeEnvironment,
    TargetProjectEvidenceCandidate,
    TargetProjectEvidenceKind,
    TargetProjectEvidenceRequest,
    TargetProjectEvidenceStatus,
    TargetWorkspaceManifest,
    TargetWorkspaceRef,
    attest_target_describe,
    detect_target_project_evidence,
    execute_target_describe,
    observe_target_workspace,
    target_sandbox_profile_sha256,
    verify_target_describe_attestation,
)

NOW = datetime(2026, 8, 25, 10, 0, tzinfo=timezone.utc)
APPROVAL_ID = "approval-" + "a" * 32


def _enrolled(tmp_path: Path):
    service = TargetEnrollmentService(
        tmp_path / "target-enrollment",
        host_fingerprint_provider=lambda: "c" * 64,
        clock=lambda: NOW,
    )
    configuration = CollectorConfigurationV4()
    request = TargetEnrollmentRequest(
        request_id="enroll-w5-target",
        operation=TargetEnrollmentOperation.ENROLL,
        target_id="wheeltec-target",
        robot_id="wheeltec",
        challenge_nonce="1" * 32,
        issued_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
        configuration_sha256=configuration.canonical_sha256(),
        configuration=configuration,
        approval_id=APPROVAL_ID,
    )
    result = service.execute(request)
    pin = CollectorEnrollmentPinRegistry(tmp_path / "controller-pins").apply(
        request,
        result,
        now=NOW,
    )
    return service, pin


def test_target_workspace_manifest_is_bounded_and_deterministic(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    (workspace_root / "src").mkdir(parents=True)
    (workspace_root / "src" / "driver.py").write_text("print('ok')\n", encoding="utf-8")
    executable = workspace_root / "bin" / "wheeltec"
    executable.parent.mkdir()
    executable.write_bytes(b"#!/bin/sh\necho wheeltec\n")
    if os.name == "posix":
        executable.chmod(0o755)
    workspace = TargetWorkspaceRef(
        workspace_id="wheeltec-workspace",
        target_id="wheeltec-target",
        robot_id="wheeltec",
        root=str(workspace_root.resolve()),
    )

    first = observe_target_workspace(
        workspace,
        selected_paths=["src/driver.py", "bin/wheeltec"],
        observed_at=NOW,
    )
    second = observe_target_workspace(
        workspace,
        selected_paths=["bin/wheeltec", "src/driver.py"],
        observed_at=NOW + timedelta(seconds=1),
    )

    assert [item.path for item in first.files] == ["bin/wheeltec", "src/driver.py"]
    assert first.content_sha256 == second.content_sha256
    assert first.observed_at != second.observed_at
    assert TargetWorkspaceManifest.model_validate_json(first.model_dump_json()) == first


def test_target_workspace_rejects_escape_symlink_and_digest_tamper(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    (workspace_root / "real.txt").write_text("real", encoding="utf-8")
    workspace = TargetWorkspaceRef(
        workspace_id="workspace-1",
        target_id="target-1",
        robot_id="robot-1",
        root=str(workspace_root.resolve()),
    )
    with pytest.raises(ValueError, match="normalized and relative"):
        observe_target_workspace(workspace, selected_paths=["../outside"])

    link = workspace_root / "link.txt"
    try:
        link.symlink_to(workspace_root / "real.txt")
    except OSError:
        pytest.skip("symlink creation is unavailable on this host")
    with pytest.raises(ValueError, match="not a regular file"):
        observe_target_workspace(workspace, selected_paths=["link.txt"])

    manifest = observe_target_workspace(workspace, selected_paths=["real.txt"])
    with pytest.raises(ValidationError, match="content digest mismatch"):
        TargetWorkspaceManifest.model_validate(
            manifest.model_copy(update={"content_sha256": "0" * 64}).model_dump()
        )


def test_target_project_evidence_detects_only_declared_candidates(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    (root / "src").mkdir(parents=True)
    (root / "pyproject.toml").write_text("[project]\nname='robot'\n", encoding="utf-8")
    (root / "src" / "main.py").write_text("print('robot')\n", encoding="utf-8")
    (root / "secret.txt").write_text("must not be inventoried", encoding="utf-8")
    workspace = TargetWorkspaceRef(
        workspace_id="workspace-project",
        target_id="target-project",
        robot_id="robot-project",
        root=str(root.resolve()),
    )
    request = TargetProjectEvidenceRequest(
        request_id="detect-project-evidence",
        workspace=workspace,
        candidates=[
            TargetProjectEvidenceCandidate(
                path="missing-runtime.json",
                kind=TargetProjectEvidenceKind.RUNTIME_METADATA,
                role="RUNTIME",
            ),
            TargetProjectEvidenceCandidate(
                path="pyproject.toml",
                kind=TargetProjectEvidenceKind.BUILD_METADATA,
            ),
            TargetProjectEvidenceCandidate(
                path="src/main.py",
                kind=TargetProjectEvidenceKind.SOURCE_ENTRYPOINT,
            ),
        ],
        approval_id=APPROVAL_ID,
    )

    first = detect_target_project_evidence(request, observed_at=NOW)
    second = detect_target_project_evidence(
        request,
        observed_at=NOW + timedelta(seconds=1),
    )

    assert first.status == TargetProjectEvidenceStatus.OBSERVED
    assert first.manifest is not None
    assert [item.path for item in first.hits] == ["pyproject.toml", "src/main.py"]
    assert "secret.txt" not in [item.path for item in first.manifest.files]
    assert first.manifest.content_sha256 == second.manifest.content_sha256  # type: ignore[union-attr]
    assert first.observed_at != second.observed_at


def test_target_project_evidence_rejects_required_missing_and_symlink(
    tmp_path: Path,
) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "real.txt").write_text("real", encoding="utf-8")
    workspace = TargetWorkspaceRef(
        workspace_id="workspace-project",
        target_id="target-project",
        robot_id="robot-project",
        root=str(root.resolve()),
    )
    required = TargetProjectEvidenceRequest(
        request_id="required-project-evidence",
        workspace=workspace,
        candidates=[
            TargetProjectEvidenceCandidate(
                path="missing.txt",
                kind=TargetProjectEvidenceKind.BUILD_METADATA,
                required=True,
            )
        ],
        approval_id=APPROVAL_ID,
    )
    with pytest.raises(ValueError, match="required.*unavailable"):
        detect_target_project_evidence(required)

    link = root / "link.txt"
    try:
        link.symlink_to(root / "real.txt")
    except OSError:
        pytest.skip("symlink creation is unavailable on this host")
    linked = required.model_copy(
        update={
            "request_id": "linked-project-evidence",
            "candidates": [
                TargetProjectEvidenceCandidate(
                    path="link.txt",
                    kind=TargetProjectEvidenceKind.SOURCE_ENTRYPOINT,
                )
            ],
        }
    )
    with pytest.raises(ValueError, match="not a regular file"):
        detect_target_project_evidence(linked)


def test_located_runtime_context_does_not_probe_controller_paths() -> None:
    environment = TargetObservedRuntimeEnvironment.model_validate(
        {
            "PATH": "/target/venv/bin:/usr/bin",
            "PYTHONPATH": "/target/workspace/src",
            "ROS_DISTRO": "humble",
        }
    )
    context = LocatedRuntimeContext(
        target_id="wheeltec-target",
        robot_id="wheeltec",
        workspace_id="wheeltec-workspace",
        workspace_sha256="a" * 64,
        adapter_entrypoint="/target/releases/r1/adapter.py",
        python_interpreter="/target/venv/bin/python",
        virtualenv_root="/target/venv",
        editable_roots=["/target/workspace/src"],
        runtime_environment=environment,
    )

    assert context.runtime_environment.as_environment()["PATH"] == (
        "/target/venv/bin:/usr/bin"
    )
    with pytest.raises(ValidationError, match="available absolute path"):
        context.runtime_environment.materialize_on_target()

    with pytest.raises(ValidationError):
        TargetObservedRuntimeEnvironment.model_validate({"OPENAI_API_KEY": "secret"})


def test_describe_attestation_binds_release_runtime_sandbox_output_and_identity(
    tmp_path: Path,
) -> None:
    service, pin = _enrolled(tmp_path)
    request = TargetDescribeRequest(
        request_id="describe-wheeltec-r1",
        target_id="wheeltec-target",
        robot_id="wheeltec",
        collector_id=pin.descriptor.collector_id,
        release_id="release-r1",
        release_manifest_sha256="1" * 64,
        bundle_manifest_sha256="2" * 64,
        runtime_context_sha256="3" * 64,
        sandbox_profile_sha256="4" * 64,
        nonce="5" * 32,
        issued_at=NOW,
        expires_at=NOW + timedelta(minutes=2),
    )
    output = {
        "operations": {
            "linux.binary.describe": "adapter.py",
            "ros.topic.list": "adapter.py",
        },
        "runtime_protocol": "robot-adapter-rpc/v1",
    }
    attestation = attest_target_describe(
        request,
        output=output,
        service=service,
        now=NOW + timedelta(seconds=1),
    )

    verify_target_describe_attestation(
        attestation,
        request=request,
        pin=pin,
        expected_operations=output["operations"],
        output=output,
        now=NOW + timedelta(seconds=2),
    )
    assert "invoke" not in json.dumps(attestation.model_dump(mode="json"))

    changed_request = request.model_copy(update={"runtime_context_sha256": "9" * 64})
    with pytest.raises(ValueError, match="binding mismatch"):
        verify_target_describe_attestation(
            attestation,
            request=changed_request,
            pin=pin,
            expected_operations=output["operations"],
            output=output,
            now=NOW + timedelta(seconds=2),
        )
    with pytest.raises(ValueError, match="output digest mismatch"):
        verify_target_describe_attestation(
            attestation,
                request=request,
                pin=pin,
                expected_operations=output["operations"],
                output={"operations": output["operations"]},
                now=NOW + timedelta(seconds=2),
            )
    with pytest.raises(ValueError, match="operations do not match"):
        verify_target_describe_attestation(
            attestation,
            request=request,
            pin=pin,
            expected_operations={"ros.topic.list": "other.py"},
            output=output,
            now=NOW + timedelta(seconds=2),
        )


def test_describe_request_rejects_replay_after_expiry(tmp_path: Path) -> None:
    service, pin = _enrolled(tmp_path)
    request = TargetDescribeRequest(
        request_id="describe-wheeltec-expiry",
        target_id="wheeltec-target",
        robot_id="wheeltec",
        collector_id=pin.descriptor.collector_id,
        release_id="release-r1",
        release_manifest_sha256="1" * 64,
        bundle_manifest_sha256="2" * 64,
        runtime_context_sha256="3" * 64,
        sandbox_profile_sha256="4" * 64,
        nonce="5" * 32,
        issued_at=NOW,
        expires_at=NOW + timedelta(minutes=1),
    )
    output = {"operations": {"ros.topic.list": "adapter.py"}}
    attestation = attest_target_describe(
        request,
        output=output,
        service=service,
        now=NOW + timedelta(seconds=1),
    )
    with pytest.raises(ValueError, match="not currently valid"):
        verify_target_describe_attestation(
            attestation,
            request=request,
            pin=pin,
            expected_operations=output["operations"],
            output=output,
            now=NOW + timedelta(minutes=2),
        )


def test_describe_output_is_secret_closed(tmp_path: Path) -> None:
    service, pin = _enrolled(tmp_path)
    request = TargetDescribeRequest(
        request_id="describe-wheeltec-secret-closed",
        target_id="wheeltec-target",
        robot_id="wheeltec",
        collector_id=pin.descriptor.collector_id,
        release_id="release-r1",
        release_manifest_sha256="1" * 64,
        bundle_manifest_sha256="2" * 64,
        runtime_context_sha256="3" * 64,
        sandbox_profile_sha256="4" * 64,
        nonce="5" * 32,
        issued_at=NOW,
        expires_at=NOW + timedelta(minutes=1),
    )
    with pytest.raises(ValidationError):
        attest_target_describe(
            request,
            output={
                "operations": {"ros.topic.list": "adapter.py"},
                "environment": {"OPENAI_API_KEY": "secret"},
            },
            service=service,
            now=NOW + timedelta(seconds=1),
        )


class _DescribeRunner:
    def __init__(self, output: dict[str, object]) -> None:
        self.output = output
        self.commands: list[list[str]] = []

    def run(self, command: list[str], **_: object) -> AdapterProcessResult:
        self.commands.append(command)
        return AdapterProcessResult(
            returncode=0,
            stdout=json.dumps(self.output),
            stderr="",
        )


def test_execute_target_describe_verifies_frozen_release_and_never_invokes(
    tmp_path: Path,
) -> None:
    service, pin = _enrolled(tmp_path)
    release_root = tmp_path / "release"
    adapter_root = release_root / "adapter"
    adapter_root.mkdir(parents=True)
    entrypoint = adapter_root / "adapter.py"
    entrypoint.write_text("# frozen adapter\n", encoding="utf-8")
    bundle = AdapterBundleManifest(
        bundle_id="wheeltec-bundle",
        bundle_version="1.0.0",
        robot_id="wheeltec",
        discovery_id="discovery-1",
        package_file="adapter.py",
        package_sha256=sha256_file(entrypoint),
        files=[
            {
                "path": "adapter.py",
                "sha256": sha256_file(entrypoint),
                "role": "ENTRYPOINT",
            }
        ],
        operations=[
            {
                "operation": "ros.topic.list",
                "entrypoint": "adapter.py",
                "contract_version": "1.1.0",
                "contract_sha256": "7" * 64,
            }
        ],
    )
    bundle_path = adapter_root / "adapter-manifest.json"
    bundle_path.write_text(bundle.model_dump_json(indent=2) + "\n", encoding="utf-8")
    other_files: dict[str, Path] = {}
    for name in (
        "tool-catalog.json",
        "state-graph.json",
        "conformance-report.json",
        "gate-report.json",
    ):
        path = release_root / name
        path.write_text("{}\n", encoding="utf-8")
        other_files[name] = path
    release = AdapterReleaseManifest(
        release_id="release-r1",
        robot_id="wheeltec",
        discovery_id="discovery-1",
        target_fingerprint_sha256="8" * 64,
        bundle_manifest="adapter/adapter-manifest.json",
        bundle_manifest_sha256=sha256_file(bundle_path),
        adapter_package="adapter/adapter.py",
        adapter_package_sha256=sha256_file(entrypoint),
        adapter_files=[
            PublishedAdapterFile(
                path="adapter/adapter.py",
                sha256=sha256_file(entrypoint),
                role="ENTRYPOINT",
            )
        ],
        tool_catalog="tool-catalog.json",
        tool_catalog_sha256=sha256_file(other_files["tool-catalog.json"]),
        state_graph="state-graph.json",
        state_graph_sha256=sha256_file(other_files["state-graph.json"]),
        conformance_report="conformance-report.json",
        conformance_report_sha256=sha256_file(other_files["conformance-report.json"]),
        gate_report="gate-report.json",
        gate_report_sha256=sha256_file(other_files["gate-report.json"]),
        published_at=NOW,
    )
    manifest_path = release_root / "manifest.json"
    manifest_path.write_text(release.model_dump_json(indent=2) + "\n", encoding="utf-8")
    context = LocatedRuntimeContext(
        target_id="wheeltec-target",
        robot_id="wheeltec",
        workspace_id="workspace-1",
        workspace_sha256="a" * 64,
        adapter_entrypoint=str(entrypoint.resolve()),
    )
    launcher = tmp_path / "sandbox-launcher"
    launcher.write_text("#!/bin/sh\n", encoding="utf-8")
    sandbox_digest = target_sandbox_profile_sha256(launcher, context.sandbox_budget)
    request = TargetDescribeRequest(
        request_id="execute-describe-wheeltec",
        target_id="wheeltec-target",
        robot_id="wheeltec",
        collector_id=pin.descriptor.collector_id,
        release_id="release-r1",
        release_manifest_sha256=sha256_file(manifest_path),
        bundle_manifest_sha256=sha256_file(bundle_path),
        runtime_context_sha256=context.canonical_sha256(),
        sandbox_profile_sha256=sandbox_digest,
        nonce="6" * 32,
        issued_at=NOW,
        expires_at=NOW + timedelta(minutes=1),
    )
    runner = _DescribeRunner({"operations": {"ros.topic.list": "adapter.py"}})

    result = execute_target_describe(
        request,
        context=context,
        release_root=release_root,
        sandbox_launcher=launcher,
        service=service,
        runner=runner,
        now=NOW + timedelta(seconds=1),
    )

    assert result.output.operations == {"ros.topic.list": "adapter.py"}
    assert len(runner.commands) == 1
    assert runner.commands[0][-2:] == [str(entrypoint.resolve()), "describe"]
    assert all("invoke" not in item for command in runner.commands for item in command)
    verify_target_describe_attestation(
        result.attestation,
        request=request,
        pin=pin,
        expected_operations=result.output.operations,
        output=result.output,
        now=NOW + timedelta(seconds=2),
    )

    entrypoint.write_text("# tampered\n", encoding="utf-8")
    with pytest.raises(ValueError, match="file digest mismatch"):
        execute_target_describe(
            request,
            context=context,
            release_root=release_root,
            sandbox_launcher=launcher,
            service=service,
            runner=runner,
            now=NOW + timedelta(seconds=2),
        )
    entrypoint.write_text("# frozen adapter\n", encoding="utf-8")
    (release_root / "undeclared.txt").write_text("unexpected", encoding="utf-8")
    with pytest.raises(ValueError, match="file set differs"):
        execute_target_describe(
            request,
            context=context,
            release_root=release_root,
            sandbox_launcher=launcher,
            service=service,
            runner=runner,
            now=NOW + timedelta(seconds=2),
        )
