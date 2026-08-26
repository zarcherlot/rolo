from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import typer
from pydantic import ValidationError

from rolo.commands.common import emit
from rolo.targets.adapter_release_activation import AdapterReleaseActivationRequest
from rolo.targets.adapter_release_reconciliation import AdapterReleaseStatusRequest
from rolo.targets.adapter_release_transfer import AdapterReleaseStageRequest
from rolo.targets.bootstrap_execution import (
    TargetBootstrapExecutionOperation,
    TargetBootstrapExecutionRequest,
)
from rolo.targets.deployment_authorization import DeploymentAuthorizationKeyRegistry
from rolo.targets.enrollment import TargetEnrollmentOperation, TargetEnrollmentRequest
from rolo.targets.evidence_v4 import TargetEvidenceCollectionRequestV4
from rolo.targets.executor import LocalTargetExecutor, TargetInspectionRequest
from rolo.targets.runtime_deployment import (
    AdapterReleaseDescribeRequest,
    TargetProjectEvidenceRequest,
)
from rolo.targets.source_discovery import TargetSourceDiscoveryRequest

MAX_INSPECTION_REQUEST_BYTES = 64 * 1024
MAX_BOOTSTRAP_EXECUTION_REQUEST_BYTES = 64 * 1024
MAX_ENROLLMENT_REQUEST_BYTES = 64 * 1024
MAX_EVIDENCE_V4_REQUEST_BYTES = 128 * 1024
MAX_ADAPTER_RELEASE_STAGE_REQUEST_BYTES = 64 * 1024
MAX_ADAPTER_RELEASE_ACTIVATION_REQUEST_BYTES = 256 * 1024
MAX_ADAPTER_RELEASE_DESCRIBE_REQUEST_BYTES = 128 * 1024
MAX_ADAPTER_RELEASE_STATUS_REQUEST_BYTES = 64 * 1024
MAX_PROJECT_EVIDENCE_REQUEST_BYTES = 256 * 1024
MAX_SOURCE_DISCOVERY_REQUEST_BYTES = 256 * 1024

target_executor_app = typer.Typer(help="Fixed target-side executor protocol for controller SSH.")


def _authorized_executor() -> LocalTargetExecutor:
    pin_root = Path(
        os.environ.get(
            "ROLO_DEPLOYMENT_AUTHORIZATION_PIN_ROOT",
            str(Path.home() / ".local" / "share" / "rolo" / "authorization-pins"),
        )
    )
    return LocalTargetExecutor(
        deployment_authorization_registry=DeploymentAuthorizationKeyRegistry(pin_root),
        require_runtime_evidence_authorization=True,
    )


def _inspection_request() -> TargetInspectionRequest:
    payload = sys.stdin.buffer.read(MAX_INSPECTION_REQUEST_BYTES + 1)
    if len(payload) > MAX_INSPECTION_REQUEST_BYTES:
        raise typer.BadParameter("target inspection request exceeded its size limit")
    try:
        return TargetInspectionRequest.model_validate_json(payload)
    except ValidationError as exc:
        detail = json.dumps(
            exc.errors(include_input=False),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        raise typer.BadParameter(f"invalid target inspection request: {detail}") from exc


def _bootstrap_request() -> TargetBootstrapExecutionRequest:
    payload = sys.stdin.buffer.read(MAX_BOOTSTRAP_EXECUTION_REQUEST_BYTES + 1)
    if len(payload) > MAX_BOOTSTRAP_EXECUTION_REQUEST_BYTES:
        raise typer.BadParameter("target bootstrap request exceeded its size limit")
    try:
        return TargetBootstrapExecutionRequest.model_validate_json(payload)
    except ValidationError as exc:
        detail = json.dumps(
            exc.errors(include_input=False),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        raise typer.BadParameter(f"invalid target bootstrap request: {detail}") from exc


def _enrollment_request() -> TargetEnrollmentRequest:
    payload = sys.stdin.buffer.read(MAX_ENROLLMENT_REQUEST_BYTES + 1)
    if len(payload) > MAX_ENROLLMENT_REQUEST_BYTES:
        raise typer.BadParameter("target enrollment request exceeded its size limit")
    try:
        return TargetEnrollmentRequest.model_validate_json(payload)
    except ValidationError as exc:
        detail = json.dumps(
            exc.errors(include_input=False),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        raise typer.BadParameter(f"invalid target enrollment request: {detail}") from exc


def _evidence_v4_request() -> TargetEvidenceCollectionRequestV4:
    payload = sys.stdin.buffer.read(MAX_EVIDENCE_V4_REQUEST_BYTES + 1)
    if len(payload) > MAX_EVIDENCE_V4_REQUEST_BYTES:
        raise typer.BadParameter("target evidence v4 request exceeded its size limit")
    try:
        return TargetEvidenceCollectionRequestV4.model_validate_json(payload)
    except ValidationError as exc:
        detail = json.dumps(
            exc.errors(include_input=False),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        raise typer.BadParameter(f"invalid target evidence v4 request: {detail}") from exc


def _adapter_release_stage_request() -> AdapterReleaseStageRequest:
    payload = sys.stdin.buffer.read(MAX_ADAPTER_RELEASE_STAGE_REQUEST_BYTES + 1)
    if len(payload) > MAX_ADAPTER_RELEASE_STAGE_REQUEST_BYTES:
        raise typer.BadParameter("adapter release stage request exceeded its size limit")
    try:
        return AdapterReleaseStageRequest.model_validate_json(payload)
    except ValidationError as exc:
        detail = json.dumps(
            exc.errors(include_input=False),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        raise typer.BadParameter(f"invalid adapter release stage request: {detail}") from exc


def _adapter_release_activation_request() -> AdapterReleaseActivationRequest:
    payload = sys.stdin.buffer.read(MAX_ADAPTER_RELEASE_ACTIVATION_REQUEST_BYTES + 1)
    if len(payload) > MAX_ADAPTER_RELEASE_ACTIVATION_REQUEST_BYTES:
        raise typer.BadParameter("adapter release activation request exceeded its size limit")
    try:
        return AdapterReleaseActivationRequest.model_validate_json(payload)
    except ValidationError as exc:
        detail = json.dumps(
            exc.errors(include_input=False),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        raise typer.BadParameter(
            f"invalid adapter release activation request: {detail}"
        ) from exc


def _adapter_release_describe_request() -> AdapterReleaseDescribeRequest:
    payload = sys.stdin.buffer.read(MAX_ADAPTER_RELEASE_DESCRIBE_REQUEST_BYTES + 1)
    if len(payload) > MAX_ADAPTER_RELEASE_DESCRIBE_REQUEST_BYTES:
        raise typer.BadParameter("adapter release describe request exceeded its size limit")
    try:
        return AdapterReleaseDescribeRequest.model_validate_json(payload)
    except ValidationError as exc:
        detail = json.dumps(
            exc.errors(include_input=False),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        raise typer.BadParameter(
            f"invalid adapter release describe request: {detail}"
        ) from exc


def _adapter_release_status_request() -> AdapterReleaseStatusRequest:
    payload = sys.stdin.buffer.read(MAX_ADAPTER_RELEASE_STATUS_REQUEST_BYTES + 1)
    if len(payload) > MAX_ADAPTER_RELEASE_STATUS_REQUEST_BYTES:
        raise typer.BadParameter("adapter release status request exceeded its size limit")
    try:
        return AdapterReleaseStatusRequest.model_validate_json(payload)
    except ValidationError as exc:
        detail = json.dumps(
            exc.errors(include_input=False),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        raise typer.BadParameter(f"invalid adapter release status request: {detail}") from exc


def _project_evidence_request() -> TargetProjectEvidenceRequest:
    payload = sys.stdin.buffer.read(MAX_PROJECT_EVIDENCE_REQUEST_BYTES + 1)
    if len(payload) > MAX_PROJECT_EVIDENCE_REQUEST_BYTES:
        raise typer.BadParameter("target project evidence request exceeded its size limit")
    try:
        return TargetProjectEvidenceRequest.model_validate_json(payload)
    except ValidationError as exc:
        detail = json.dumps(
            exc.errors(include_input=False),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        raise typer.BadParameter(f"invalid target project evidence request: {detail}") from exc


def _source_discovery_request() -> TargetSourceDiscoveryRequest:
    payload = sys.stdin.buffer.read(MAX_SOURCE_DISCOVERY_REQUEST_BYTES + 1)
    if len(payload) > MAX_SOURCE_DISCOVERY_REQUEST_BYTES:
        raise typer.BadParameter("target source discovery request exceeded its size limit")
    try:
        return TargetSourceDiscoveryRequest.model_validate_json(payload)
    except ValidationError as exc:
        detail = json.dumps(
            exc.errors(include_input=False),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        raise typer.BadParameter(f"invalid target source discovery request: {detail}") from exc


@target_executor_app.command("inspect")
def inspect() -> None:
    """Execute one strict read-only inspection request received on standard input."""
    emit(LocalTargetExecutor().inspect(_inspection_request()))


@target_executor_app.command("bootstrap")
def bootstrap() -> None:
    """Execute one strict target-local bootstrap transaction from standard input."""
    emit(_authorized_executor().execute_bootstrap(_bootstrap_request()))


@target_executor_app.command("enroll")
def enroll() -> None:
    """Execute one strict target-local collector enrollment transaction."""
    emit(LocalTargetExecutor().execute_enrollment(_enrollment_request()))


@target_executor_app.command("evidence-v4")
def evidence_v4() -> None:
    """Collect one strict target-local Ed25519 evidence bundle."""
    emit(LocalTargetExecutor().collect_evidence_v4(_evidence_v4_request()))


@target_executor_app.command("adapter-release-stage")
def adapter_release_stage() -> None:
    """Verify and atomically stage one signed frozen Adapter release."""

    emit(_authorized_executor().stage_adapter_release(_adapter_release_stage_request()))


@target_executor_app.command("adapter-release-activate")
def adapter_release_activate() -> None:
    """Activate or roll back a staged release under a signed Gate receipt and CAS."""

    emit(
        _authorized_executor().activate_adapter_release(
            _adapter_release_activation_request()
        )
    )


@target_executor_app.command("adapter-release-describe")
def adapter_release_describe() -> None:
    """Run only frozen release `describe` inside the configured production sandbox."""

    emit(_authorized_executor().describe_adapter_release(_adapter_release_describe_request()))


@target_executor_app.command("adapter-release-status")
def adapter_release_status() -> None:
    """Return a request-bound, verified release status without mutating target state."""

    emit(LocalTargetExecutor().status_adapter_release(_adapter_release_status_request()))


@target_executor_app.command("project-evidence")
def project_evidence() -> None:
    """Observe only explicitly declared project evidence files on this target."""

    emit(_authorized_executor().detect_project_evidence(_project_evidence_request()))


@target_executor_app.command("source-discovery")
def source_discovery() -> None:
    """Analyze bounded project source under a target-verifiable R2 grant."""

    emit(_authorized_executor().discover_source(_source_discovery_request()))


@target_executor_app.command("dispatch", hidden=True)
def dispatch() -> None:
    """Forced-command entrypoint allowing only installed read-only protocols."""

    original = os.environ.get("SSH_ORIGINAL_COMMAND", "")
    if original == "robotctl target-executor inspect":
        emit(LocalTargetExecutor().inspect(_inspection_request()))
        return
    if original == "robotctl target-executor bootstrap":
        request = _bootstrap_request()
        if request.operation not in {
            TargetBootstrapExecutionOperation.STATUS,
            TargetBootstrapExecutionOperation.HEALTH,
        }:
            raise typer.BadParameter(
                "forced target runtime credential permits only status and health"
            )
        emit(LocalTargetExecutor().execute_bootstrap(request))
        return
    if original == "robotctl target-executor enroll":
        request = _enrollment_request()
        if request.operation != TargetEnrollmentOperation.STATUS:
            raise typer.BadParameter(
                "forced target runtime credential permits only enrollment status"
            )
        emit(LocalTargetExecutor().execute_enrollment(request))
        return
    if original == "robotctl target-executor adapter-release-status":
        emit(LocalTargetExecutor().status_adapter_release(_adapter_release_status_request()))
        return
    if original == "robotctl target-executor project-evidence":
        emit(_authorized_executor().detect_project_evidence(_project_evidence_request()))
        return
    if original == "robotctl target-executor source-discovery":
        emit(_authorized_executor().discover_source(_source_discovery_request()))
        return
    if original == "robotctl target-executor evidence-v4":
        emit(_authorized_executor().collect_evidence_v4(_evidence_v4_request()))
        return
    raise typer.BadParameter("forced target runtime command is not permitted")
