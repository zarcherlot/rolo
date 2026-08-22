from __future__ import annotations

import hashlib
import hmac
import json
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from rolo.adapter_runner import AdapterRunner
from rolo.adapter_runtime import invoke_adapter, load_current_release
from rolo.core.models import ToolDescriptor
from rolo.stages.adapt.agent_contracts import (
    OperationRegistryResolver,
    ToolSessionDescriptor,
    validate_tool_session_descriptor,
)

_RISK_ORDER = {"R0": 0, "R1": 1, "R2": 2, "R3": 3}


class ToolGatewayError(ValueError):
    """Base error for a denied or failed Tool Gateway request."""


class ToolSessionNotFoundError(ToolGatewayError):
    """The requested session does not exist."""


class ToolSessionAuthorizationError(ToolGatewayError):
    """The caller did not present authority for the frozen session."""


class ToolSessionBudgetError(ToolGatewayError):
    """The frozen session has exhausted one of its hard budgets."""


class ConcurrentToolInvocationError(ToolGatewayError):
    """Only one invocation may execute in a session at a time."""


class ToolGatewayPolicy(BaseModel):
    """Deployment policy applied in addition to a session's narrower authority."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-tool-gateway-policy/v1"] = "rolo-tool-gateway-policy/v1"
    policy_version: str = Field(min_length=1, max_length=128)
    allowed_callers: list[str] = Field(min_length=1, max_length=256)
    allowed_stages: list[Literal["diagnose", "verify"]] = Field(
        default_factory=lambda: ["diagnose", "verify"]
    )
    max_risk: Literal["R0", "R1"] = "R1"
    max_operations: int = Field(default=256, ge=1, le=2_048)
    max_session_calls: int = Field(default=1_000, ge=1, le=10_000)
    max_session_elapsed_s: float = Field(default=3_600, gt=0, le=86_400)
    max_session_result_bytes: int = Field(
        default=64_000_000,
        ge=1,
        le=1_000_000_000,
    )
    max_session_ttl_s: float = Field(default=3_600, gt=0, le=86_400)
    max_invocation_timeout_s: float = Field(default=60, gt=0, le=3_600)

    @field_validator("allowed_callers", "allowed_stages")
    @classmethod
    def require_unique_authority(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Tool Gateway policy authority lists must be unique")
        return value


class ToolInvocationResult(BaseModel):
    """Bounded result envelope returned to a downstream Agent."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-tool-invocation-result/v1"] = (
        "rolo-tool-invocation-result/v1"
    )
    session_id: str
    operation: str
    call_index: int = Field(ge=1)
    result: dict[str, Any] | None
    result_bytes: int = Field(ge=0)
    result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    truncated: bool = False
    audit_ref: str

    @model_validator(mode="after")
    def require_omitted_truncated_result(self) -> ToolInvocationResult:
        if self.truncated != (self.result is None):
            raise ValueError("only a truncated result may omit its payload")
        return self


@dataclass
class _SessionState:
    descriptor: ToolSessionDescriptor
    calls: int = 0
    result_bytes: int = 0
    closed: bool = False
    invoke_lock: threading.Lock = field(default_factory=threading.Lock)


RuntimeInvoker = Callable[..., dict[str, Any]]
SessionAuthorizer = Callable[[ToolSessionDescriptor, str], bool]


def tool_session_descriptor_sha256(descriptor: ToolSessionDescriptor) -> str:
    """Return the canonical digest a trusted issuer must authorize out of band."""
    encoded = json.dumps(
        descriptor.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class ToolGateway:
    """Session-scoped facade over the immutable Adapter Runtime.

    The gateway never exposes the global Tool Catalog. Every operation is release-bound,
    Registry-bound, read-only, Verified, R0/R1, budgeted, and independently audited.
    """

    def __init__(
        self,
        *,
        output_root: Path,
        artifact_root: Path,
        resolver: OperationRegistryResolver,
        policy: ToolGatewayPolicy,
        session_authorizer: SessionAuthorizer,
        gateway_audit_path: Path,
        runtime_policy_path: Path | None = None,
        runtime_audit_path: Path | None = None,
        runner: AdapterRunner | None = None,
        runtime_invoker: RuntimeInvoker = invoke_adapter,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.output_root = output_root
        self.artifact_root = artifact_root
        self.resolver = resolver
        self.policy = ToolGatewayPolicy.model_validate(policy.model_dump())
        self._session_authorizer = session_authorizer
        self.gateway_audit_path = gateway_audit_path
        self.runtime_policy_path = runtime_policy_path
        self.runtime_audit_path = runtime_audit_path
        self.runner = runner
        self._runtime_invoker = runtime_invoker
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._sessions: dict[str, _SessionState] = {}
        self._sessions_lock = threading.Lock()
        self._audit_lock = threading.Lock()

    def open_session(self, descriptor: ToolSessionDescriptor) -> None:
        """Admit only an out-of-band-issued session after all deterministic checks.

        ``session_authorizer`` is a trusted deployment boundary. It must compare the
        canonical descriptor digest with a protected issuer record or verify an equivalent
        signed artifact. Fields asserted inside the caller-provided descriptor are never
        treated as proof of issuance.
        """
        frozen_descriptor = ToolSessionDescriptor.model_validate(descriptor.model_dump())
        descriptor_sha256 = tool_session_descriptor_sha256(frozen_descriptor)
        try:
            try:
                issued = self._session_authorizer(
                    frozen_descriptor,
                    descriptor_sha256,
                )
            except Exception as exc:
                raise ToolSessionAuthorizationError(
                    "trusted Tool Session issuer rejected the descriptor"
                ) from exc
            if issued is not True:
                raise ToolSessionAuthorizationError(
                    "descriptor has no matching trusted Tool Session issuance"
                )
            self._validate_descriptor_policy(frozen_descriptor)
            validate_tool_session_descriptor(frozen_descriptor, self.resolver)
            self._bound_tools(frozen_descriptor)
            with self._sessions_lock:
                if frozen_descriptor.session_id in self._sessions:
                    raise ToolGatewayError("Tool Session ID is already registered")
                self._sessions[frozen_descriptor.session_id] = _SessionState(
                    descriptor=frozen_descriptor
                )
        except Exception as exc:
            self._audit(
                action="OPEN",
                outcome="DENIED",
                session_id=descriptor.session_id,
                robot_id=descriptor.robot_id,
                reason=str(exc),
                session_descriptor_sha256=descriptor_sha256,
            )
            raise
        self._audit(
            action="OPEN",
            outcome="ALLOWED",
            session_id=descriptor.session_id,
            robot_id=descriptor.robot_id,
            reason=(
                "trusted issuance, Registry, release, and Tool Gateway policy identities "
                "matched"
            ),
            session_descriptor_sha256=descriptor_sha256,
        )

    def list_tools(self, session_id: str, nonce: str) -> list[ToolDescriptor]:
        """Return only the frozen session subset, never the global Tool Catalog."""
        state = self._authenticate(session_id, nonce, action="LIST")
        try:
            tools = self._bound_tools(state.descriptor)
        except Exception as exc:
            self._audit_state(state, action="LIST", outcome="DENIED", reason=str(exc))
            raise
        self._audit_state(
            state,
            action="LIST",
            outcome="ALLOWED",
            reason=f"returned {len(tools)} session-scoped tools",
        )
        return tools

    def invoke(
        self,
        session_id: str,
        nonce: str,
        operation: str,
        payload: dict[str, Any],
        *,
        timeout_s: float | None = None,
    ) -> ToolInvocationResult:
        """Invoke one pinned operation through Adapter Runtime and return a bounded envelope."""
        state = self._authenticate(session_id, nonce, action="INVOKE", operation=operation)
        if not state.invoke_lock.acquire(blocking=False):
            error = ConcurrentToolInvocationError(
                "a Tool Session cannot execute concurrent invocations"
            )
            self._audit_state(
                state,
                action="INVOKE",
                outcome="DENIED",
                reason=str(error),
                operation=operation,
            )
            raise error
        try:
            return self._invoke_locked(state, operation, payload, timeout_s=timeout_s)
        finally:
            state.invoke_lock.release()

    def close_session(self, session_id: str, nonce: str) -> None:
        """Cancel future calls for a session; an in-flight bounded Runtime call is unaffected."""
        state = self._authenticate(session_id, nonce, action="CLOSE")
        state.closed = True
        self._audit_state(
            state,
            action="CLOSE",
            outcome="ALLOWED",
            reason="Tool Session was closed",
        )

    def _invoke_locked(
        self,
        state: _SessionState,
        operation: str,
        payload: dict[str, Any],
        *,
        timeout_s: float | None,
    ) -> ToolInvocationResult:
        descriptor = state.descriptor
        payload_sha256 = self._safe_json_sha256(payload)
        try:
            self._require_json_payload(payload)
            tools = {tool.operation: tool for tool in self._bound_tools(descriptor)}
            tool = tools.get(operation)
            if tool is None:
                raise ToolSessionAuthorizationError(
                    "operation is outside the frozen Tool Session"
                )
            self._validate_budget(state)
            remaining_s = descriptor.budget.max_elapsed_s - self._elapsed_s(descriptor)
            requested_timeout = timeout_s if timeout_s is not None else tool.max_duration_s
            if requested_timeout <= 0:
                raise ToolGatewayError("invocation timeout must be positive")
            effective_timeout = min(
                requested_timeout,
                tool.max_duration_s,
                self.policy.max_invocation_timeout_s,
                remaining_s,
            )
            if effective_timeout <= 0:
                raise ToolSessionBudgetError("Tool Session elapsed-time budget is exhausted")
            state.calls += 1
            call_index = state.calls
            result = self._runtime_invoker(
                self.output_root,
                descriptor.robot_id,
                operation,
                payload,
                artifact_root=self.artifact_root,
                timeout_s=effective_timeout,
                policy_path=self.runtime_policy_path,
                audit_path=self.runtime_audit_path,
                runner=self.runner,
                expected_release_id=descriptor.release_id,
                expected_target_fingerprint_sha256=descriptor.target_fingerprint_sha256,
                expected_tool_catalog_sha256=descriptor.tool_catalog_sha256,
                expected_state_graph_sha256=descriptor.state_graph_sha256,
            )
            encoded = json.dumps(
                result,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            result_sha256 = hashlib.sha256(encoded).hexdigest()
            remaining_bytes = descriptor.budget.max_result_bytes - state.result_bytes
            truncated = len(encoded) > remaining_bytes
            state.result_bytes = min(
                descriptor.budget.max_result_bytes,
                state.result_bytes + len(encoded),
            )
            audit_ref = self._audit_state(
                state,
                action="INVOKE",
                outcome="TRUNCATED" if truncated else "ALLOWED",
                reason=(
                    "result exceeded the remaining session byte budget"
                    if truncated
                    else "Adapter Runtime invocation completed"
                ),
                operation=operation,
                payload_sha256=payload_sha256,
                result_sha256=result_sha256,
                result_bytes=len(encoded),
            )
            return ToolInvocationResult(
                session_id=descriptor.session_id,
                operation=operation,
                call_index=call_index,
                result=None if truncated else result,
                result_bytes=len(encoded),
                result_sha256=result_sha256,
                truncated=truncated,
                audit_ref=audit_ref,
            )
        except Exception as exc:
            self._audit_state(
                state,
                action="INVOKE",
                outcome="DENIED" if isinstance(exc, ToolGatewayError) else "FAILED",
                reason=str(exc),
                operation=operation,
                payload_sha256=payload_sha256,
            )
            raise

    def _authenticate(
        self,
        session_id: str,
        nonce: str,
        *,
        action: str,
        operation: str | None = None,
    ) -> _SessionState:
        with self._sessions_lock:
            state = self._sessions.get(session_id)
        if state is None:
            error = ToolSessionNotFoundError("Tool Session is not registered")
            self._audit(
                action=action,
                outcome="DENIED",
                session_id=session_id,
                robot_id=None,
                reason=str(error),
                operation=operation,
            )
            raise error
        try:
            if not isinstance(nonce, str) or not hmac.compare_digest(
                state.descriptor.nonce, nonce
            ):
                raise ToolSessionAuthorizationError("Tool Session nonce does not match")
            if state.closed:
                raise ToolSessionAuthorizationError("Tool Session is closed")
            self._validate_time(state.descriptor)
        except Exception as exc:
            self._audit_state(
                state,
                action=action,
                outcome="DENIED",
                reason=str(exc),
                operation=operation,
            )
            raise
        return state

    def _validate_descriptor_policy(self, descriptor: ToolSessionDescriptor) -> None:
        self._validate_time(descriptor)
        if descriptor.policy_version != self.policy.policy_version:
            raise ToolSessionAuthorizationError("Tool Session policy version is stale")
        if descriptor.caller not in self.policy.allowed_callers:
            raise ToolSessionAuthorizationError("Tool Session caller is not authorized")
        if descriptor.stage not in self.policy.allowed_stages:
            raise ToolSessionAuthorizationError("Tool Session stage is not authorized")
        if _RISK_ORDER[descriptor.max_risk] > _RISK_ORDER[self.policy.max_risk]:
            raise ToolSessionAuthorizationError("Tool Session risk exceeds gateway policy")
        if len(descriptor.allowed_operations) > self.policy.max_operations:
            raise ToolSessionAuthorizationError("Tool Session operation subset is too large")
        if descriptor.budget.max_calls > self.policy.max_session_calls:
            raise ToolSessionAuthorizationError("Tool Session call budget exceeds policy")
        if descriptor.budget.max_elapsed_s > self.policy.max_session_elapsed_s:
            raise ToolSessionAuthorizationError("Tool Session elapsed budget exceeds policy")
        if descriptor.budget.max_result_bytes > self.policy.max_session_result_bytes:
            raise ToolSessionAuthorizationError("Tool Session result budget exceeds policy")
        ttl_s = (descriptor.expires_at - descriptor.created_at).total_seconds()
        if ttl_s > self.policy.max_session_ttl_s:
            raise ToolSessionAuthorizationError("Tool Session TTL exceeds policy")

    def _validate_time(self, descriptor: ToolSessionDescriptor) -> None:
        if descriptor.created_at.tzinfo is None or descriptor.expires_at.tzinfo is None:
            raise ToolSessionAuthorizationError("Tool Session timestamps must include timezone")
        now = self._now()
        if descriptor.created_at.astimezone(timezone.utc) > now:
            raise ToolSessionAuthorizationError("Tool Session creation time is in the future")
        if descriptor.expires_at.astimezone(timezone.utc) <= now:
            raise ToolSessionAuthorizationError("Tool Session is expired")

    def _validate_budget(self, state: _SessionState) -> None:
        budget = state.descriptor.budget
        if state.calls >= budget.max_calls:
            raise ToolSessionBudgetError("Tool Session call budget is exhausted")
        if self._elapsed_s(state.descriptor) >= budget.max_elapsed_s:
            raise ToolSessionBudgetError("Tool Session elapsed-time budget is exhausted")
        if state.result_bytes >= budget.max_result_bytes:
            raise ToolSessionBudgetError("Tool Session result-byte budget is exhausted")

    def _bound_tools(self, descriptor: ToolSessionDescriptor) -> list[ToolDescriptor]:
        _, release, _, catalog = load_current_release(
            self.output_root,
            descriptor.robot_id,
            artifact_root=self.artifact_root,
        )
        expected_release = (
            descriptor.release_id,
            descriptor.target_fingerprint_sha256,
            descriptor.tool_catalog_sha256,
            descriptor.state_graph_sha256,
            descriptor.contract_catalog_sha256,
        )
        actual_release = (
            release.release_id,
            release.target_fingerprint_sha256,
            release.tool_catalog_sha256,
            release.state_graph_sha256,
            catalog.contract_catalog_sha256,
        )
        if expected_release != actual_release:
            raise ToolSessionAuthorizationError(
                "active release identity does not match the frozen Tool Session"
            )
        by_operation = {tool.operation: tool for tool in catalog.tools}
        tools: list[ToolDescriptor] = []
        for operation in descriptor.allowed_operations:
            tool = by_operation.get(operation)
            if tool is None:
                raise ToolSessionAuthorizationError(
                    f"session operation is absent from the active Tool Catalog: {operation}"
                )
            if tool.availability != "VERIFIED":
                raise ToolSessionAuthorizationError(
                    f"session operation is not Verified: {operation}"
                )
            if tool.access != "read" or tool.risk not in {"R0", "R1"}:
                raise ToolSessionAuthorizationError(
                    f"session operation is outside the read-only R0/R1 MVP: {operation}"
                )
            if _RISK_ORDER[tool.risk] > _RISK_ORDER[descriptor.max_risk]:
                raise ToolSessionAuthorizationError(
                    f"session operation exceeds its risk ceiling: {operation}"
                )
            if tool.contract_sha256 != descriptor.contract_sha256[operation]:
                raise ToolSessionAuthorizationError(
                    f"session operation contract is stale: {operation}"
                )
            tools.append(tool.model_copy(deep=True))
        return tools

    def _elapsed_s(self, descriptor: ToolSessionDescriptor) -> float:
        return max(
            0.0,
            (self._now() - descriptor.created_at.astimezone(timezone.utc)).total_seconds(),
        )

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            raise ToolGatewayError("Tool Gateway clock must include timezone")
        return value.astimezone(timezone.utc)

    @staticmethod
    def _canonical_json_bytes(value: object) -> bytes:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")

    @classmethod
    def _safe_json_sha256(cls, value: object) -> str:
        """Hash JSON inputs without letting malformed values break failure auditing."""
        try:
            encoded = cls._canonical_json_bytes(value)
        except (TypeError, ValueError):
            encoded = b"rolo-invalid-json-payload/v1"
        return hashlib.sha256(encoded).hexdigest()

    @classmethod
    def _require_json_payload(cls, payload: object) -> None:
        if not isinstance(payload, dict) or any(
            not isinstance(key, str) for key in payload
        ):
            raise ToolGatewayError("tool payload must be a JSON object with string keys")
        try:
            cls._canonical_json_bytes(payload)
        except (TypeError, ValueError) as exc:
            raise ToolGatewayError("tool payload must be JSON-serializable") from exc

    def _audit_state(
        self,
        state: _SessionState,
        *,
        action: str,
        outcome: str,
        reason: str,
        operation: str | None = None,
        payload_sha256: str | None = None,
        result_sha256: str | None = None,
        result_bytes: int | None = None,
    ) -> str:
        return self._audit(
            action=action,
            outcome=outcome,
            session_id=state.descriptor.session_id,
            robot_id=state.descriptor.robot_id,
            release_id=state.descriptor.release_id,
            caller=state.descriptor.caller,
            stage=state.descriptor.stage,
            reason=reason,
            operation=operation,
            call_count=state.calls,
            result_budget_used=state.result_bytes,
            payload_sha256=payload_sha256,
            result_sha256=result_sha256,
            result_bytes=result_bytes,
        )

    def _audit(
        self,
        *,
        action: str,
        outcome: str,
        session_id: str,
        robot_id: str | None,
        reason: str,
        operation: str | None = None,
        release_id: str | None = None,
        caller: str | None = None,
        stage: str | None = None,
        call_count: int | None = None,
        result_budget_used: int | None = None,
        payload_sha256: str | None = None,
        result_sha256: str | None = None,
        result_bytes: int | None = None,
        session_descriptor_sha256: str | None = None,
    ) -> str:
        event_id = str(uuid4())
        record = {
            "schema_version": "rolo-tool-gateway-audit/v1",
            "event_id": event_id,
            "observed_at": self._now().isoformat(),
            "policy_version": self.policy.policy_version,
            "action": action,
            "outcome": outcome,
            "session_id": session_id,
            "robot_id": robot_id,
            "release_id": release_id,
            "caller": caller,
            "stage": stage,
            "operation": operation,
            "reason": reason[:1_000],
            "call_count": call_count,
            "result_budget_used": result_budget_used,
            "payload_sha256": payload_sha256,
            "result_sha256": result_sha256,
            "result_bytes": result_bytes,
            "session_descriptor_sha256": session_descriptor_sha256,
        }
        try:
            with self._audit_lock:
                self.gateway_audit_path.parent.mkdir(parents=True, exist_ok=True)
                with self.gateway_audit_path.open("a", encoding="utf-8") as stream:
                    stream.write(
                        json.dumps(record, ensure_ascii=False, separators=(",", ":"))
                    )
                    stream.write("\n")
                    stream.flush()
        except OSError as exc:
            raise ToolGatewayError(f"Tool Gateway audit failed: {exc}") from exc
        return f"audit:{event_id}"
