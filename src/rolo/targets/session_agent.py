from __future__ import annotations

import hashlib
import json
import re
import shlex
import threading
from collections.abc import Callable
from enum import Enum
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from rolo.targets.adapt_jobs import (
    TargetAdaptJobSpecStore,
    TargetAdaptJobSubmission,
    TargetAdaptJobSubmissionService,
    build_target_adapt_job_spec,
)
from rolo.targets.bootstrap_jobs import (
    TargetBootstrapJobSubmission,
    TargetBootstrapJobSubmissionResult,
    TargetBootstrapPublicSubmissionService,
)
from rolo.targets.connection_assessment import TargetDeploymentJobRunner
from rolo.targets.deployment_api import DeploymentJobSubmission, build_deployment_command
from rolo.targets.deployment_jobs import DeploymentJobRecord, DeploymentJobStore
from rolo.targets.deployment_tui import TargetDeploymentTui, TargetDeploymentTuiPage
from rolo.targets.models import (
    ApprovalStatus,
    DeploymentCommandKind,
    DeploymentJobState,
    InteractionSurface,
)
from rolo.targets.registration import (
    TargetRegistrationService,
    target_connection_binding_sha256,
)

_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$"
_JOB_ID = r"^deployment-[0-9a-f]{32}$"
_APPROVAL_ID = r"^approval-[0-9a-f]{32}$"
_PRINCIPAL = r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,127}$"
_IDEMPOTENCY = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{7,127}$"
_SHA256 = r"^[0-9a-f]{64}$"


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class SessionAgentAction(str, Enum):
    CLARIFY = "CLARIFY"
    LIST_TARGETS = "LIST_TARGETS"
    SHOW_TARGET = "SHOW_TARGET"
    ASSESS_CONNECTION = "ASSESS_CONNECTION"
    SUBMIT_BOOTSTRAP = "SUBMIT_BOOTSTRAP"
    SUBMIT_ADAPT = "SUBMIT_ADAPT"
    GET_JOB = "GET_JOB"
    RUN_JOB = "RUN_JOB"
    CANCEL_JOB = "CANCEL_JOB"
    SHOW_APPROVAL = "SHOW_APPROVAL"
    LIST_BLOCKERS = "LIST_BLOCKERS"


class SessionAgentMissingInput(str, Enum):
    TARGET_ID = "TARGET_ID"
    JOB_ID = "JOB_ID"
    PACKAGE_REF = "PACKAGE_REF"
    APPROVER_PRINCIPAL = "APPROVER_PRINCIPAL"
    APPROVAL_ID = "APPROVAL_ID"
    TARGET_SELECTION = "TARGET_SELECTION"


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
    requires_external_approval: bool = False
    allowed_parameters: list[str] = Field(default_factory=list, max_length=32)


class SessionAgentToolCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-session-agent-tool-catalog/v1"] = (
        "rolo-session-agent-tool-catalog/v1"
    )
    tools: list[SessionAgentToolDescriptor] = Field(min_length=1, max_length=32)
    raw_shell_available: Literal[False] = False
    approval_decision_available: Literal[False] = False
    credential_material_available: Literal[False] = False

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
        SessionAgentAction.CLARIFY: (SessionAgentToolRisk.READ_ONLY, "NONE", False, []),
        SessionAgentAction.LIST_TARGETS: (
            SessionAgentToolRisk.READ_ONLY,
            "NONE",
            False,
            [],
        ),
        SessionAgentAction.SHOW_TARGET: (
            SessionAgentToolRisk.READ_ONLY,
            "NONE",
            False,
            ["target_id"],
        ),
        SessionAgentAction.ASSESS_CONNECTION: (
            SessionAgentToolRisk.JOB_CREATE,
            "TARGET_READ",
            False,
            ["target_id", "active_probe", "run_after_submit"],
        ),
        SessionAgentAction.SUBMIT_BOOTSTRAP: (
            SessionAgentToolRisk.APPROVAL_HANDOFF,
            "CONTROLLER_STATE",
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
        SessionAgentAction.SUBMIT_ADAPT: (
            SessionAgentToolRisk.JOB_CREATE,
            "CONTROLLER_STATE",
            False,
            ["target_id", "active_probe", "run_after_submit"],
        ),
        SessionAgentAction.GET_JOB: (
            SessionAgentToolRisk.READ_ONLY,
            "NONE",
            False,
            ["job_id"],
        ),
        SessionAgentAction.RUN_JOB: (
            SessionAgentToolRisk.JOB_EXECUTE,
            "TARGET_MUTATION",
            True,
            ["job_id"],
        ),
        SessionAgentAction.CANCEL_JOB: (
            SessionAgentToolRisk.JOB_CANCEL,
            "CONTROLLER_STATE",
            False,
            ["job_id"],
        ),
        SessionAgentAction.SHOW_APPROVAL: (
            SessionAgentToolRisk.READ_ONLY,
            "NONE",
            False,
            ["approval_id"],
        ),
        SessionAgentAction.LIST_BLOCKERS: (
            SessionAgentToolRisk.READ_ONLY,
            "NONE",
            False,
            [],
        ),
    }
    tools = [
        SessionAgentToolDescriptor(
            action=action,
            risk=risk,
            effect=effect,
            requires_external_approval=approval,
            allowed_parameters=parameters,
        )
        for action, (risk, effect, approval, parameters) in definitions.items()
    ]
    tools.sort(key=lambda item: item.action.value)
    return SessionAgentToolCatalog(tools=tools)


class SessionAgentTurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-session-agent-turn-request/v1"] = (
        "rolo-session-agent-turn-request/v1"
    )
    message: str = Field(min_length=1, max_length=16_384)
    principal: str = Field(pattern=_PRINCIPAL)
    idempotency_key: str = Field(pattern=_IDEMPOTENCY)
    allowed_target_ids: list[str] = Field(default_factory=list, max_length=1000)
    max_tool_calls: int = Field(default=4, ge=1, le=8)
    timeout_s: float = Field(default=120.0, ge=1.0, le=1800.0)

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        if any(character in value for character in ("\x00", "\r")):
            raise ValueError("Session Agent message contains control characters")
        return value.strip()

    @field_validator("allowed_target_ids")
    @classmethod
    def canonical_targets(cls, values: list[str]) -> list[str]:
        if any(re.fullmatch(_IDENTIFIER, value) is None for value in values):
            raise ValueError("Session Agent allowed target ID is invalid")
        if values != sorted(set(values)):
            raise ValueError("Session Agent allowed target IDs must be unique and sorted")
        return values


class SessionAgentIntent(BaseModel):
    """Strict model output. It deliberately has no shell, argv, path or credential fields."""

    model_config = ConfigDict(extra="forbid")

    action: SessionAgentAction
    target_id: str | None = Field(default=None, pattern=_IDENTIFIER)
    job_id: str | None = Field(default=None, pattern=_JOB_ID)
    approval_id: str | None = Field(default=None, pattern=_APPROVAL_ID)
    package_ref: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}@[0-9a-f]{64}$",
    )
    approver_principal: str | None = Field(default=None, pattern=_PRINCIPAL)
    active_probe: Literal["none", "help", "runtime-readonly"] = "runtime-readonly"
    run_after_submit: bool = False
    run_adapter_agent: Literal[False] = False
    approval_ttl_s: int = Field(default=900, ge=60, le=86_400)
    expect_current_present: bool | None = False
    expected_current_manifest_sha256: str | None = Field(default=None, pattern=_SHA256)
    missing_inputs: list[SessionAgentMissingInput] = Field(default_factory=list, max_length=8)

    @field_validator("missing_inputs")
    @classmethod
    def canonical_missing_inputs(
        cls,
        values: list[SessionAgentMissingInput],
    ) -> list[SessionAgentMissingInput]:
        if values != sorted(set(values), key=lambda item: item.value):
            raise ValueError("Session Agent missing inputs must be unique and sorted")
        return values


class SessionAgentPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-session-agent-plan/v1"] = "rolo-session-agent-plan/v1"
    catalog_sha256: str = Field(pattern=_SHA256)
    intents: list[SessionAgentIntent] = Field(min_length=1, max_length=8)


class SessionAgentPlanner(Protocol):
    def plan(
        self,
        request: SessionAgentTurnRequest,
        catalog: SessionAgentToolCatalog,
        *,
        registered_target_ids: list[str],
    ) -> SessionAgentPlan: ...


class SessionAgentTurnStatus(str, Enum):
    COMPLETED = "COMPLETED"
    SUBMITTED = "SUBMITTED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class SessionAgentToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence: int = Field(ge=1, le=8)
    action: SessionAgentAction
    input_sha256: str = Field(pattern=_SHA256)
    status: SessionAgentTurnStatus
    summary: str = Field(min_length=1, max_length=1000)
    target_id: str | None = Field(default=None, pattern=_IDENTIFIER)
    job_id: str | None = Field(default=None, pattern=_JOB_ID)
    approval_id: str | None = Field(default=None, pattern=_APPROVAL_ID)
    command_sha256: str | None = Field(default=None, pattern=_SHA256)
    canonical_cli: str | None = Field(default=None, max_length=8192)


class SessionAgentTurnResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-session-agent-turn-result/v1"] = (
        "rolo-session-agent-turn-result/v1"
    )
    status: SessionAgentTurnStatus
    catalog_sha256: str = Field(pattern=_SHA256)
    plan_sha256: str = Field(pattern=_SHA256)
    tool_calls: list[SessionAgentToolCall] = Field(default_factory=list, max_length=8)
    clarification_codes: list[SessionAgentMissingInput] = Field(
        default_factory=list,
        max_length=8,
    )
    clarification: str | None = Field(default=None, max_length=1000)
    summary: str = Field(min_length=1, max_length=1000)


_CLARIFICATIONS = {
    SessionAgentMissingInput.TARGET_ID: "请明确要操作的目标 ID。",
    SessionAgentMissingInput.TARGET_SELECTION: "存在多个可用目标，请明确选择一个目标 ID。",
    SessionAgentMissingInput.JOB_ID: "请提供要查询或控制的 Job ID。",
    SessionAgentMissingInput.PACKAGE_REF: "请提供已导入 Controller 仓库的不可变 package ref。",
    SessionAgentMissingInput.APPROVER_PRINCIPAL: "请指定与请求人不同的审批人 principal。",
    SessionAgentMissingInput.APPROVAL_ID: "请提供要查看的 Approval ID。",
}


def _required_missing(intent: SessionAgentIntent) -> list[SessionAgentMissingInput]:
    missing = set(intent.missing_inputs)
    if intent.action in {
        SessionAgentAction.SHOW_TARGET,
        SessionAgentAction.ASSESS_CONNECTION,
        SessionAgentAction.SUBMIT_BOOTSTRAP,
        SessionAgentAction.SUBMIT_ADAPT,
    } and intent.target_id is None:
        missing.add(SessionAgentMissingInput.TARGET_ID)
    if intent.action in {
        SessionAgentAction.GET_JOB,
        SessionAgentAction.RUN_JOB,
        SessionAgentAction.CANCEL_JOB,
    } and intent.job_id is None:
        missing.add(SessionAgentMissingInput.JOB_ID)
    if intent.action == SessionAgentAction.SUBMIT_BOOTSTRAP:
        if intent.package_ref is None:
            missing.add(SessionAgentMissingInput.PACKAGE_REF)
        if intent.approver_principal is None:
            missing.add(SessionAgentMissingInput.APPROVER_PRINCIPAL)
    if intent.action == SessionAgentAction.SHOW_APPROVAL and intent.approval_id is None:
        missing.add(SessionAgentMissingInput.APPROVAL_ID)
    return sorted(missing, key=lambda item: item.value)


class SessionAgentOrchestrator:
    """Compile strict model intent into existing W7 services without delegating authority."""

    def __init__(
        self,
        *,
        planner: SessionAgentPlanner,
        registrations: TargetRegistrationService,
        jobs: DeploymentJobStore,
        adapt_specs: TargetAdaptJobSpecStore,
        bootstrap_submissions: TargetBootstrapPublicSubmissionService,
        job_runner: TargetDeploymentJobRunner,
        workbench: TargetDeploymentTui,
        timer_factory: Callable[[float, Callable[[], None]], threading.Timer] = threading.Timer,
    ) -> None:
        self.planner = planner
        self.registrations = registrations
        self.jobs = jobs
        self.adapt_specs = adapt_specs
        self.bootstrap_submissions = bootstrap_submissions
        self.job_runner = job_runner
        self.workbench = workbench
        self.timer_factory = timer_factory
        self.catalog = build_session_agent_tool_catalog()

    @staticmethod
    def _intent_digest(intent: SessionAgentIntent) -> str:
        return _canonical_sha256(intent.model_dump(mode="json"))

    @staticmethod
    def _plan_digest(plan: SessionAgentPlan) -> str:
        return _canonical_sha256(plan.model_dump(mode="json"))

    @staticmethod
    def _expanded_tool_calls(intent: SessionAgentIntent) -> int:
        return 2 if intent.run_after_submit else 1

    def _clarification_result(
        self,
        plan: SessionAgentPlan,
        codes: list[SessionAgentMissingInput],
    ) -> SessionAgentTurnResult:
        canonical_codes = sorted(set(codes), key=lambda item: item.value)
        return SessionAgentTurnResult(
            status=SessionAgentTurnStatus.NEEDS_CLARIFICATION,
            catalog_sha256=self.catalog.canonical_sha256(),
            plan_sha256=self._plan_digest(plan),
            clarification_codes=canonical_codes,
            clarification=" ".join(_CLARIFICATIONS[code] for code in canonical_codes),
            summary="执行前仍缺少必须由用户确认的输入。",
        )

    def _approval_for_job(self, job_id: str):  # type: ignore[no-untyped-def]
        requests = [
            request
            for request in self.jobs.list_approval_requests(limit=10_000)
            if request.job_id == job_id
        ]
        if not requests:
            return None, None
        if len(requests) != 1:
            raise ValueError("Session Agent found an ambiguous approval set")
        request = requests[0]
        return request, self.jobs.get_approval_decision(request.approval_id)

    @staticmethod
    def _call(
        sequence: int,
        intent: SessionAgentIntent,
        *,
        status: SessionAgentTurnStatus,
        summary: str,
        target_id: str | None = None,
        job: DeploymentJobRecord | None = None,
        approval_id: str | None = None,
        canonical_cli: str | None = None,
    ) -> SessionAgentToolCall:
        return SessionAgentToolCall(
            sequence=sequence,
            action=intent.action,
            input_sha256=SessionAgentOrchestrator._intent_digest(intent),
            status=status,
            summary=summary,
            target_id=target_id,
            job_id=job.job.job_id if job is not None else intent.job_id,
            approval_id=approval_id,
            command_sha256=job.job.command_sha256 if job is not None else None,
            canonical_cli=canonical_cli,
        )

    def _run_job(
        self,
        intent: SessionAgentIntent,
        *,
        sequence: int,
        timeout_s: float,
    ) -> SessionAgentToolCall:
        assert intent.job_id is not None
        record = self.jobs.load_job(intent.job_id)
        approval, decision = self._approval_for_job(intent.job_id)
        if approval is not None and (
            decision is None or decision.status != ApprovalStatus.APPROVED
        ):
            return self._call(
                sequence,
                intent,
                status=SessionAgentTurnStatus.APPROVAL_REQUIRED,
                summary="Job 需要绑定审批人完成独立审批，Session Agent 未执行目标动作。",
                target_id=record.job.command.target_id,
                job=record,
                approval_id=approval.approval_id,
                canonical_cli=shlex.join(
                    [
                        "robotctl",
                        "target",
                        "approval",
                        "decide",
                        "--approval-id",
                        approval.approval_id,
                        "--principal",
                        approval.approver_principal,
                        "--idempotency-key",
                        "<idempotency-key>",
                        "--reason",
                        "<review-reason>",
                        "--approve",
                    ]
                ),
            )
        cancel_event = threading.Event()
        timer = self.timer_factory(timeout_s, cancel_event.set)
        timer.daemon = True
        timer.start()
        try:
            executed = self.job_runner.run(intent.job_id, cancel_event=cancel_event)
        finally:
            timer.cancel()
        status = (
            SessionAgentTurnStatus.COMPLETED
            if executed.job.state == DeploymentJobState.COMPLETE
            else SessionAgentTurnStatus.BLOCKED
            if executed.job.state
            in {DeploymentJobState.BLOCKED, DeploymentJobState.FAILED}
            else SessionAgentTurnStatus.CANCEL_REQUESTED
            if executed.job.state == DeploymentJobState.CANCELLED
            else SessionAgentTurnStatus.SUBMITTED
        )
        return self._call(
            sequence,
            intent,
            status=status,
            summary=f"Job 当前状态为 {executed.job.state.value}。",
            target_id=executed.job.command.target_id,
            job=executed,
            canonical_cli=shlex.join(
                ["robotctl", "target", "job", "run", "--job-id", intent.job_id]
            ),
        )

    def _execute(
        self,
        intent: SessionAgentIntent,
        request: SessionAgentTurnRequest,
        *,
        sequence: int,
    ) -> SessionAgentToolCall:
        if intent.action == SessionAgentAction.LIST_TARGETS:
            snapshot = self.workbench.snapshot(TargetDeploymentTuiPage.FLEET)
            return self._call(
                sequence,
                intent,
                status=SessionAgentTurnStatus.COMPLETED,
                summary=f"已读取 {len(snapshot.rows)} 个已注册目标。",
            )
        if intent.action == SessionAgentAction.LIST_BLOCKERS:
            snapshot = self.workbench.snapshot(TargetDeploymentTuiPage.BLOCKER)
            return self._call(
                sequence,
                intent,
                status=SessionAgentTurnStatus.COMPLETED,
                summary=f"当前有 {len(snapshot.rows)} 个需要关注的 Job。",
            )
        if intent.action == SessionAgentAction.SHOW_TARGET:
            assert intent.target_id is not None
            snapshot = self.workbench.snapshot(
                TargetDeploymentTuiPage.TARGET,
                target_id=intent.target_id,
            )
            return self._call(
                sequence,
                intent,
                status=SessionAgentTurnStatus.COMPLETED,
                summary=f"已读取目标 {intent.target_id} 的 {len(snapshot.rows)} 条状态。",
                target_id=intent.target_id,
            )
        if intent.action == SessionAgentAction.ASSESS_CONNECTION:
            assert intent.target_id is not None
            registration = self.registrations.load(intent.target_id)
            submission = DeploymentJobSubmission(
                active_probe=intent.active_probe,
                run_adapter_agent=False,
                parameters_sha256=target_connection_binding_sha256(
                    registration.target,
                    registration.connection,
                ),
            )
            command = build_deployment_command(
                target_id=intent.target_id,
                command_kind=DeploymentCommandKind.ASSESS_CONNECTION,
                submission=submission,
                requested_by=request.principal,
                interaction_surface=InteractionSurface.NATURAL_LANGUAGE,
                idempotency_key=request.idempotency_key,
            )
            job = self.jobs.create_job(command)
            call = self._call(
                sequence,
                intent,
                status=SessionAgentTurnStatus.SUBMITTED,
                summary="连接评估 Job 已创建。",
                target_id=intent.target_id,
                job=job,
                canonical_cli=shlex.join(
                    [
                        "robotctl",
                        "target",
                        "connect",
                        "assess",
                        "--target",
                        intent.target_id,
                        "--active-probe",
                        intent.active_probe,
                        "--idempotency-key",
                        request.idempotency_key,
                        "--requested-by",
                        request.principal,
                    ]
                ),
            )
            if intent.run_after_submit:
                run_intent = SessionAgentIntent(
                    action=SessionAgentAction.RUN_JOB,
                    job_id=job.job.job_id,
                )
                return self._run_job(
                    run_intent,
                    sequence=sequence,
                    timeout_s=request.timeout_s,
                ).model_copy(update={"action": intent.action})
            return call
        if intent.action == SessionAgentAction.SUBMIT_ADAPT:
            assert intent.target_id is not None
            spec = build_target_adapt_job_spec(
                self.registrations.load(intent.target_id),
                TargetAdaptJobSubmission(
                    active_probe=intent.active_probe,
                    run_adapter_agent=False,
                    timeout_s=min(86_400, max(1, int(request.timeout_s))),
                ),
            )
            job = TargetAdaptJobSubmissionService(self.jobs, self.adapt_specs).submit(
                spec,
                requested_by=request.principal,
                interaction_surface=InteractionSurface.NATURAL_LANGUAGE,
                idempotency_key=request.idempotency_key,
            )
            call = self._call(
                sequence,
                intent,
                status=SessionAgentTurnStatus.SUBMITTED,
                summary="Local discovery-only Adapt Job 已创建。",
                target_id=intent.target_id,
                job=job,
                canonical_cli=shlex.join(
                    [
                        "robotctl",
                        "target",
                        "adapt",
                        "submit",
                        "--target",
                        intent.target_id,
                        "--active-probe",
                        intent.active_probe,
                        "--no-run-adapter-agent",
                        "--timeout-s",
                        str(min(86_400, max(1, int(request.timeout_s)))),
                        "--idempotency-key",
                        request.idempotency_key,
                        "--requested-by",
                        request.principal,
                    ]
                ),
            )
            if intent.run_after_submit:
                run_intent = SessionAgentIntent(
                    action=SessionAgentAction.RUN_JOB,
                    job_id=job.job.job_id,
                )
                return self._run_job(
                    run_intent,
                    sequence=sequence,
                    timeout_s=request.timeout_s,
                ).model_copy(update={"action": intent.action})
            return call
        if intent.action == SessionAgentAction.SUBMIT_BOOTSTRAP:
            assert intent.target_id is not None
            assert intent.package_ref is not None
            assert intent.approver_principal is not None
            result: TargetBootstrapJobSubmissionResult = self.bootstrap_submissions.submit(
                target_id=intent.target_id,
                submission=TargetBootstrapJobSubmission(
                    package_ref=intent.package_ref,
                    approver_principal=intent.approver_principal,
                    approval_ttl_s=intent.approval_ttl_s,
                    expect_current_present=intent.expect_current_present,
                    expected_current_manifest_sha256=(
                        intent.expected_current_manifest_sha256
                    ),
                    timeout_s=min(1800.0, max(10.0, request.timeout_s)),
                ),
                requested_by=request.principal,
                interaction_surface=InteractionSurface.NATURAL_LANGUAGE,
                idempotency_key=request.idempotency_key,
            )
            return self._call(
                sequence,
                intent,
                status=SessionAgentTurnStatus.APPROVAL_REQUIRED,
                summary="Bootstrap Job 已冻结；等待独立审批，Session Agent 未执行目标写入。",
                target_id=intent.target_id,
                job=result.job,
                approval_id=result.approval.approval_id,
                canonical_cli=shlex.join(
                    [
                        "robotctl",
                        "target",
                        "bootstrap",
                        "submit",
                        "--target",
                        intent.target_id,
                        "--package-ref",
                        intent.package_ref,
                        "--approver",
                        intent.approver_principal,
                        "--idempotency-key",
                        request.idempotency_key,
                        "--requested-by",
                        request.principal,
                    ]
                ),
            )
        if intent.action == SessionAgentAction.GET_JOB:
            assert intent.job_id is not None
            job = self.jobs.load_job(intent.job_id)
            return self._call(
                sequence,
                intent,
                status=SessionAgentTurnStatus.COMPLETED,
                summary=f"Job 当前状态为 {job.job.state.value}。",
                target_id=job.job.command.target_id,
                job=job,
                canonical_cli=shlex.join(
                    ["robotctl", "target", "job", "get", "--job-id", intent.job_id]
                ),
            )
        if intent.action == SessionAgentAction.RUN_JOB:
            return self._run_job(
                intent,
                sequence=sequence,
                timeout_s=request.timeout_s,
            )
        if intent.action == SessionAgentAction.CANCEL_JOB:
            assert intent.job_id is not None
            job = self.jobs.request_cancel(intent.job_id)
            return self._call(
                sequence,
                intent,
                status=SessionAgentTurnStatus.CANCEL_REQUESTED,
                summary="Job 取消请求已持久化。",
                target_id=job.job.command.target_id,
                job=job,
                canonical_cli=shlex.join(
                    ["robotctl", "target", "job", "cancel", "--job-id", intent.job_id]
                ),
            )
        if intent.action == SessionAgentAction.SHOW_APPROVAL:
            assert intent.approval_id is not None
            approval = self.jobs.load_approval_request(intent.approval_id)
            decision = self.jobs.get_approval_decision(intent.approval_id)
            status = decision.status if decision is not None else ApprovalStatus.PENDING
            return self._call(
                sequence,
                intent,
                status=SessionAgentTurnStatus.COMPLETED,
                summary=f"Approval 当前状态为 {status.value}；决定必须由绑定审批人执行。",
                target_id=approval.target_id,
                approval_id=approval.approval_id,
                canonical_cli=shlex.join(
                    [
                        "robotctl",
                        "target",
                        "tui",
                        "--page",
                        "approval",
                        "--approval-id",
                        approval.approval_id,
                    ]
                ),
            )
        raise ValueError("Session Agent action is not executable")

    def run(self, request: SessionAgentTurnRequest) -> SessionAgentTurnResult:
        registered = sorted(
            profile.target_id for profile in self.registrations.registry.list_targets()
        )
        plan = self.planner.plan(
            request,
            self.catalog,
            registered_target_ids=registered,
        )
        if plan.catalog_sha256 != self.catalog.canonical_sha256():
            raise ValueError("Session Agent plan does not bind the active tool catalog")
        missing = [item for intent in plan.intents for item in _required_missing(intent)]
        if missing:
            return self._clarification_result(plan, missing)
        required_calls = sum(self._expanded_tool_calls(intent) for intent in plan.intents)
        if required_calls > request.max_tool_calls:
            return self._clarification_result(
                plan,
                [SessionAgentMissingInput.TARGET_SELECTION],
            ).model_copy(update={"summary": "请求超过本轮 Agent action budget，请缩小任务范围。"})
        allowed = set(request.allowed_target_ids or registered)
        referenced_targets = {
            intent.target_id for intent in plan.intents if intent.target_id is not None
        }
        if not referenced_targets.issubset(allowed):
            return self._clarification_result(
                plan,
                [SessionAgentMissingInput.TARGET_SELECTION],
            )
        if any(
            intent.action == SessionAgentAction.SUBMIT_BOOTSTRAP
            and intent.approver_principal == request.principal
            for intent in plan.intents
        ):
            return self._clarification_result(
                plan,
                [SessionAgentMissingInput.APPROVER_PRINCIPAL],
            )
        calls: list[SessionAgentToolCall] = []
        for sequence, intent in enumerate(plan.intents, start=1):
            if intent.action == SessionAgentAction.CLARIFY:
                return self._clarification_result(
                    plan,
                    intent.missing_inputs
                    or [SessionAgentMissingInput.TARGET_SELECTION],
                )
            try:
                call = self._execute(intent, request, sequence=sequence)
            except (FileNotFoundError, OSError, ValueError):
                call = self._call(
                    sequence,
                    intent,
                    status=SessionAgentTurnStatus.FAILED,
                    summary="工具执行失败；未将异常或目标输出返回模型。",
                    target_id=intent.target_id,
                )
            calls.append(call)
            if call.status in {
                SessionAgentTurnStatus.APPROVAL_REQUIRED,
                SessionAgentTurnStatus.BLOCKED,
                SessionAgentTurnStatus.FAILED,
            }:
                break
        terminal = calls[-1].status
        return SessionAgentTurnResult(
            status=terminal,
            catalog_sha256=self.catalog.canonical_sha256(),
            plan_sha256=self._plan_digest(plan),
            tool_calls=calls,
            summary=calls[-1].summary,
        )
