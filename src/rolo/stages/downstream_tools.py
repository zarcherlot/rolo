from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from rolo.core.hashing import sha256_file
from rolo.core.models import ToolDescriptor
from rolo.stages.adapt.agent_contracts import ToolSessionDescriptor
from rolo.stages.adapt.tool_gateway import (
    ToolGatewayError,
    ToolInvocationResult,
    ToolSessionAuthorizationError,
    ToolSessionBudgetError,
)
from rolo.stages.artifact_paths import ArtifactLayout, resolve_artifact_ref


class DownstreamToolGateway(Protocol):
    """The only Tool Gateway surface exposed to a downstream Agent."""

    def open_session(self, descriptor: ToolSessionDescriptor) -> None: ...

    def list_tools(self, session_id: str, nonce: str) -> list[ToolDescriptor]: ...

    def invoke(
        self,
        session_id: str,
        nonce: str,
        operation: str,
        payload: dict[str, Any],
        *,
        timeout_s: float | None = None,
    ) -> ToolInvocationResult: ...

    def close_session(self, session_id: str, nonce: str) -> None: ...


class DownstreamToolHandoff(BaseModel):
    """Immutable binding from a Diagnose/Verify handoff to one Tool Session."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-downstream-tool-handoff/v1"] = "rolo-downstream-tool-handoff/v1"
    stage: Literal["diagnose", "verify"]
    robot_id: str = Field(min_length=1, max_length=128)
    caller: str = Field(min_length=1, max_length=128)
    tool_session_ref: str = Field(min_length=1, max_length=512)
    tool_session_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    session_id: str = Field(min_length=1, max_length=128)
    release_id: str = Field(min_length=1, max_length=128)
    tool_catalog_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    state_graph_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    access_scope: Literal["verified-read-only-r0-r1"] = "verified-read-only-r0-r1"
    publication_authority: Literal["none"] = "none"


class DownstreamToolFailure(str, Enum):
    SESSION_EXPIRED = "SESSION_EXPIRED"
    IDENTITY_DRIFT = "IDENTITY_DRIFT"
    UNAUTHORIZED = "UNAUTHORIZED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    GATEWAY_FAILURE = "GATEWAY_FAILURE"


class DownstreamToolOutcome(BaseModel):
    """Fail-closed result envelope safe to return to an untrusted Agent."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-downstream-tool-outcome/v1"] = "rolo-downstream-tool-outcome/v1"
    status: Literal["READY", "SUCCEEDED", "DEGRADED"]
    session_id: str
    operation: str | None = None
    tools: list[ToolDescriptor] = Field(default_factory=list)
    invocation: ToolInvocationResult | None = None
    failure: DownstreamToolFailure | None = None
    message: str = Field(min_length=1, max_length=1_000)
    retry_allowed: bool = False


def validate_downstream_tool_handoff(
    artifact_root: Path,
    robot_id: str,
    stage: Literal["diagnose", "verify"],
) -> tuple[DownstreamToolHandoff, ToolSessionDescriptor]:
    """Resolve the canonical handoff and verify its exact Tool Session binding."""

    handoff_path = ArtifactLayout(artifact_root).stage_file(stage, robot_id, "tool_handoff.json")
    handoff = DownstreamToolHandoff.model_validate_json(handoff_path.read_text(encoding="utf-8"))
    if handoff.robot_id != robot_id or handoff.stage != stage:
        raise ValueError("downstream tool handoff stage or robot identity mismatch")

    session_path = resolve_artifact_ref(artifact_root, handoff.tool_session_ref)
    if not session_path.is_file() or sha256_file(session_path) != handoff.tool_session_sha256:
        raise ValueError("downstream tool handoff Tool Session hash mismatch")
    session = ToolSessionDescriptor.model_validate_json(session_path.read_text(encoding="utf-8"))
    _validate_handoff_session_identity(handoff, session)
    return handoff, session


def _validate_handoff_session_identity(
    handoff: DownstreamToolHandoff,
    session: ToolSessionDescriptor,
) -> None:
    expected = (
        handoff.robot_id,
        handoff.stage,
        handoff.caller,
        handoff.session_id,
        handoff.release_id,
        handoff.tool_catalog_sha256,
        handoff.state_graph_sha256,
    )
    actual = (
        session.robot_id,
        session.stage,
        session.caller,
        session.session_id,
        session.release_id,
        session.tool_catalog_sha256,
        session.state_graph_sha256,
    )
    if actual != expected:
        raise ValueError("downstream tool handoff does not match its Tool Session identity")


class DownstreamToolConsumer:
    """Fail-closed Diagnose/Verify facade over a frozen Tool Gateway session.

    This class has no Registry, Tool Catalog, release, or publication interface. It can only
    list and invoke the subset admitted by its immutable ToolSessionDescriptor.
    """

    def __init__(
        self,
        *,
        handoff: DownstreamToolHandoff,
        session: ToolSessionDescriptor,
        gateway: DownstreamToolGateway,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._handoff = DownstreamToolHandoff.model_validate(handoff.model_dump())
        self._session = ToolSessionDescriptor.model_validate(session.model_dump())
        _validate_handoff_session_identity(self._handoff, self._session)
        self._gateway = gateway
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._active = False
        self._terminal_failure: DownstreamToolFailure | None = None

    @property
    def handoff(self) -> DownstreamToolHandoff:
        return self._handoff.model_copy(deep=True)

    @property
    def session(self) -> ToolSessionDescriptor:
        return self._session.model_copy(deep=True)

    @classmethod
    def from_handoff(
        cls,
        *,
        artifact_root: Path,
        robot_id: str,
        stage: Literal["diagnose", "verify"],
        gateway: DownstreamToolGateway,
        clock: Callable[[], datetime] | None = None,
    ) -> DownstreamToolConsumer:
        handoff, session = validate_downstream_tool_handoff(artifact_root, robot_id, stage)
        return cls(handoff=handoff, session=session, gateway=gateway, clock=clock)

    def open(self) -> DownstreamToolOutcome:
        failure = self._preflight()
        if failure is not None:
            return failure
        if self._active:
            return self._success("READY", "Tool Session is already active")
        try:
            self._gateway.open_session(self._session.model_copy(deep=True))
        except Exception as exc:
            return self._degrade_exception(exc)
        self._active = True
        return self._success("READY", "frozen Tool Session is active")

    def list_tools(self) -> DownstreamToolOutcome:
        failure = self._preflight(require_active=True)
        if failure is not None:
            return failure
        try:
            tools = self._gateway.list_tools(self._session.session_id, self._session.nonce)
            self._validate_returned_tools(tools)
        except Exception as exc:
            return self._degrade_exception(exc)
        return self._success(
            "SUCCEEDED",
            f"returned {len(tools)} session-scoped tools",
            tools=tools,
        )

    def invoke(
        self,
        operation: str,
        payload: dict[str, Any],
        *,
        timeout_s: float | None = None,
    ) -> DownstreamToolOutcome:
        failure = self._preflight(require_active=True, operation=operation)
        if failure is not None:
            return failure
        if operation not in self._session.allowed_operations:
            return self._degrade(
                DownstreamToolFailure.UNAUTHORIZED,
                "operation is outside the frozen Tool Session",
                operation=operation,
            )
        try:
            invocation = self._gateway.invoke(
                self._session.session_id,
                self._session.nonce,
                operation,
                payload,
                timeout_s=timeout_s,
            )
        except Exception as exc:
            return self._degrade_exception(exc, operation=operation)
        if invocation.operation != operation or invocation.session_id != self._session.session_id:
            return self._degrade(
                DownstreamToolFailure.IDENTITY_DRIFT,
                "Tool Gateway result identity does not match the frozen request",
                operation=operation,
            )
        return self._success(
            "SUCCEEDED",
            "read-only Tool Gateway invocation completed",
            operation=operation,
            invocation=invocation,
        )

    def close(self) -> DownstreamToolOutcome:
        failure = self._preflight(require_active=True)
        if failure is not None:
            return failure
        try:
            self._gateway.close_session(self._session.session_id, self._session.nonce)
        except Exception as exc:
            return self._degrade_exception(exc)
        self._active = False
        return self._success("SUCCEEDED", "Tool Session is closed")

    def _preflight(
        self,
        *,
        require_active: bool = False,
        operation: str | None = None,
    ) -> DownstreamToolOutcome | None:
        if self._terminal_failure is not None:
            return self._failure_outcome(
                self._terminal_failure,
                "Tool Session is disabled after a prior fail-closed degradation",
                operation=operation,
            )
        if self._session.created_at.tzinfo is None or self._session.expires_at.tzinfo is None:
            return self._degrade(
                DownstreamToolFailure.IDENTITY_DRIFT,
                "Tool Session timestamps must include timezone",
                operation=operation,
            )
        now = self._now()
        if self._session.expires_at.astimezone(timezone.utc) <= now:
            return self._degrade(
                DownstreamToolFailure.SESSION_EXPIRED,
                "Tool Session is expired",
                operation=operation,
            )
        if self._session.created_at.astimezone(timezone.utc) > now:
            return self._degrade(
                DownstreamToolFailure.IDENTITY_DRIFT,
                "Tool Session creation time is in the future",
                operation=operation,
            )
        if require_active and not self._active:
            return self._degrade(
                DownstreamToolFailure.UNAUTHORIZED,
                "Tool Session is not active",
                operation=operation,
            )
        return None

    def _validate_returned_tools(self, tools: list[ToolDescriptor]) -> None:
        if [tool.operation for tool in tools] != self._session.allowed_operations:
            raise ToolSessionAuthorizationError(
                "Tool Gateway subset identity drifted from the frozen Tool Session"
            )
        max_risk = {"R0": 0, "R1": 1}[self._session.max_risk]
        for tool in tools:
            if (
                tool.availability != "VERIFIED"
                or tool.access != "read"
                or tool.risk not in {"R0", "R1"}
                or {"R0": 0, "R1": 1}.get(tool.risk, 2) > max_risk
                or tool.contract_sha256 != self._session.contract_sha256[tool.operation]
            ):
                raise ToolSessionAuthorizationError(
                    "Tool Gateway returned a non-Verified, non-read-only, or stale tool"
                )

    def _degrade_exception(
        self,
        exc: Exception,
        *,
        operation: str | None = None,
    ) -> DownstreamToolOutcome:
        if isinstance(exc, ToolSessionBudgetError):
            failure = DownstreamToolFailure.BUDGET_EXHAUSTED
        elif isinstance(exc, ToolSessionAuthorizationError):
            message = str(exc).lower()
            if "expired" in message:
                failure = DownstreamToolFailure.SESSION_EXPIRED
            elif any(
                marker in message
                for marker in ("identity", "drift", "stale", "release", "catalog", "contract")
            ):
                failure = DownstreamToolFailure.IDENTITY_DRIFT
            else:
                failure = DownstreamToolFailure.UNAUTHORIZED
        elif isinstance(exc, ToolGatewayError):
            failure = DownstreamToolFailure.GATEWAY_FAILURE
        else:
            failure = DownstreamToolFailure.GATEWAY_FAILURE
        return self._degrade(failure, str(exc) or type(exc).__name__, operation=operation)

    def _degrade(
        self,
        failure: DownstreamToolFailure,
        message: str,
        *,
        operation: str | None = None,
    ) -> DownstreamToolOutcome:
        self._active = False
        self._terminal_failure = failure
        return self._failure_outcome(failure, message, operation=operation)

    def _failure_outcome(
        self,
        failure: DownstreamToolFailure,
        message: str,
        *,
        operation: str | None = None,
    ) -> DownstreamToolOutcome:
        return DownstreamToolOutcome(
            status="DEGRADED",
            session_id=self._session.session_id,
            operation=operation,
            failure=failure,
            message=message[:1_000] or "Tool Session failed closed",
            retry_allowed=False,
        )

    def _success(
        self,
        status: Literal["READY", "SUCCEEDED"],
        message: str,
        *,
        operation: str | None = None,
        tools: list[ToolDescriptor] | None = None,
        invocation: ToolInvocationResult | None = None,
    ) -> DownstreamToolOutcome:
        return DownstreamToolOutcome(
            status=status,
            session_id=self._session.session_id,
            operation=operation,
            tools=tools or [],
            invocation=invocation,
            message=message,
        )

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            raise ValueError("downstream Tool Session clock must include timezone")
        return value.astimezone(timezone.utc)
