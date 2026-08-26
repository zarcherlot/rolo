from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Literal
from xml.etree import ElementTree

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rolo.core.persistence import atomic_write_text
from rolo.targets.bootstrap import TargetArchitecture, TargetInstallIndex, TargetPlatformFacts
from rolo.targets.bootstrap_execution import (
    TargetBootstrapExecutionOperation,
    TargetBootstrapExecutionRequest,
    TargetBootstrapExecutionResult,
)
from rolo.targets.credentials import CredentialPurpose
from rolo.targets.executor import (
    TargetExecutionErrorCode,
    TargetExecutionStatus,
    TargetExecutor,
    TargetInspectionRequest,
    TargetInspectionResult,
    TargetInspectionTool,
)
from rolo.targets.models import TargetConnectionProfile, TargetProfile, TargetTransport

_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$"
_SHA256_PATTERN = r"^[0-9a-f]{64}$"


def _canonical_sha256(value: object) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class W10AutomatedResult(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"


class W10AcceptanceGateId(str, Enum):
    PROVISIONING_TYPED_INSPECTION = "PROVISIONING_TYPED_INSPECTION"
    BOOTSTRAP_CAPABILITY_INSPECTION = "BOOTSTRAP_CAPABILITY_INSPECTION"
    RUNTIME_TYPED_INSPECTION = "RUNTIME_TYPED_INSPECTION"
    RUNTIME_INSTALLATION_BINDING = "RUNTIME_INSTALLATION_BINDING"
    REAL_SSH_TEST_REPORT = "REAL_SSH_TEST_REPORT"
    PLATFORM_BINDING = "PLATFORM_BINDING"


class W10RealSshAcceptanceRequest(BaseModel):
    """Operator-supplied immutable bindings for one real-target acceptance run."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-w10-real-ssh-acceptance-request/v1"] = (
        "rolo-w10-real-ssh-acceptance-request/v1"
    )
    target_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    environment_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    expected_architecture: TargetArchitecture
    os_image_sha256: str = Field(pattern=_SHA256_PATTERN)
    package_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    package_manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    acceptance_suite_sha256: str = Field(pattern=_SHA256_PATTERN)
    test_report_sha256: str = Field(pattern=_SHA256_PATTERN)
    timeout_s: float = Field(default=20.0, ge=1.0, le=300.0)

    def canonical_sha256(self) -> str:
        return _canonical_sha256(self)


class W10ObservedPlatform(BaseModel):
    model_config = ConfigDict(extra="forbid")

    machine: str = Field(min_length=1, max_length=64)
    os: str = Field(min_length=1, max_length=64)
    os_release: str = Field(min_length=1, max_length=256)
    python: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    python_executable: str = Field(min_length=1, max_length=4096)
    uid: int | None = Field(default=None, ge=0)

    @property
    def normalized_architecture(self) -> TargetArchitecture | None:
        machine = self.machine.casefold().replace("-", "_")
        if machine in {"amd64", "x86_64"}:
            return TargetArchitecture.X86_64
        if machine in {"arm64", "aarch64"}:
            return TargetArchitecture.AARCH64
        return None


class W10ObservedRuntimeInstallation(BaseModel):
    """Path-free projection of the target-validated active runtime index."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-w10-observed-runtime-installation/v1"] = (
        "rolo-w10-observed-runtime-installation/v1"
    )
    current_package_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    current_package_version: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$")
    current_manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    previous_package_id: str | None = Field(default=None, pattern=_IDENTIFIER_PATTERN)
    previous_package_version: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$",
    )
    previous_manifest_sha256: str | None = Field(
        default=None,
        pattern=_SHA256_PATTERN,
    )

    @model_validator(mode="after")
    def bind_previous_release(self) -> W10ObservedRuntimeInstallation:
        previous = (
            self.previous_package_id,
            self.previous_package_version,
            self.previous_manifest_sha256,
        )
        if any(value is not None for value in previous) and not all(
            value is not None for value in previous
        ):
            raise ValueError("W10 previous runtime identity must be complete")
        return self


class W10TestReportSummary(BaseModel):
    """Bounded aggregate extracted from a real pytest JUnit XML report."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-w10-test-report-summary/v1"] = "rolo-w10-test-report-summary/v1"
    format: Literal["JUNIT_XML"] = "JUNIT_XML"
    report_sha256: str = Field(pattern=_SHA256_PATTERN)
    test_count: int = Field(ge=0, le=1_000_000)
    failure_count: int = Field(ge=0, le=1_000_000)
    error_count: int = Field(ge=0, le=1_000_000)
    skipped_count: int = Field(ge=0, le=1_000_000)
    duration_s: float = Field(ge=0.0, le=31_536_000.0)
    minimum_executed_tests: Literal[4] = 4
    automated_result: W10AutomatedResult

    @model_validator(mode="after")
    def bind_counts_and_result(self) -> W10TestReportSummary:
        if self.failure_count + self.error_count + self.skipped_count > self.test_count:
            raise ValueError("W10 JUnit outcome counts exceed the test count")
        expected = (
            W10AutomatedResult.PASSED
            if self.test_count - self.skipped_count >= self.minimum_executed_tests
            and self.failure_count == 0
            and self.error_count == 0
            else W10AutomatedResult.FAILED
        )
        if self.automated_result != expected:
            raise ValueError("W10 JUnit aggregate result does not match its counts")
        return self


class W10InspectionEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gate_id: W10AcceptanceGateId
    credential_purpose: CredentialPurpose | None = None
    automated_result: W10AutomatedResult
    request_sha256: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    result_sha256: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    error_code: str | None = Field(default=None, min_length=1, max_length=128)
    started_at: datetime
    finished_at: datetime

    @model_validator(mode="after")
    def require_consistent_result(self) -> W10InspectionEvidence:
        if self.finished_at < self.started_at:
            raise ValueError("W10 gate finish time cannot precede start time")
        if self.automated_result == W10AutomatedResult.PASSED and self.error_code:
            raise ValueError("passed W10 gate cannot contain an error code")
        if self.automated_result == W10AutomatedResult.FAILED and not self.error_code:
            raise ValueError("failed W10 gate requires an error code")
        if self.gate_id == W10AcceptanceGateId.PLATFORM_BINDING:
            if self.credential_purpose is not None:
                raise ValueError("platform binding gate cannot select an SSH identity")
            if self.request_sha256 is not None or self.result_sha256 is not None:
                raise ValueError("platform binding gate cannot bind a synthetic request")
        elif self.gate_id == W10AcceptanceGateId.REAL_SSH_TEST_REPORT:
            if self.credential_purpose is not None or self.request_sha256 is not None:
                raise ValueError("test report gate cannot select an SSH identity or request")
            if self.result_sha256 is None:
                raise ValueError("test report gate requires its report digest")
        elif (
            self.credential_purpose is None
            or self.request_sha256 is None
            or self.result_sha256 is None
        ):
            raise ValueError("W10 inspection gate requires identity and request/result digests")
        return self


class W10RealSshAcceptanceReceipt(BaseModel):
    """Secret-closed automated evidence; deliberately not a production acceptance."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-w10-real-ssh-acceptance-receipt/v1"] = (
        "rolo-w10-real-ssh-acceptance-receipt/v1"
    )
    request: W10RealSshAcceptanceRequest
    request_sha256: str = Field(pattern=_SHA256_PATTERN)
    target_profile_sha256: str = Field(pattern=_SHA256_PATTERN)
    connection_profile_sha256: str = Field(pattern=_SHA256_PATTERN)
    endpoint_sha256: str = Field(pattern=_SHA256_PATTERN)
    known_hosts_sha256: str = Field(pattern=_SHA256_PATTERN)
    pinned_host_key_sha256: str = Field(pattern=r"^SHA256:[A-Za-z0-9+/]{43}$")
    identity_binding_sha256: dict[CredentialPurpose, str]
    provisioning_platform: W10ObservedPlatform | None = None
    runtime_platform: W10ObservedPlatform | None = None
    runtime_installation: W10ObservedRuntimeInstallation | None = None
    bootstrap_capabilities_sha256: str | None = Field(
        default=None,
        pattern=_SHA256_PATTERN,
    )
    test_report: W10TestReportSummary
    gates: list[W10InspectionEvidence] = Field(min_length=6, max_length=6)
    automated_result: W10AutomatedResult
    matrix_status: Literal["NOT_VERIFIED"] = "NOT_VERIFIED"
    manual_review_required: Literal[True] = True
    production_ready: Literal[False] = False
    started_at: datetime
    finished_at: datetime

    @model_validator(mode="after")
    def bind_receipt(self) -> W10RealSshAcceptanceReceipt:
        if self.request_sha256 != self.request.canonical_sha256():
            raise ValueError("W10 receipt request digest mismatch")
        if self.request.test_report_sha256 != self.test_report.report_sha256:
            raise ValueError("W10 receipt test report digest mismatch")
        expected_purposes = {
            CredentialPurpose.SSH_PROVISIONING,
            CredentialPurpose.SSH_BOOTSTRAP,
            CredentialPurpose.SSH_RUNTIME,
        }
        if set(self.identity_binding_sha256) != expected_purposes:
            raise ValueError("W10 receipt requires all three SSH identity bindings")
        if any(
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
            for value in self.identity_binding_sha256.values()
        ):
            raise ValueError("W10 receipt identity binding digest is invalid")
        expected_gates = set(W10AcceptanceGateId)
        if {gate.gate_id for gate in self.gates} != expected_gates:
            raise ValueError("W10 receipt must contain each automated gate exactly once")
        expected_gate_purposes = {
            W10AcceptanceGateId.PROVISIONING_TYPED_INSPECTION: (CredentialPurpose.SSH_PROVISIONING),
            W10AcceptanceGateId.BOOTSTRAP_CAPABILITY_INSPECTION: (CredentialPurpose.SSH_BOOTSTRAP),
            W10AcceptanceGateId.RUNTIME_TYPED_INSPECTION: CredentialPurpose.SSH_RUNTIME,
            W10AcceptanceGateId.RUNTIME_INSTALLATION_BINDING: (CredentialPurpose.SSH_RUNTIME),
            W10AcceptanceGateId.REAL_SSH_TEST_REPORT: None,
            W10AcceptanceGateId.PLATFORM_BINDING: None,
        }
        if any(
            gate.credential_purpose != expected_gate_purposes[gate.gate_id] for gate in self.gates
        ):
            raise ValueError("W10 receipt gate is bound to the wrong SSH identity")
        all_passed = all(gate.automated_result == W10AutomatedResult.PASSED for gate in self.gates)
        if all_passed != (self.automated_result == W10AutomatedResult.PASSED):
            raise ValueError("W10 receipt aggregate result does not match its gates")
        if all_passed and (
            self.provisioning_platform is None
            or self.runtime_platform is None
            or self.runtime_installation is None
            or self.bootstrap_capabilities_sha256 is None
            or self.test_report.automated_result != W10AutomatedResult.PASSED
        ):
            raise ValueError("passed W10 receipt requires all parsed platform evidence")
        if self.finished_at < self.started_at:
            raise ValueError("W10 receipt finish time cannot precede start time")
        return self

    def canonical_sha256(self) -> str:
        return _canonical_sha256(self)


def _read_bounded_regular_file(path: Path, *, maximum_size: int) -> bytes:
    expanded = path.expanduser()
    if expanded.is_symlink():
        raise ValueError("W10 evidence input must not be a symbolic link")
    resolved = expanded.resolve()
    if not resolved.is_file():
        raise ValueError("W10 evidence input must be a regular file")
    if resolved.stat().st_size > maximum_size:
        raise ValueError("W10 evidence input exceeds its size limit")
    return resolved.read_bytes()


def w10_acceptance_file_sha256(
    path: Path,
    *,
    maximum_size: int = 8 * 1024 * 1024,
) -> str:
    return hashlib.sha256(_read_bounded_regular_file(path, maximum_size=maximum_size)).hexdigest()


def _junit_integer(value: str | None, *, field_name: str) -> int:
    if value is None or not value.isascii() or not value.isdigit():
        raise ValueError(f"W10 JUnit report requires integer {field_name}")
    parsed = int(value)
    if parsed > 1_000_000:
        raise ValueError(f"W10 JUnit {field_name} exceeds its limit")
    return parsed


def parse_w10_junit_report(path: Path) -> W10TestReportSummary:
    raw = _read_bounded_regular_file(path, maximum_size=8 * 1024 * 1024)
    upper = raw.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise ValueError("W10 JUnit report cannot contain DTD or entity declarations")
    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError as exc:
        raise ValueError("W10 JUnit report is invalid XML") from exc
    if root.tag not in {"testsuite", "testsuites"}:
        raise ValueError("W10 JUnit report root must be testsuite or testsuites")
    attributes = root.attrib
    if root.tag == "testsuites" and "tests" not in attributes:
        suites = list(root.findall("./testsuite"))
        if not suites:
            raise ValueError("W10 JUnit report contains no test suites")
        counts = {
            name: sum(_junit_integer(suite.get(name), field_name=name) for suite in suites)
            for name in ("tests", "failures", "errors", "skipped")
        }
        try:
            duration_s = sum(float(suite.get("time", "0")) for suite in suites)
        except ValueError as exc:
            raise ValueError("W10 JUnit report has an invalid duration") from exc
    else:
        counts = {
            name: _junit_integer(attributes.get(name), field_name=name)
            for name in ("tests", "failures", "errors", "skipped")
        }
        try:
            duration_s = float(attributes.get("time", "0"))
        except ValueError as exc:
            raise ValueError("W10 JUnit report has an invalid duration") from exc
    if not 0.0 <= duration_s <= 31_536_000.0:
        raise ValueError("W10 JUnit report duration is outside its limit")
    automated_result = (
        W10AutomatedResult.PASSED
        if counts["tests"] - counts["skipped"] >= 4
        and counts["failures"] == 0
        and counts["errors"] == 0
        else W10AutomatedResult.FAILED
    )
    return W10TestReportSummary(
        report_sha256=hashlib.sha256(raw).hexdigest(),
        test_count=counts["tests"],
        failure_count=counts["failures"],
        error_count=counts["errors"],
        skipped_count=counts["skipped"],
        duration_s=duration_s,
        automated_result=automated_result,
    )


def _identity_binding_sha256(
    connection: TargetConnectionProfile,
    purpose: CredentialPurpose,
) -> str:
    if purpose == CredentialPurpose.SSH_PROVISIONING:
        user = connection.provisioning_user
        credential_ref = connection.provisioning_credential_ref
    elif purpose == CredentialPurpose.SSH_BOOTSTRAP:
        user = connection.user
        credential_ref = connection.credential_ref
    elif purpose == CredentialPurpose.SSH_RUNTIME:
        user = connection.runtime_user
        credential_ref = connection.runtime_credential_ref
    else:
        raise ValueError("unsupported W10 SSH credential purpose")
    if user is None or credential_ref is None:
        raise ValueError(f"W10 requires an explicit {purpose.value} identity")
    return _canonical_sha256(
        {
            "credential_purpose": purpose.value,
            "credential_ref_sha256": hashlib.sha256(credential_ref.encode("utf-8")).hexdigest(),
            "user": user,
        }
    )


def _inspection_evidence(
    *,
    gate_id: W10AcceptanceGateId,
    purpose: CredentialPurpose,
    request: TargetInspectionRequest,
    result: TargetInspectionResult,
    protocol_error: str | None = None,
) -> W10InspectionEvidence:
    error_code = protocol_error
    if result.status != TargetExecutionStatus.SUCCEEDED:
        error_code = (result.error_code or TargetExecutionErrorCode.PROTOCOL_ERROR).value
    return W10InspectionEvidence(
        gate_id=gate_id,
        credential_purpose=purpose,
        automated_result=(
            W10AutomatedResult.PASSED if error_code is None else W10AutomatedResult.FAILED
        ),
        request_sha256=request.canonical_sha256(),
        result_sha256=_canonical_sha256(result),
        error_code=error_code,
        started_at=result.started_at,
        finished_at=result.finished_at,
    )


def _runtime_installation_projection(
    index: TargetInstallIndex,
) -> W10ObservedRuntimeInstallation:
    current = index.current
    previous = index.previous
    return W10ObservedRuntimeInstallation(
        current_package_id=current.package_id,
        current_package_version=current.package_version,
        current_manifest_sha256=current.manifest_sha256,
        previous_package_id=previous.package_id if previous is not None else None,
        previous_package_version=(previous.package_version if previous is not None else None),
        previous_manifest_sha256=(previous.manifest_sha256 if previous is not None else None),
    )


def _runtime_status_error(
    request: TargetBootstrapExecutionRequest,
    result: TargetBootstrapExecutionResult,
    *,
    expected_package_id: str,
    expected_manifest_sha256: str,
) -> tuple[str | None, W10ObservedRuntimeInstallation | None]:
    if (
        result.request_id != request.request_id
        or result.request_sha256 != request.canonical_sha256()
        or result.target_id != request.target_id
        or result.package_id != request.package_id
        or result.manifest_sha256 != request.manifest_sha256
        or result.operation != TargetBootstrapExecutionOperation.STATUS
        or result.executor_kind.value != "SSH"
    ):
        return TargetExecutionErrorCode.PROTOCOL_ERROR.value, None
    if result.status != TargetExecutionStatus.SUCCEEDED:
        if result.transport_error_code is not None:
            return result.transport_error_code.value, None
        if result.bootstrap_error_code is not None:
            return result.bootstrap_error_code.value, None
        return TargetExecutionErrorCode.PROTOCOL_ERROR.value, None
    if result.install_index is None:
        return "RUNTIME_NOT_INSTALLED", None
    projection = _runtime_installation_projection(result.install_index)
    if (
        projection.current_package_id != expected_package_id
        or projection.current_manifest_sha256 != expected_manifest_sha256
    ):
        return "RUNTIME_PACKAGE_MISMATCH", projection
    return None, projection


class W10RealSshAcceptanceRunner:
    def __init__(
        self,
        *,
        target: TargetProfile,
        connection: TargetConnectionProfile,
        executor_factory: Callable[[CredentialPurpose], TargetExecutor],
    ) -> None:
        if target.transport != TargetTransport.SSH:
            raise ValueError("W10 real SSH acceptance requires an SSH target")
        if target.connection_profile_id != connection.connection_profile_id:
            raise ValueError("W10 target and connection profile are not bound")
        if connection.expected_host_key_sha256 is None:
            raise ValueError("W10 acceptance requires an explicit host-key fingerprint")
        self._target = target
        self._connection = connection
        self._executor_factory = executor_factory
        for purpose in (
            CredentialPurpose.SSH_PROVISIONING,
            CredentialPurpose.SSH_BOOTSTRAP,
            CredentialPurpose.SSH_RUNTIME,
        ):
            _identity_binding_sha256(connection, purpose)

    @staticmethod
    def _request(
        *,
        request_id: str,
        tool: TargetInspectionTool,
        timeout_s: float,
    ) -> TargetInspectionRequest:
        return TargetInspectionRequest(
            request_id=request_id,
            tool=tool,
            timeout_s=timeout_s,
            max_stdout_bytes=64 * 1024,
            max_stderr_bytes=16 * 1024,
        )

    def run(
        self,
        request: W10RealSshAcceptanceRequest,
        *,
        test_report: W10TestReportSummary,
    ) -> W10RealSshAcceptanceReceipt:
        if request.target_id != self._target.target_id:
            raise ValueError("W10 acceptance request target mismatch")
        if request.test_report_sha256 != test_report.report_sha256:
            raise ValueError("W10 acceptance test report digest mismatch")
        short_digest = request.canonical_sha256()[:12]
        probe_specs = (
            (
                W10AcceptanceGateId.PROVISIONING_TYPED_INSPECTION,
                CredentialPurpose.SSH_PROVISIONING,
                TargetInspectionTool.PLATFORM,
            ),
            (
                W10AcceptanceGateId.BOOTSTRAP_CAPABILITY_INSPECTION,
                CredentialPurpose.SSH_BOOTSTRAP,
                TargetInspectionTool.RUNTIME_CAPABILITIES,
            ),
            (
                W10AcceptanceGateId.RUNTIME_TYPED_INSPECTION,
                CredentialPurpose.SSH_RUNTIME,
                TargetInspectionTool.PLATFORM,
            ),
        )
        evidence: list[W10InspectionEvidence] = []
        provisioning_platform: W10ObservedPlatform | None = None
        runtime_platform: W10ObservedPlatform | None = None
        runtime_installation: W10ObservedRuntimeInstallation | None = None
        bootstrap_capabilities_sha256: str | None = None
        results: list[TargetInspectionResult] = []
        executors = {
            purpose: self._executor_factory(purpose)
            for purpose in (
                CredentialPurpose.SSH_PROVISIONING,
                CredentialPurpose.SSH_BOOTSTRAP,
                CredentialPurpose.SSH_RUNTIME,
            )
        }

        for gate_id, purpose, tool in probe_specs:
            probe = self._request(
                request_id=f"w10-{short_digest}-{purpose.value.casefold().replace('_', '-')}",
                tool=tool,
                timeout_s=request.timeout_s,
            )
            result = executors[purpose].inspect(probe)
            results.append(result)
            protocol_error: str | None = None
            if (
                result.request_id != probe.request_id
                or result.request_sha256 != probe.canonical_sha256()
                or result.executor_kind.value != "SSH"
            ):
                protocol_error = TargetExecutionErrorCode.PROTOCOL_ERROR.value
            elif result.status == TargetExecutionStatus.SUCCEEDED:
                try:
                    if tool == TargetInspectionTool.PLATFORM:
                        platform = W10ObservedPlatform.model_validate_json(result.stdout)
                        if purpose == CredentialPurpose.SSH_PROVISIONING:
                            provisioning_platform = platform
                        else:
                            runtime_platform = platform
                    else:
                        capabilities = TargetPlatformFacts.model_validate_json(result.stdout)
                        bootstrap_capabilities_sha256 = _canonical_sha256(capabilities)
                except ValueError:
                    protocol_error = TargetExecutionErrorCode.PROTOCOL_ERROR.value
            evidence.append(
                _inspection_evidence(
                    gate_id=gate_id,
                    purpose=purpose,
                    request=probe,
                    result=result,
                    protocol_error=protocol_error,
                )
            )

        status_request = TargetBootstrapExecutionRequest(
            request_id=f"w10-{short_digest}-runtime-installation",
            operation=TargetBootstrapExecutionOperation.STATUS,
            target_id=request.target_id,
            package_id=request.package_id,
            manifest_sha256=request.package_manifest_sha256,
            timeout_s=max(10.0, request.timeout_s),
        )
        status_started_at = datetime.now(timezone.utc)
        status_result = executors[CredentialPurpose.SSH_RUNTIME].execute_bootstrap(status_request)
        status_finished_at = datetime.now(timezone.utc)
        status_error, runtime_installation = _runtime_status_error(
            status_request,
            status_result,
            expected_package_id=request.package_id,
            expected_manifest_sha256=request.package_manifest_sha256,
        )
        evidence.append(
            W10InspectionEvidence(
                gate_id=W10AcceptanceGateId.RUNTIME_INSTALLATION_BINDING,
                credential_purpose=CredentialPurpose.SSH_RUNTIME,
                automated_result=(
                    W10AutomatedResult.PASSED if status_error is None else W10AutomatedResult.FAILED
                ),
                request_sha256=status_request.canonical_sha256(),
                result_sha256=_canonical_sha256(status_result),
                error_code=status_error,
                started_at=status_started_at,
                finished_at=status_finished_at,
            )
        )

        report_error: str | None = None
        if test_report.automated_result != W10AutomatedResult.PASSED:
            report_error = (
                "TEST_REPORT_FAILED"
                if test_report.failure_count or test_report.error_count
                else "TEST_REPORT_INSUFFICIENT_EXECUTION"
            )
        now = datetime.now(timezone.utc)
        started_at = min(
            [item.started_at for item in results] + [status_started_at],
            default=now,
        )
        finished_at = max(
            [item.finished_at for item in results] + [status_finished_at],
            default=now,
        )
        evidence.append(
            W10InspectionEvidence(
                gate_id=W10AcceptanceGateId.REAL_SSH_TEST_REPORT,
                automated_result=(
                    W10AutomatedResult.PASSED if report_error is None else W10AutomatedResult.FAILED
                ),
                result_sha256=test_report.report_sha256,
                error_code=report_error,
                started_at=started_at,
                finished_at=finished_at,
            )
        )

        platform_error: str | None = None
        if provisioning_platform is None or runtime_platform is None:
            platform_error = "PLATFORM_EVIDENCE_MISSING"
        elif (
            provisioning_platform.machine.casefold() != runtime_platform.machine.casefold()
            or provisioning_platform.os.casefold() != runtime_platform.os.casefold()
            or provisioning_platform.os_release != runtime_platform.os_release
        ):
            platform_error = "PLATFORM_EVIDENCE_DIVERGED"
        elif runtime_platform.normalized_architecture != request.expected_architecture:
            platform_error = "PLATFORM_ARCHITECTURE_MISMATCH"
        evidence.append(
            W10InspectionEvidence(
                gate_id=W10AcceptanceGateId.PLATFORM_BINDING,
                automated_result=(
                    W10AutomatedResult.PASSED
                    if platform_error is None
                    else W10AutomatedResult.FAILED
                ),
                error_code=platform_error,
                started_at=started_at,
                finished_at=finished_at,
            )
        )
        automated_result = (
            W10AutomatedResult.PASSED
            if all(item.automated_result == W10AutomatedResult.PASSED for item in evidence)
            else W10AutomatedResult.FAILED
        )
        connection = self._connection
        return W10RealSshAcceptanceReceipt(
            request=request,
            request_sha256=request.canonical_sha256(),
            target_profile_sha256=self._target.canonical_sha256(),
            connection_profile_sha256=connection.canonical_sha256(),
            endpoint_sha256=_canonical_sha256({"host": connection.host, "port": connection.port}),
            known_hosts_sha256=w10_acceptance_file_sha256(
                Path(connection.known_hosts_path),
                maximum_size=4 * 1024 * 1024,
            ),
            pinned_host_key_sha256=connection.expected_host_key_sha256,
            identity_binding_sha256={
                purpose: _identity_binding_sha256(connection, purpose)
                for purpose in (
                    CredentialPurpose.SSH_PROVISIONING,
                    CredentialPurpose.SSH_BOOTSTRAP,
                    CredentialPurpose.SSH_RUNTIME,
                )
            },
            provisioning_platform=provisioning_platform,
            runtime_platform=runtime_platform,
            runtime_installation=runtime_installation,
            bootstrap_capabilities_sha256=bootstrap_capabilities_sha256,
            test_report=test_report,
            gates=evidence,
            automated_result=automated_result,
            started_at=started_at,
            finished_at=finished_at,
        )


def write_w10_real_ssh_acceptance_receipt(
    path: Path,
    receipt: W10RealSshAcceptanceReceipt,
) -> None:
    expanded = path.expanduser()
    if expanded.is_symlink():
        raise ValueError("W10 acceptance receipt cannot overwrite a symbolic link")
    destination = expanded.resolve()
    atomic_write_text(
        destination,
        json.dumps(
            receipt.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
