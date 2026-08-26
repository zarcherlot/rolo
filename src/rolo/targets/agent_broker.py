from __future__ import annotations

import hashlib
import hmac
import json
import re
import shlex
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from rolo.core.persistence import atomic_write_text, interprocess_lock
from rolo.targets.adapt_jobs import (
    TargetAdaptJobSpecStore,
    TargetAdaptJobSubmission,
    TargetAdaptJobSubmissionService,
    build_target_adapt_job_spec,
    resolve_target_adapt_project_evidence_binding,
    resolve_target_adapt_runtime_evidence_binding,
    resolve_target_adapt_source_discovery_binding,
)
from rolo.targets.bootstrap_jobs import (
    TargetBootstrapJobSubmission,
    TargetBootstrapJobSubmissionResult,
    TargetBootstrapPublicSubmissionService,
)
from rolo.targets.connection_assessment import TargetDeploymentJobRunner
from rolo.targets.deployment_jobs import DeploymentJobRecord, DeploymentJobStore
from rolo.targets.deployment_tui import (
    TargetDeploymentTui,
    TargetDeploymentTuiPage,
    TargetDeploymentTuiRow,
    TargetDeploymentTuiSnapshot,
)
from rolo.targets.enrollment import CollectorEnrollmentPinRegistry
from rolo.targets.models import (
    ApprovalStatus,
    DeploymentCommand,
    DeploymentCommandKind,
    DeploymentJobState,
    InteractionSurface,
)
from rolo.targets.project_evidence_jobs import (
    TargetProjectEvidenceArtifactStore,
    TargetProjectEvidenceJobSubmission,
    TargetProjectEvidenceJobSubmissionResult,
    TargetProjectEvidenceSubmissionService,
)
from rolo.targets.registration import (
    TargetRegistrationService,
    target_connection_binding_sha256,
)
from rolo.targets.runtime_evidence_jobs import (
    TargetRuntimeEvidenceArtifactStore,
    TargetRuntimeEvidenceJobSubmission,
    TargetRuntimeEvidenceJobSubmissionResult,
    TargetRuntimeEvidenceSubmissionService,
)
from rolo.targets.runtime_rollback_jobs import (
    TargetRuntimeRollbackJobSubmissionResult,
    TargetRuntimeRollbackSubmission,
    TargetRuntimeRollbackSubmissionService,
)
from rolo.targets.source_discovery_jobs import (
    TargetSourceDiscoveryArtifactStore,
    TargetSourceDiscoveryJobSubmission,
    TargetSourceDiscoveryJobSubmissionResult,
    TargetSourceDiscoverySubmissionService,
)

_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$"
_JOB_ID = r"^deployment-[0-9a-f]{32}$"
_APPROVAL_ID = r"^approval-[0-9a-f]{32}$"
_SESSION_ID = r"^agent-session-[0-9a-f]{32}$"
_PRINCIPAL = r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,127}$"
_IDEMPOTENCY = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{7,127}$"
_SHA256 = r"^[0-9a-f]{64}$"
_PACKAGE_REF = r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}@[0-9a-f]{64}$"
_TARGET_WRITE = "target:write"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class SessionAgentAction(str, Enum):
    """Commands available to the model. Approval decisions are deliberately absent."""

    LIST_TARGETS = "LIST_TARGETS"
    SHOW_TARGET = "SHOW_TARGET"
    ASSESS_CONNECTION = "ASSESS_CONNECTION"
    SUBMIT_BOOTSTRAP = "SUBMIT_BOOTSTRAP"
    SUBMIT_RUNTIME_ROLLBACK = "SUBMIT_RUNTIME_ROLLBACK"
    SUBMIT_PROJECT_EVIDENCE = "SUBMIT_PROJECT_EVIDENCE"
    SUBMIT_SOURCE_DISCOVERY = "SUBMIT_SOURCE_DISCOVERY"
    SUBMIT_RUNTIME_EVIDENCE = "SUBMIT_RUNTIME_EVIDENCE"
    SUBMIT_ADAPT = "SUBMIT_ADAPT"
    GET_JOB = "GET_JOB"
    RUN_JOB = "RUN_JOB"
    CANCEL_JOB = "CANCEL_JOB"
    SHOW_APPROVAL = "SHOW_APPROVAL"
    LIST_BLOCKERS = "LIST_BLOCKERS"


class SessionAgentToolRisk(str, Enum):
    READ_ONLY = "READ_ONLY"
    JOB_CREATE = "JOB_CREATE"
    JOB_EXECUTE = "JOB_EXECUTE"
    JOB_CANCEL = "JOB_CANCEL"
    APPROVAL_HANDOFF = "APPROVAL_HANDOFF"


class SessionAgentToolDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: SessionAgentAction
    risk: SessionAgentToolRisk
    effect: Literal["NONE", "CONTROLLER_STATE", "TARGET_READ", "TARGET_MUTATION"]
    required_permission: Literal["target:write"] | None = None
    requires_external_approval: bool = False
    allowed_parameters: list[str] = Field(default_factory=list, max_length=16)


class SessionAgentToolCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-session-agent-tool-catalog/v2"] = (
        "rolo-session-agent-tool-catalog/v2"
    )
    tools: list[SessionAgentToolDescriptor] = Field(min_length=1, max_length=32)
    raw_shell_available: Literal[False] = False
    approval_decision_available: Literal[False] = False
    credential_material_available: Literal[False] = False
    model_generated_identity_available: Literal[False] = False
    raw_target_output_available: Literal[False] = False

    @model_validator(mode="after")
    def unique_actions(self) -> SessionAgentToolCatalog:
        actions = [tool.action for tool in self.tools]
        if actions != sorted(set(actions), key=lambda item: item.value):
            raise ValueError("Session Agent tools must use unique canonical action order")
        return self

    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.model_dump(mode="json"))


def build_session_agent_tool_catalog() -> SessionAgentToolCatalog:
    definitions = {
        SessionAgentAction.LIST_TARGETS: (
            SessionAgentToolRisk.READ_ONLY,
            "NONE",
            None,
            False,
            [],
        ),
        SessionAgentAction.SHOW_TARGET: (
            SessionAgentToolRisk.READ_ONLY,
            "NONE",
            None,
            False,
            ["target_id"],
        ),
        SessionAgentAction.ASSESS_CONNECTION: (
            SessionAgentToolRisk.JOB_CREATE,
            "TARGET_READ",
            _TARGET_WRITE,
            False,
            ["target_id", "active_probe"],
        ),
        SessionAgentAction.SUBMIT_BOOTSTRAP: (
            SessionAgentToolRisk.APPROVAL_HANDOFF,
            "CONTROLLER_STATE",
            _TARGET_WRITE,
            True,
            [
                "target_id",
                "package_ref",
                "approver_principal",
                "approval_ttl_s",
                "expect_current_present",
                "expected_current_manifest_sha256",
            ],
        ),
        SessionAgentAction.SUBMIT_RUNTIME_ROLLBACK: (
            SessionAgentToolRisk.APPROVAL_HANDOFF,
            "CONTROLLER_STATE",
            _TARGET_WRITE,
            True,
            [
                "target_id",
                "package_id",
                "expected_current_manifest_sha256",
                "expected_previous_manifest_sha256",
                "approver_principal",
                "approval_ttl_s",
            ],
        ),
        SessionAgentAction.SUBMIT_PROJECT_EVIDENCE: (
            SessionAgentToolRisk.APPROVAL_HANDOFF,
            "CONTROLLER_STATE",
            _TARGET_WRITE,
            True,
            ["target_id", "approver_principal", "approval_ttl_s"],
        ),
        SessionAgentAction.SUBMIT_SOURCE_DISCOVERY: (
            SessionAgentToolRisk.APPROVAL_HANDOFF,
            "CONTROLLER_STATE",
            _TARGET_WRITE,
            True,
            ["target_id", "approver_principal", "approval_ttl_s"],
        ),
        SessionAgentAction.SUBMIT_RUNTIME_EVIDENCE: (
            SessionAgentToolRisk.APPROVAL_HANDOFF,
            "CONTROLLER_STATE",
            _TARGET_WRITE,
            True,
            ["target_id", "approver_principal", "approval_ttl_s"],
        ),
        SessionAgentAction.SUBMIT_ADAPT: (
            SessionAgentToolRisk.JOB_CREATE,
            "CONTROLLER_STATE",
            _TARGET_WRITE,
            False,
            [
                "target_id",
                "active_probe",
                "project_evidence_job_id",
                "source_discovery_job_id",
                "runtime_evidence_job_id",
            ],
        ),
        SessionAgentAction.GET_JOB: (
            SessionAgentToolRisk.READ_ONLY,
            "NONE",
            None,
            False,
            ["job_id"],
        ),
        SessionAgentAction.RUN_JOB: (
            SessionAgentToolRisk.JOB_EXECUTE,
            "TARGET_MUTATION",
            _TARGET_WRITE,
            True,
            ["job_id"],
        ),
        SessionAgentAction.CANCEL_JOB: (
            SessionAgentToolRisk.JOB_CANCEL,
            "CONTROLLER_STATE",
            _TARGET_WRITE,
            False,
            ["job_id"],
        ),
        SessionAgentAction.SHOW_APPROVAL: (
            SessionAgentToolRisk.READ_ONLY,
            "NONE",
            None,
            False,
            ["approval_id"],
        ),
        SessionAgentAction.LIST_BLOCKERS: (
            SessionAgentToolRisk.READ_ONLY,
            "NONE",
            None,
            False,
            [],
        ),
    }
    tools = [
        SessionAgentToolDescriptor(
            action=action,
            risk=risk,
            effect=effect,
            required_permission=permission,
            requires_external_approval=approval,
            allowed_parameters=parameters,
        )
        for action, (risk, effect, permission, approval, parameters) in definitions.items()
    ]
    tools.sort(key=lambda item: item.action.value)
    return SessionAgentToolCatalog(tools=tools)


_COMMAND_FIELDS = {
    "target_id",
    "job_id",
    "approval_id",
    "package_ref",
    "package_id",
    "approver_principal",
    "active_probe",
    "project_evidence_job_id",
    "source_discovery_job_id",
    "runtime_evidence_job_id",
    "approval_ttl_s",
    "expect_current_present",
    "expected_current_manifest_sha256",
    "expected_previous_manifest_sha256",
}


class SessionAgentCommand(BaseModel):
    """One broker command selected by the model, not an authorization-bearing intent."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-session-agent-command/v1"] = "rolo-session-agent-command/v1"
    sequence: int = Field(ge=1, le=8)
    action: SessionAgentAction
    target_id: str | None = Field(default=None, pattern=_IDENTIFIER)
    job_id: str | None = Field(default=None, pattern=_JOB_ID)
    approval_id: str | None = Field(default=None, pattern=_APPROVAL_ID)
    package_ref: str | None = Field(default=None, pattern=_PACKAGE_REF)
    package_id: str | None = Field(default=None, pattern=_IDENTIFIER)
    approver_principal: str | None = Field(default=None, pattern=_PRINCIPAL)
    active_probe: Literal["none", "help", "runtime-readonly"] | None = None
    project_evidence_job_id: str | None = Field(default=None, pattern=_JOB_ID)
    source_discovery_job_id: str | None = Field(default=None, pattern=_JOB_ID)
    runtime_evidence_job_id: str | None = Field(default=None, pattern=_JOB_ID)
    approval_ttl_s: int | None = Field(default=None, ge=60, le=86_400)
    expect_current_present: bool | None = None
    expected_current_manifest_sha256: str | None = Field(
        default=None,
        pattern=_SHA256,
    )
    expected_previous_manifest_sha256: str | None = Field(
        default=None,
        pattern=_SHA256,
    )

    @model_validator(mode="after")
    def validate_action_parameters(self) -> SessionAgentCommand:
        descriptors = {
            tool.action: set(tool.allowed_parameters)
            for tool in build_session_agent_tool_catalog().tools
        }
        allowed = descriptors[self.action]
        supplied = {field for field in _COMMAND_FIELDS if getattr(self, field) is not None}
        disallowed = sorted(supplied - allowed)
        if disallowed:
            raise ValueError(f"{self.action.value} does not accept: {', '.join(disallowed)}")
        required: dict[SessionAgentAction, set[str]] = {
            SessionAgentAction.SHOW_TARGET: {"target_id"},
            SessionAgentAction.ASSESS_CONNECTION: {"target_id"},
            SessionAgentAction.SUBMIT_BOOTSTRAP: {
                "target_id",
                "package_ref",
                "approver_principal",
            },
            SessionAgentAction.SUBMIT_RUNTIME_ROLLBACK: {
                "target_id",
                "package_id",
                "expected_current_manifest_sha256",
                "expected_previous_manifest_sha256",
                "approver_principal",
            },
            SessionAgentAction.SUBMIT_PROJECT_EVIDENCE: {
                "target_id",
                "approver_principal",
            },
            SessionAgentAction.SUBMIT_SOURCE_DISCOVERY: {
                "target_id",
                "approver_principal",
            },
            SessionAgentAction.SUBMIT_RUNTIME_EVIDENCE: {
                "target_id",
                "approver_principal",
            },
            SessionAgentAction.SUBMIT_ADAPT: {"target_id"},
            SessionAgentAction.GET_JOB: {"job_id"},
            SessionAgentAction.RUN_JOB: {"job_id"},
            SessionAgentAction.CANCEL_JOB: {"job_id"},
            SessionAgentAction.SHOW_APPROVAL: {"approval_id"},
        }
        missing = sorted(required.get(self.action, set()) - supplied)
        if missing:
            raise ValueError(f"{self.action.value} requires: {', '.join(missing)}")
        if (
            self.action == SessionAgentAction.SUBMIT_BOOTSTRAP
            and self.expected_current_manifest_sha256 is not None
            and self.expect_current_present is not True
        ):
            raise ValueError(
                "expected_current_manifest_sha256 requires expect_current_present=true"
            )
        return self

    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.model_dump(mode="json", exclude_none=True))


class SessionAgentSubject(BaseModel):
    """Identity established by the Controller, never populated by the model."""

    model_config = ConfigDict(extra="forbid")

    principal: str = Field(pattern=_PRINCIPAL)
    permissions: list[str] = Field(default_factory=list, max_length=32)

    @field_validator("permissions")
    @classmethod
    def canonical_permissions(cls, values: list[str]) -> list[str]:
        permission = r"^[a-z][a-z0-9-]*:[a-z][a-z0-9-]*$"
        if any(re.fullmatch(permission, item) is None for item in values):
            raise ValueError("Session Agent permission is invalid")
        if values != sorted(set(values)):
            raise ValueError("Session Agent permissions must be unique and sorted")
        return values


class SessionAgentOpenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-session-agent-open-request/v1"] = (
        "rolo-session-agent-open-request/v1"
    )
    allowed_target_ids: list[str] = Field(min_length=1, max_length=1000)
    max_tool_calls: int = Field(default=4, ge=1, le=8)
    timeout_s: int = Field(default=120, ge=10, le=1800)
    conversation_sha256: str | None = Field(default=None, pattern=_SHA256)

    @field_validator("allowed_target_ids")
    @classmethod
    def canonical_targets(cls, values: list[str]) -> list[str]:
        if any(re.fullmatch(_IDENTIFIER, value) is None for value in values):
            raise ValueError("Session Agent allowed target ID is invalid")
        if values != sorted(set(values)):
            raise ValueError("Session Agent allowed target IDs must be unique and sorted")
        return values

    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.model_dump(mode="json"))


class SessionAgentTurnStatus(str, Enum):
    COMPLETED = "COMPLETED"
    SUBMITTED = "SUBMITTED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class SessionAgentCommandReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-session-agent-command-receipt/v1"] = (
        "rolo-session-agent-command-receipt/v1"
    )
    sequence: int = Field(ge=1, le=8)
    action: SessionAgentAction
    command_sha256: str = Field(pattern=_SHA256)
    status: SessionAgentTurnStatus
    summary: str = Field(min_length=1, max_length=1000)
    target_id: str | None = Field(default=None, pattern=_IDENTIFIER)
    job_id: str | None = Field(default=None, pattern=_JOB_ID)
    approval_id: str | None = Field(default=None, pattern=_APPROVAL_ID)
    deployment_command_sha256: str | None = Field(default=None, pattern=_SHA256)
    job_state: DeploymentJobState | None = None
    approval_status: ApprovalStatus | None = None
    canonical_cli: str | None = Field(default=None, max_length=8192)
    projection: TargetDeploymentTuiSnapshot | None = None

    @field_validator("summary")
    @classmethod
    def single_line_summary(cls, value: str) -> str:
        return " ".join(value.splitlines())


class SessionAgentSessionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-session-agent-session/v1"] = "rolo-session-agent-session/v1"
    session_id: str = Field(pattern=_SESSION_ID)
    open_request_sha256: str = Field(pattern=_SHA256)
    open_idempotency_sha256: str = Field(pattern=_SHA256)
    principal: str = Field(pattern=_PRINCIPAL)
    permissions: list[str] = Field(default_factory=list, max_length=32)
    allowed_target_ids: list[str] = Field(min_length=1, max_length=1000)
    catalog_sha256: str = Field(pattern=_SHA256)
    max_tool_calls: int = Field(ge=1, le=8)
    next_sequence: int = Field(default=1, ge=1, le=9)
    created_at: datetime
    expires_at: datetime
    cancelled_at: datetime | None = None
    receipts: list[SessionAgentCommandReceipt] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def bind_sequence_and_receipts(self) -> SessionAgentSessionRecord:
        if self.next_sequence != len(self.receipts) + 1:
            raise ValueError("Session Agent next sequence does not match its receipts")
        if len(self.receipts) > self.max_tool_calls:
            raise ValueError("Session Agent receipts exceed the action budget")
        if self.expires_at <= self.created_at:
            raise ValueError("Session Agent expiry must follow creation")
        return self


class SessionAgentSessionStore:
    """Persistent, secret-free session audit. One broker serializes each active session."""

    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().absolute()
        if self.root.is_symlink():
            raise ValueError("Session Agent store root cannot be a symbolic link")
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id: str) -> Path:
        if re.fullmatch(_SESSION_ID, session_id) is None:
            raise ValueError("invalid Session Agent session ID")
        return self.root / f"{session_id}.json"

    def _execution_guard_path(self, session_id: str) -> Path:
        if re.fullmatch(_SESSION_ID, session_id) is None:
            raise ValueError("invalid Session Agent session ID")
        return self.root / "execution-guards" / f"{session_id}.guard"

    @contextmanager
    def execution_lock(self, session_id: str) -> Iterator[None]:
        """Serialize commands across Controller workers without blocking cancellation."""
        with interprocess_lock(
            self._execution_guard_path(session_id),
            timeout_s=10.0,
            stale_after_s=1860.0,
        ):
            yield

    @staticmethod
    def _read_locked(path: Path) -> SessionAgentSessionRecord:
        if path.is_symlink() or not path.is_file():
            raise ValueError("Session Agent session is unavailable")
        if path.stat().st_size > 4 * 1024 * 1024:
            raise ValueError("Session Agent session exceeds its size limit")
        return SessionAgentSessionRecord.model_validate_json(path.read_text(encoding="utf-8"))

    def create(self, record: SessionAgentSessionRecord) -> SessionAgentSessionRecord:
        atomic_write_text(
            self._path(record.session_id),
            record.model_dump_json(indent=2) + "\n",
            require_absent=True,
        )
        return record

    def load(self, session_id: str) -> SessionAgentSessionRecord:
        path = self._path(session_id)
        with interprocess_lock(path):
            return self._read_locked(path)

    def save(self, record: SessionAgentSessionRecord) -> SessionAgentSessionRecord:
        path = self._path(record.session_id)
        if path.is_symlink() or not path.is_file():
            raise ValueError("Session Agent session is unavailable")
        atomic_write_text(path, record.model_dump_json(indent=2) + "\n")
        return record

    def mark_cancelled(
        self,
        session_id: str,
        *,
        cancelled_at: datetime,
    ) -> SessionAgentSessionRecord:
        """Persist cancellation without waiting for a long-running command lock."""
        path = self._path(session_id)
        with interprocess_lock(path):
            record = self._read_locked(path)
            if record.cancelled_at is None:
                record = record.model_copy(update={"cancelled_at": cancelled_at})
                atomic_write_text(
                    path,
                    record.model_dump_json(indent=2) + "\n",
                    acquire_lock=False,
                )
            return record

    def append_receipt(
        self,
        base: SessionAgentSessionRecord,
        receipt: SessionAgentCommandReceipt,
    ) -> SessionAgentSessionRecord:
        """Commit one serialized command while preserving concurrent cancellation."""
        path = self._path(base.session_id)
        with interprocess_lock(path):
            current = self._read_locked(path)
            if current.next_sequence != base.next_sequence or current.receipts != base.receipts:
                raise ValueError("Session Agent command state changed concurrently")
            updated = SessionAgentSessionRecord.model_validate(
                {
                    **current.model_dump(),
                    "next_sequence": current.next_sequence + 1,
                    "receipts": [
                        *(item.model_dump() for item in current.receipts),
                        receipt.model_dump(),
                    ],
                }
            )
            atomic_write_text(
                path,
                updated.model_dump_json(indent=2) + "\n",
                acquire_lock=False,
            )
            return updated


class _SessionAgentCancellation:
    """threading.Event-compatible cancellation with a persistent cross-process source."""

    def __init__(
        self,
        local_event: threading.Event,
        sessions: SessionAgentSessionStore,
        session_id: str,
    ) -> None:
        self.local_event = local_event
        self.sessions = sessions
        self.session_id = session_id

    def is_set(self) -> bool:
        if self.local_event.is_set():
            return True
        try:
            return self.sessions.load(self.session_id).cancelled_at is not None
        except (OSError, TimeoutError, ValueError):
            return True


class SessionAgentBroker:
    """Authenticated, bounded execution boundary outside the model process."""

    def __init__(
        self,
        *,
        sessions: SessionAgentSessionStore,
        registrations: TargetRegistrationService,
        jobs: DeploymentJobStore,
        adapt_specs: TargetAdaptJobSpecStore,
        bootstrap_submissions: TargetBootstrapPublicSubmissionService,
        job_runner: TargetDeploymentJobRunner,
        workbench: TargetDeploymentTui,
        rollback_submissions: TargetRuntimeRollbackSubmissionService | None = None,
        project_evidence_submissions: TargetProjectEvidenceSubmissionService | None = None,
        project_evidence_artifacts: TargetProjectEvidenceArtifactStore | None = None,
        source_discovery_submissions: TargetSourceDiscoverySubmissionService | None = None,
        source_discovery_artifacts: TargetSourceDiscoveryArtifactStore | None = None,
        runtime_evidence_submissions: TargetRuntimeEvidenceSubmissionService | None = None,
        runtime_evidence_artifacts: TargetRuntimeEvidenceArtifactStore | None = None,
        collector_pins: CollectorEnrollmentPinRegistry | None = None,
        now: Callable[[], datetime] = _utc_now,
        timer_factory: Callable[[float, Callable[[], None]], threading.Timer] = (threading.Timer),
    ) -> None:
        self.sessions = sessions
        self.registrations = registrations
        self.jobs = jobs
        self.adapt_specs = adapt_specs
        self.bootstrap_submissions = bootstrap_submissions
        self.rollback_submissions = rollback_submissions
        self.project_evidence_submissions = project_evidence_submissions
        self.project_evidence_artifacts = project_evidence_artifacts
        self.source_discovery_submissions = source_discovery_submissions
        self.source_discovery_artifacts = source_discovery_artifacts
        self.runtime_evidence_submissions = runtime_evidence_submissions
        self.runtime_evidence_artifacts = runtime_evidence_artifacts
        self.collector_pins = collector_pins
        self.job_runner = job_runner
        self.workbench = workbench
        self.now = now
        self.timer_factory = timer_factory
        self.catalog = build_session_agent_tool_catalog()
        self._session_locks: dict[str, threading.Lock] = {}
        self._session_locks_guard = threading.Lock()
        self._active_cancel_events: dict[str, set[threading.Event]] = {}
        self._active_cancel_events_guard = threading.Lock()

    def _lock_for(self, session_id: str) -> threading.Lock:
        with self._session_locks_guard:
            return self._session_locks.setdefault(session_id, threading.Lock())

    def open_session(
        self,
        subject: SessionAgentSubject,
        request: SessionAgentOpenRequest,
        *,
        idempotency_key: str,
    ) -> SessionAgentSessionRecord:
        if re.fullmatch(_IDEMPOTENCY, idempotency_key) is None:
            raise ValueError("Session Agent idempotency key is not canonical")
        for target_id in request.allowed_target_ids:
            self.registrations.load(target_id)
        created_at = self.now()
        identity_payload = {
            "principal": subject.principal,
            "idempotency_key": idempotency_key,
        }
        identity = _canonical_sha256(identity_payload)
        candidate = SessionAgentSessionRecord(
            session_id=f"agent-session-{identity[:32]}",
            open_request_sha256=request.canonical_sha256(),
            open_idempotency_sha256=hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest(),
            principal=subject.principal,
            permissions=subject.permissions,
            allowed_target_ids=request.allowed_target_ids,
            catalog_sha256=self.catalog.canonical_sha256(),
            max_tool_calls=request.max_tool_calls,
            created_at=created_at,
            expires_at=created_at + timedelta(seconds=request.timeout_s),
        )
        try:
            return self.sessions.create(candidate)
        except FileExistsError:
            existing = self.sessions.load(candidate.session_id)
            if (
                existing.principal != candidate.principal
                or existing.permissions != candidate.permissions
                or existing.open_request_sha256 != candidate.open_request_sha256
                or existing.open_idempotency_sha256 != candidate.open_idempotency_sha256
            ):
                raise ValueError(
                    "Session Agent idempotency key belongs to another open request"
                ) from None
            return existing

    @staticmethod
    def _assert_subject(
        record: SessionAgentSessionRecord,
        subject: SessionAgentSubject,
    ) -> None:
        if not hmac.compare_digest(record.principal, subject.principal):
            raise PermissionError("Session Agent session belongs to another principal")
        if record.permissions != subject.permissions:
            raise PermissionError("Session Agent permissions changed after session creation")

    def cancel_session(
        self,
        session_id: str,
        subject: SessionAgentSubject,
    ) -> SessionAgentSessionRecord:
        record = self.sessions.load(session_id)
        self._assert_subject(record, subject)
        record = self.sessions.mark_cancelled(session_id, cancelled_at=self.now())
        self._assert_subject(record, subject)
        with self._active_cancel_events_guard:
            active = tuple(self._active_cancel_events.get(session_id, ()))
        for event in active:
            event.set()
        return record

    def get_session(
        self,
        session_id: str,
        subject: SessionAgentSubject,
    ) -> SessionAgentSessionRecord:
        record = self.sessions.load(session_id)
        self._assert_subject(record, subject)
        return record

    def _descriptor(self, action: SessionAgentAction) -> SessionAgentToolDescriptor:
        return next(tool for tool in self.catalog.tools if tool.action == action)

    @staticmethod
    def _assert_target_allowed(
        record: SessionAgentSessionRecord,
        target_id: str,
    ) -> None:
        if target_id not in record.allowed_target_ids:
            raise PermissionError("Session Agent target is outside the session allowlist")

    def _target_for_command(self, command: SessionAgentCommand) -> str | None:
        if command.target_id is not None:
            return command.target_id
        if command.job_id is not None:
            return self.jobs.load_job(command.job_id).job.command.target_id
        if command.approval_id is not None:
            return self.jobs.load_approval_request(command.approval_id).target_id
        return None

    @staticmethod
    def _idempotency_key(
        record: SessionAgentSessionRecord,
        command: SessionAgentCommand,
    ) -> str:
        return (
            f"agent:{record.session_id.removeprefix('agent-session-')}:"
            f"{command.sequence}:{command.canonical_sha256()[:24]}"
        )

    @staticmethod
    def _safe_projection(
        snapshot: TargetDeploymentTuiSnapshot,
        allowed_target_ids: set[str],
    ) -> TargetDeploymentTuiSnapshot:
        rows: list[TargetDeploymentTuiRow] = []
        for row in snapshot.rows:
            fields = {field.name: field.value for field in row.fields}
            target_id = row.identity if row.kind == "TARGET" else fields.get("target")
            if target_id not in allowed_target_ids:
                continue
            rows.append(row.model_copy(update={"canonical_cli": None}))
        return snapshot.model_copy(update={"rows": rows[:100]})

    @staticmethod
    def _approval_for_job(
        jobs: DeploymentJobStore,
        job_id: str,
    ):  # type: ignore[no-untyped-def]
        requests = [
            request
            for request in jobs.list_approval_requests(limit=10_000)
            if request.job_id == job_id
        ]
        if not requests:
            return None, None
        if len(requests) != 1:
            raise ValueError("Session Agent found an ambiguous approval set")
        request = requests[0]
        return request, jobs.get_approval_decision(request.approval_id)

    @staticmethod
    def _receipt(
        command: SessionAgentCommand,
        *,
        status: SessionAgentTurnStatus,
        summary: str,
        target_id: str | None = None,
        job: DeploymentJobRecord | None = None,
        approval_id: str | None = None,
        approval_status: ApprovalStatus | None = None,
        canonical_cli: str | None = None,
        projection: TargetDeploymentTuiSnapshot | None = None,
    ) -> SessionAgentCommandReceipt:
        return SessionAgentCommandReceipt(
            sequence=command.sequence,
            action=command.action,
            command_sha256=command.canonical_sha256(),
            status=status,
            summary=summary,
            target_id=target_id,
            job_id=job.job.job_id if job is not None else command.job_id,
            approval_id=approval_id,
            deployment_command_sha256=(job.job.command_sha256 if job is not None else None),
            job_state=job.job.state if job is not None else None,
            approval_status=approval_status,
            canonical_cli=canonical_cli,
            projection=projection,
        )

    def _run_job(
        self,
        record: SessionAgentSessionRecord,
        command: SessionAgentCommand,
        *,
        now: datetime,
    ) -> SessionAgentCommandReceipt:
        assert command.job_id is not None
        current = self.jobs.load_job(command.job_id)
        target_id = current.job.command.target_id
        self._assert_target_allowed(record, target_id)
        approval, decision = self._approval_for_job(self.jobs, command.job_id)
        if approval is not None and (
            decision is None or decision.status != ApprovalStatus.APPROVED
        ):
            return self._receipt(
                command,
                status=SessionAgentTurnStatus.APPROVAL_REQUIRED,
                summary="Job 需要绑定审批人完成独立审批；Agent 未执行目标动作。",
                target_id=target_id,
                job=current,
                approval_id=approval.approval_id,
                approval_status=(
                    decision.status if decision is not None else ApprovalStatus.PENDING
                ),
            )
        remaining_s = max(0.0, (record.expires_at - now).total_seconds())
        if remaining_s <= 0:
            raise TimeoutError("Session Agent session expired")
        local_cancel_event = threading.Event()
        cancel_event = _SessionAgentCancellation(
            local_cancel_event,
            self.sessions,
            record.session_id,
        )
        timer = self.timer_factory(remaining_s, local_cancel_event.set)
        timer.daemon = True
        timer.start()
        with self._active_cancel_events_guard:
            self._active_cancel_events.setdefault(record.session_id, set()).add(local_cancel_event)
        try:
            executed = self.job_runner.run(  # type: ignore[arg-type]
                command.job_id,
                cancel_event=cancel_event,
            )
        finally:
            timer.cancel()
            with self._active_cancel_events_guard:
                active = self._active_cancel_events.get(record.session_id)
                if active is not None:
                    active.discard(local_cancel_event)
                    if not active:
                        self._active_cancel_events.pop(record.session_id, None)
        if executed.job.state == DeploymentJobState.COMPLETE:
            status = SessionAgentTurnStatus.COMPLETED
        elif executed.job.state in {DeploymentJobState.BLOCKED, DeploymentJobState.FAILED}:
            status = SessionAgentTurnStatus.BLOCKED
        elif executed.job.state == DeploymentJobState.CANCELLED:
            status = SessionAgentTurnStatus.CANCEL_REQUESTED
        else:
            status = SessionAgentTurnStatus.SUBMITTED
        return self._receipt(
            command,
            status=status,
            summary=f"Job 当前状态为 {executed.job.state.value}。",
            target_id=target_id,
            job=executed,
            canonical_cli=shlex.join(
                ["robotctl", "target", "job", "run", "--job-id", command.job_id]
            ),
        )

    def _execute_command(
        self,
        record: SessionAgentSessionRecord,
        command: SessionAgentCommand,
        *,
        now: datetime,
    ) -> SessionAgentCommandReceipt:
        allowed = set(record.allowed_target_ids)
        if command.action == SessionAgentAction.LIST_TARGETS:
            projection = self._safe_projection(
                self.workbench.snapshot(TargetDeploymentTuiPage.FLEET),
                allowed,
            )
            return self._receipt(
                command,
                status=SessionAgentTurnStatus.COMPLETED,
                summary=f"已读取 {len(projection.rows)} 个允许访问的目标。",
                projection=projection,
            )
        if command.action == SessionAgentAction.LIST_BLOCKERS:
            projection = self._safe_projection(
                self.workbench.snapshot(TargetDeploymentTuiPage.BLOCKER),
                allowed,
            )
            return self._receipt(
                command,
                status=SessionAgentTurnStatus.COMPLETED,
                summary=f"当前有 {len(projection.rows)} 个允许访问且需要关注的 Job。",
                projection=projection,
            )
        if command.action == SessionAgentAction.SHOW_TARGET:
            assert command.target_id is not None
            self._assert_target_allowed(record, command.target_id)
            projection = self._safe_projection(
                self.workbench.snapshot(
                    TargetDeploymentTuiPage.TARGET,
                    target_id=command.target_id,
                ),
                allowed,
            )
            return self._receipt(
                command,
                status=SessionAgentTurnStatus.COMPLETED,
                summary=f"已读取目标 {command.target_id} 的安全状态投影。",
                target_id=command.target_id,
                projection=projection,
            )
        if command.action == SessionAgentAction.ASSESS_CONNECTION:
            assert command.target_id is not None
            registration = self.registrations.load(command.target_id)
            active_probe = command.active_probe or "runtime-readonly"
            job_command = DeploymentCommand(
                command=DeploymentCommandKind.ASSESS_CONNECTION,
                target_id=command.target_id,
                active_probe=active_probe,
                run_adapter_agent=False,
                requested_by=record.principal,
                interaction_surface=InteractionSurface.NATURAL_LANGUAGE,
                idempotency_key=self._idempotency_key(record, command),
                parameters_sha256=target_connection_binding_sha256(
                    registration.target,
                    registration.connection,
                ),
            )
            job = self.jobs.create_job(job_command)
            return self._receipt(
                command,
                status=SessionAgentTurnStatus.SUBMITTED,
                summary="连接评估 Job 已创建；运行是独立命令。",
                target_id=command.target_id,
                job=job,
                canonical_cli=shlex.join(
                    [
                        "robotctl",
                        "target",
                        "connect",
                        "assess",
                        "--target",
                        command.target_id,
                        "--active-probe",
                        active_probe,
                        "--idempotency-key",
                        job_command.idempotency_key,
                        "--requested-by",
                        record.principal,
                    ]
                ),
            )
        if command.action == SessionAgentAction.SUBMIT_ADAPT:
            assert command.target_id is not None
            active_probe = command.active_probe or (
                "runtime-readonly"
                if command.runtime_evidence_job_id is not None
                else "none"
                if command.project_evidence_job_id is not None
                or command.source_discovery_job_id is not None
                else "runtime-readonly"
            )
            remaining_s = max(1, int((record.expires_at - now).total_seconds()))
            registration = self.registrations.load(command.target_id)
            binding = None
            if command.project_evidence_job_id is not None:
                if self.project_evidence_artifacts is None:
                    raise RuntimeError("Project evidence artifacts are unavailable")
                binding = resolve_target_adapt_project_evidence_binding(
                    job_id=command.project_evidence_job_id,
                    target_id=command.target_id,
                    target_registration_sha256=target_connection_binding_sha256(
                        registration.target,
                        registration.connection,
                    ),
                    jobs=self.jobs,
                    artifacts=self.project_evidence_artifacts,
                    max_age_s=900,
                    now=now,
                )
            runtime_binding = None
            if command.runtime_evidence_job_id is not None:
                if self.runtime_evidence_artifacts is None or self.collector_pins is None:
                    raise RuntimeError("Runtime evidence artifacts are unavailable")
                runtime_binding = resolve_target_adapt_runtime_evidence_binding(
                    job_id=command.runtime_evidence_job_id,
                    target_id=command.target_id,
                    target_registration_sha256=target_connection_binding_sha256(
                        registration.target,
                        registration.connection,
                    ),
                    jobs=self.jobs,
                    artifacts=self.runtime_evidence_artifacts,
                    pins=self.collector_pins,
                    max_age_s=300,
                    now=now,
                )
            source_binding = None
            if command.source_discovery_job_id is not None:
                if binding is None:
                    raise ValueError(
                        "Source discovery requires a project evidence workspace binding"
                    )
                if self.source_discovery_artifacts is None:
                    raise RuntimeError("Source discovery artifacts are unavailable")
                source_binding = resolve_target_adapt_source_discovery_binding(
                    job_id=command.source_discovery_job_id,
                    target_id=command.target_id,
                    target_registration_sha256=target_connection_binding_sha256(
                        registration.target,
                        registration.connection,
                    ),
                    workspace_sha256=binding.workspace_sha256,
                    jobs=self.jobs,
                    artifacts=self.source_discovery_artifacts,
                    max_age_s=900,
                    now=now,
                )
            spec = build_target_adapt_job_spec(
                registration,
                TargetAdaptJobSubmission(
                    active_probe=active_probe,
                    run_adapter_agent=False,
                    timeout_s=min(86_400, remaining_s),
                    project_evidence_job_id=command.project_evidence_job_id,
                    source_discovery_job_id=command.source_discovery_job_id,
                    runtime_evidence_job_id=command.runtime_evidence_job_id,
                ),
                project_evidence=binding,
                source_discovery=source_binding,
                runtime_evidence=runtime_binding,
            )
            job = TargetAdaptJobSubmissionService(self.jobs, self.adapt_specs).submit(
                spec,
                requested_by=record.principal,
                interaction_surface=InteractionSurface.NATURAL_LANGUAGE,
                idempotency_key=self._idempotency_key(record, command),
                now=now,
            )
            return self._receipt(
                command,
                status=SessionAgentTurnStatus.SUBMITTED,
                summary="Discovery-only Adapt Job 已创建；运行是独立命令。",
                target_id=command.target_id,
                job=job,
                canonical_cli=shlex.join(
                    [
                        "robotctl",
                        "target",
                        "adapt",
                        "submit",
                        "--target",
                        command.target_id,
                        "--active-probe",
                        active_probe,
                        "--no-run-adapter-agent",
                        "--idempotency-key",
                        job.job.command.idempotency_key,
                        "--requested-by",
                        record.principal,
                    ]
                    + (
                        [
                            "--project-evidence-job-id",
                            command.project_evidence_job_id,
                        ]
                        if command.project_evidence_job_id is not None
                        else []
                    )
                    + (
                        [
                            "--source-discovery-job-id",
                            command.source_discovery_job_id,
                        ]
                        if command.source_discovery_job_id is not None
                        else []
                    )
                    + (
                        [
                            "--runtime-evidence-job-id",
                            command.runtime_evidence_job_id,
                        ]
                        if command.runtime_evidence_job_id is not None
                        else []
                    )
                ),
            )
        if command.action == SessionAgentAction.SUBMIT_PROJECT_EVIDENCE:
            assert command.target_id is not None
            assert command.approver_principal is not None
            if self.project_evidence_submissions is None:
                raise RuntimeError("Project evidence submission is unavailable")
            if hmac.compare_digest(command.approver_principal, record.principal):
                raise PermissionError("Session Agent cannot assign its requester as approver")
            result: TargetProjectEvidenceJobSubmissionResult = (
                self.project_evidence_submissions.submit(
                    target_id=command.target_id,
                    submission=TargetProjectEvidenceJobSubmission(
                        approver_principal=command.approver_principal,
                        approval_ttl_s=command.approval_ttl_s or 900,
                        timeout_s=max(
                            1.0,
                            min(300.0, (record.expires_at - now).total_seconds()),
                        ),
                    ),
                    requested_by=record.principal,
                    interaction_surface=InteractionSurface.NATURAL_LANGUAGE,
                    idempotency_key=self._idempotency_key(record, command),
                    now=now,
                )
            )
            return self._receipt(
                command,
                status=SessionAgentTurnStatus.APPROVAL_REQUIRED,
                summary=(
                    "Project evidence Job 已冻结为默认有界候选集；"
                    "等待独立审批，Agent 未读取目标文件。"
                ),
                target_id=command.target_id,
                job=result.job,
                approval_id=result.approval.approval_id,
                approval_status=ApprovalStatus.PENDING,
                canonical_cli=shlex.join(
                    [
                        "robotctl",
                        "target",
                        "project-evidence",
                        "submit",
                        "--target",
                        command.target_id,
                        "--approver",
                        command.approver_principal,
                        "--idempotency-key",
                        result.job.job.command.idempotency_key,
                        "--requested-by",
                        record.principal,
                    ]
                ),
            )
        if command.action == SessionAgentAction.SUBMIT_SOURCE_DISCOVERY:
            assert command.target_id is not None
            assert command.approver_principal is not None
            if self.source_discovery_submissions is None:
                raise RuntimeError("Source discovery submission is unavailable")
            if hmac.compare_digest(command.approver_principal, record.principal):
                raise PermissionError("Session Agent cannot assign its requester as approver")
            source_result: TargetSourceDiscoveryJobSubmissionResult = (
                self.source_discovery_submissions.submit(
                    target_id=command.target_id,
                    submission=TargetSourceDiscoveryJobSubmission(
                        approver_principal=command.approver_principal,
                        approval_ttl_s=command.approval_ttl_s or 900,
                        timeout_s=max(
                            1.0,
                            min(300.0, (record.expires_at - now).total_seconds()),
                        ),
                    ),
                    requested_by=record.principal,
                    interaction_surface=InteractionSurface.NATURAL_LANGUAGE,
                    idempotency_key=self._idempotency_key(record, command),
                    now=now,
                )
            )
            return self._receipt(
                command,
                status=SessionAgentTurnStatus.APPROVAL_REQUIRED,
                summary=(
                    "Source discovery Job 已冻结为 workspace 根目录的有界结构化分析；"
                    "等待独立审批，Agent 未读取源码。"
                ),
                target_id=command.target_id,
                job=source_result.job,
                approval_id=source_result.approval.approval_id,
                approval_status=ApprovalStatus.PENDING,
                canonical_cli=shlex.join(
                    [
                        "robotctl",
                        "target",
                        "source-discovery",
                        "submit",
                        "--target",
                        command.target_id,
                        "--approver",
                        command.approver_principal,
                        "--idempotency-key",
                        source_result.job.job.command.idempotency_key,
                        "--requested-by",
                        record.principal,
                    ]
                ),
            )
        if command.action == SessionAgentAction.SUBMIT_RUNTIME_EVIDENCE:
            assert command.target_id is not None
            assert command.approver_principal is not None
            if self.runtime_evidence_submissions is None:
                raise RuntimeError("Runtime evidence submission is unavailable")
            if hmac.compare_digest(command.approver_principal, record.principal):
                raise PermissionError("Session Agent cannot assign its requester as approver")
            runtime_result: TargetRuntimeEvidenceJobSubmissionResult = (
                self.runtime_evidence_submissions.submit(
                    target_id=command.target_id,
                    submission=TargetRuntimeEvidenceJobSubmission(
                        approver_principal=command.approver_principal,
                        approval_ttl_s=command.approval_ttl_s or 300,
                        timeout_s=max(
                            1.0,
                            min(300.0, (record.expires_at - now).total_seconds()),
                        ),
                    ),
                    requested_by=record.principal,
                    interaction_surface=InteractionSurface.NATURAL_LANGUAGE,
                    idempotency_key=self._idempotency_key(record, command),
                    now=now,
                )
            )
            return self._receipt(
                command,
                status=SessionAgentTurnStatus.APPROVAL_REQUIRED,
                summary=(
                    "Runtime evidence Job 已冻结为 hw/Linux/ROS 只读采集；"
                    "等待独立审批，Agent 未执行目标探测。"
                ),
                target_id=command.target_id,
                job=runtime_result.job,
                approval_id=runtime_result.approval.approval_id,
                approval_status=ApprovalStatus.PENDING,
                canonical_cli=shlex.join(
                    [
                        "robotctl",
                        "target",
                        "runtime-evidence",
                        "submit",
                        "--target",
                        command.target_id,
                        "--approver",
                        command.approver_principal,
                        "--idempotency-key",
                        runtime_result.job.job.command.idempotency_key,
                        "--requested-by",
                        record.principal,
                    ]
                ),
            )
        if command.action == SessionAgentAction.SUBMIT_BOOTSTRAP:
            assert command.target_id is not None
            assert command.package_ref is not None
            assert command.approver_principal is not None
            if hmac.compare_digest(command.approver_principal, record.principal):
                raise PermissionError("Session Agent cannot assign its requester as approver")
            result: TargetBootstrapJobSubmissionResult = self.bootstrap_submissions.submit(
                target_id=command.target_id,
                submission=TargetBootstrapJobSubmission(
                    package_ref=command.package_ref,
                    approver_principal=command.approver_principal,
                    approval_ttl_s=command.approval_ttl_s or 900,
                    expect_current_present=(
                        command.expect_current_present
                        if command.expect_current_present is not None
                        else False
                    ),
                    expected_current_manifest_sha256=(command.expected_current_manifest_sha256),
                    timeout_s=max(
                        10.0,
                        min(1800.0, (record.expires_at - now).total_seconds()),
                    ),
                ),
                requested_by=record.principal,
                interaction_surface=InteractionSurface.NATURAL_LANGUAGE,
                idempotency_key=self._idempotency_key(record, command),
            )
            return self._receipt(
                command,
                status=SessionAgentTurnStatus.APPROVAL_REQUIRED,
                summary="Bootstrap Job 已冻结；等待独立审批，Agent 未执行目标写入。",
                target_id=command.target_id,
                job=result.job,
                approval_id=result.approval.approval_id,
                approval_status=ApprovalStatus.PENDING,
                canonical_cli=shlex.join(
                    [
                        "robotctl",
                        "target",
                        "bootstrap",
                        "submit",
                        "--target",
                        command.target_id,
                        "--package-ref",
                        command.package_ref,
                        "--approver",
                        command.approver_principal,
                        "--idempotency-key",
                        result.job.job.command.idempotency_key,
                        "--requested-by",
                        record.principal,
                    ]
                ),
            )
        if command.action == SessionAgentAction.SUBMIT_RUNTIME_ROLLBACK:
            assert command.target_id is not None
            assert command.package_id is not None
            assert command.expected_current_manifest_sha256 is not None
            assert command.expected_previous_manifest_sha256 is not None
            assert command.approver_principal is not None
            if self.rollback_submissions is None:
                raise RuntimeError("Target runtime rollback submission is unavailable")
            if hmac.compare_digest(command.approver_principal, record.principal):
                raise PermissionError("Session Agent cannot assign its requester as approver")
            result: TargetRuntimeRollbackJobSubmissionResult = self.rollback_submissions.submit(
                target_id=command.target_id,
                submission=TargetRuntimeRollbackSubmission(
                    package_id=command.package_id,
                    expected_current_manifest_sha256=(command.expected_current_manifest_sha256),
                    expected_previous_manifest_sha256=(command.expected_previous_manifest_sha256),
                    approver_principal=command.approver_principal,
                    approval_ttl_s=command.approval_ttl_s or 900,
                    timeout_s=max(
                        10.0,
                        min(1800.0, (record.expires_at - now).total_seconds()),
                    ),
                ),
                requested_by=record.principal,
                interaction_surface=InteractionSurface.NATURAL_LANGUAGE,
                idempotency_key=self._idempotency_key(record, command),
            )
            return self._receipt(
                command,
                status=SessionAgentTurnStatus.APPROVAL_REQUIRED,
                summary=(
                    "Target runtime rollback Job 已冻结；等待独立审批，Agent 未执行目标写入。"
                ),
                target_id=command.target_id,
                job=result.job,
                approval_id=result.approval.approval_id,
                approval_status=ApprovalStatus.PENDING,
                canonical_cli=shlex.join(
                    [
                        "robotctl",
                        "target",
                        "runtime",
                        "rollback",
                        "--target",
                        command.target_id,
                        "--package-id",
                        command.package_id,
                        "--expected-current-manifest-sha256",
                        command.expected_current_manifest_sha256,
                        "--expected-previous-manifest-sha256",
                        command.expected_previous_manifest_sha256,
                        "--approver",
                        command.approver_principal,
                        "--idempotency-key",
                        result.job.job.command.idempotency_key,
                        "--requested-by",
                        record.principal,
                    ]
                ),
            )
        if command.action == SessionAgentAction.GET_JOB:
            assert command.job_id is not None
            job = self.jobs.load_job(command.job_id)
            self._assert_target_allowed(record, job.job.command.target_id)
            return self._receipt(
                command,
                status=SessionAgentTurnStatus.COMPLETED,
                summary=f"Job 当前状态为 {job.job.state.value}。",
                target_id=job.job.command.target_id,
                job=job,
                canonical_cli=shlex.join(
                    ["robotctl", "target", "job", "get", "--job-id", command.job_id]
                ),
            )
        if command.action == SessionAgentAction.RUN_JOB:
            return self._run_job(record, command, now=now)
        if command.action == SessionAgentAction.CANCEL_JOB:
            assert command.job_id is not None
            job = self.jobs.request_cancel(command.job_id)
            return self._receipt(
                command,
                status=SessionAgentTurnStatus.CANCEL_REQUESTED,
                summary="Job 取消请求已持久化。",
                target_id=job.job.command.target_id,
                job=job,
                canonical_cli=shlex.join(
                    ["robotctl", "target", "job", "cancel", "--job-id", command.job_id]
                ),
            )
        if command.action == SessionAgentAction.SHOW_APPROVAL:
            assert command.approval_id is not None
            approval = self.jobs.load_approval_request(command.approval_id)
            self._assert_target_allowed(record, approval.target_id)
            decision = self.jobs.get_approval_decision(command.approval_id)
            status = decision.status if decision is not None else ApprovalStatus.PENDING
            projection = self._safe_projection(
                self.workbench.snapshot(
                    TargetDeploymentTuiPage.APPROVAL,
                    approval_id=command.approval_id,
                ),
                allowed,
            )
            return self._receipt(
                command,
                status=SessionAgentTurnStatus.COMPLETED,
                summary=f"Approval 当前状态为 {status.value}；决定必须由绑定审批人执行。",
                target_id=approval.target_id,
                approval_id=approval.approval_id,
                approval_status=status,
                projection=projection,
            )
        raise ValueError("Session Agent command is not executable")

    def execute(
        self,
        session_id: str,
        subject: SessionAgentSubject,
        command: SessionAgentCommand,
    ) -> SessionAgentCommandReceipt:
        with self._lock_for(session_id), self.sessions.execution_lock(session_id):
            record = self.sessions.load(session_id)
            self._assert_subject(record, subject)
            now = self.now()
            if record.cancelled_at is not None:
                raise RuntimeError("Session Agent session is cancelled")
            if now >= record.expires_at:
                raise TimeoutError("Session Agent session expired")
            if command.sequence < record.next_sequence:
                previous = record.receipts[command.sequence - 1]
                if previous.command_sha256 != command.canonical_sha256():
                    raise ValueError("Session Agent sequence belongs to another command")
                return previous
            if command.sequence > record.next_sequence:
                raise ValueError("Session Agent command sequence is not the next expected value")
            if len(record.receipts) >= record.max_tool_calls:
                raise RuntimeError("Session Agent action budget is exhausted")
            descriptor = self._descriptor(command.action)
            if (
                descriptor.required_permission is not None
                and descriptor.required_permission not in record.permissions
            ):
                raise PermissionError(
                    f"Session Agent lacks permission: {descriptor.required_permission}"
                )
            target_id = self._target_for_command(command)
            if target_id is not None:
                self._assert_target_allowed(record, target_id)
            try:
                receipt = self._execute_command(record, command, now=now)
            except PermissionError:
                raise
            except (FileNotFoundError, OSError, RuntimeError, TimeoutError, ValueError):
                receipt = self._receipt(
                    command,
                    status=SessionAgentTurnStatus.FAILED,
                    summary=(
                        f"Broker 拒绝或无法执行 {command.action.value}；未返回异常或目标输出。"
                    ),
                    target_id=target_id,
                )
            self.sessions.append_receipt(record, receipt)
            return receipt
