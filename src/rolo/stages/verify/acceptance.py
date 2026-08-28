"""Provider-neutral acceptance cases and deterministic Oracle execution.

The runner is intentionally independent of Codex/Claude and only accepts a frozen
``DownstreamToolConsumer``.  It therefore cannot acquire a new operation or turn an
Agent's prose into release authority.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

from rolo.core.artifacts import ArtifactStore
from rolo.stages.artifact_paths import ArtifactLayout
from rolo.stages.downstream_tools import DownstreamToolConsumer, DownstreamToolOutcome


class OracleKind(str, Enum):
    FIELD_EQUALS = "FIELD_EQUALS"
    FIELD_EXISTS = "FIELD_EXISTS"
    NUMERIC_BETWEEN = "NUMERIC_BETWEEN"
    STATUS_IN = "STATUS_IN"


class VerificationOracle(BaseModel):
    """A deterministic assertion over one bounded tool result."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-verification-oracle/v1"] = "rolo-verification-oracle/v1"
    kind: OracleKind
    path: str = Field(min_length=1, max_length=256)
    expected: JsonValue | None = None
    minimum: float | None = None
    maximum: float | None = None

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        if value.startswith(".") or ".." in value or any(part == "" for part in value.split(".")):
            raise ValueError("oracle path must be a non-empty dotted JSON path")
        return value

    @field_validator("maximum")
    @classmethod
    def validate_maximum(cls, value: float | None, info) -> float | None:
        minimum = info.data.get("minimum")
        if value is not None and minimum is not None and value < minimum:
            raise ValueError("oracle maximum must be greater than or equal to minimum")
        return value

    @model_validator(mode="after")
    def validate_kind_parameters(self) -> VerificationOracle:
        if (
            self.kind == OracleKind.NUMERIC_BETWEEN
            and self.minimum is None
            and self.maximum is None
        ):
            raise ValueError("numeric oracle requires minimum or maximum")
        if self.kind == OracleKind.STATUS_IN and not isinstance(self.expected, list):
            raise ValueError("STATUS_IN oracle expected value must be a list")
        return self


class VerificationCase(BaseModel):
    """One read-only operation invocation and its Oracle."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-verification-case/v1"] = "rolo-verification-case/v1"
    case_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,127}$")
    operation: str = Field(min_length=1, max_length=256)
    payload: dict[str, JsonValue] = Field(default_factory=dict)
    oracle: VerificationOracle
    timeout_s: float = Field(default=30.0, gt=0.0, le=600.0)


class VerificationPlan(BaseModel):
    """Bounded, immutable set of acceptance cases."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-verification-plan/v1"] = "rolo-verification-plan/v1"
    robot_id: str = Field(min_length=1, max_length=128)
    cases: list[VerificationCase] = Field(min_length=1, max_length=256)
    max_elapsed_s: float = Field(default=3_600.0, gt=0.0, le=86_400.0)
    source_ref: str | None = None
    source_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @field_validator("cases")
    @classmethod
    def validate_unique_cases(cls, value: list[VerificationCase]) -> list[VerificationCase]:
        ids = [item.case_id for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError("verification case IDs must be unique")
        return value

    @model_validator(mode="after")
    def validate_source_pair(self) -> VerificationPlan:
        if bool(self.source_ref) != bool(self.source_sha256):
            raise ValueError(
                "verification plan source reference and hash must be provided together"
            )
        return self


class VerificationCaseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-verification-case-result/v1"] = (
        "rolo-verification-case-result/v1"
    )
    case_id: str
    operation: str
    status: Literal["PASS", "FAIL", "TIMEOUT", "CANCELLED", "ERROR"]
    message: str = Field(min_length=1, max_length=2_000)
    audit_ref: str | None = None
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class VerificationRunReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-verification-run/v1"] = "rolo-verification-run/v1"
    run_id: str
    robot_id: str
    status: Literal["PASS", "FAIL", "CANCELLED"]
    case_results: list[VerificationCaseResult]
    evidence_ref: str
    started_at: datetime
    completed_at: datetime


def _lookup(payload: Mapping[str, Any], path: str) -> tuple[bool, Any]:
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return False, None
        current = current[part]
    return True, current


def evaluate_oracle(
    oracle: VerificationOracle, result: Mapping[str, Any] | None
) -> tuple[bool, str]:
    """Evaluate an Oracle without executing code supplied by an Agent."""

    payload = result or {}
    exists, value = _lookup(payload, oracle.path)
    if oracle.kind == OracleKind.FIELD_EXISTS:
        return exists, "field exists" if exists else f"missing field: {oracle.path}"
    if oracle.kind == OracleKind.FIELD_EQUALS:
        ok = exists and value == oracle.expected
        return ok, "field equals expected value" if ok else f"field mismatch: {oracle.path}"
    if oracle.kind == OracleKind.STATUS_IN:
        expected = oracle.expected
        allowed = expected if isinstance(expected, list) else [expected]
        ok = exists and value in allowed
        return ok, "status is allowed" if ok else f"status is not allowed: {oracle.path}"
    if not exists or isinstance(value, bool) or not isinstance(value, (int, float)):
        return False, f"numeric field is missing or not numeric: {oracle.path}"
    if oracle.minimum is not None and value < oracle.minimum:
        return False, f"numeric value is below minimum: {oracle.path}"
    if oracle.maximum is not None and value > oracle.maximum:
        return False, f"numeric value is above maximum: {oracle.path}"
    return True, "numeric value is within bounds"


def run_verification_plan(
    plan: VerificationPlan,
    *,
    consumer: DownstreamToolConsumer,
    artifacts: ArtifactStore,
    cancel_event: threading.Event | None = None,
    clock: Callable[[], datetime] | None = None,
    run_id: str | None = None,
) -> VerificationRunReport:
    """Execute bounded read-only cases and persist one tamper-evident evidence artifact."""

    now = clock or (lambda: datetime.now(timezone.utc))
    started = now().astimezone(timezone.utc)
    selected_run = run_id or f"verify-{uuid4().hex}"
    results: list[VerificationCaseResult] = []
    opened = consumer.open()
    if opened.status != "READY":
        results.append(
            VerificationCaseResult(
                case_id="__session__",
                operation="session.open",
                status="ERROR",
                message=opened.message,
            )
        )
    else:
        for case in plan.cases:
            if cancel_event is not None and cancel_event.is_set():
                results.append(
                    VerificationCaseResult(
                        case_id=case.case_id,
                        operation=case.operation,
                        status="CANCELLED",
                        message="verification cancellation requested before invocation",
                    )
                )
                break
            if (now().astimezone(timezone.utc) - started).total_seconds() >= plan.max_elapsed_s:
                results.append(
                    VerificationCaseResult(
                        case_id=case.case_id,
                        operation=case.operation,
                        status="TIMEOUT",
                        message="verification elapsed-time budget exhausted",
                    )
                )
                break
            outcome: DownstreamToolOutcome = consumer.invoke(
                case.operation, dict(case.payload), timeout_s=case.timeout_s
            )
            if outcome.status != "SUCCEEDED" or outcome.invocation is None:
                status: Literal["FAIL", "TIMEOUT", "ERROR"] = "ERROR"
                if outcome.failure and outcome.failure.value in {
                    "GATEWAY_FAILURE",
                    "BUDGET_EXHAUSTED",
                }:
                    status = "TIMEOUT"
                results.append(
                    VerificationCaseResult(
                        case_id=case.case_id,
                        operation=case.operation,
                        status=status,
                        message=outcome.message,
                    )
                )
                continue
            passed, message = evaluate_oracle(case.oracle, outcome.invocation.result)
            results.append(
                VerificationCaseResult(
                    case_id=case.case_id,
                    operation=case.operation,
                    status="PASS" if passed else "FAIL",
                    message=message,
                    audit_ref=outcome.invocation.audit_ref,
                )
            )
        closed = consumer.close()
        if closed.status != "SUCCEEDED":
            results.append(
                VerificationCaseResult(
                    case_id="__session_close__",
                    operation="session.close",
                    status="ERROR",
                    message=closed.message,
                )
            )
    completed = now().astimezone(timezone.utc)
    status: Literal["PASS", "FAIL", "CANCELLED"] = "PASS"
    if any(item.status == "CANCELLED" for item in results):
        status = "CANCELLED"
    elif any(item.status != "PASS" for item in results):
        status = "FAIL"
    relative = f"verify/{plan.robot_id}/runs/{selected_run}/verification_evidence.json"
    evidence_path = artifacts.write_json(
        relative,
        {
            "schema_version": "rolo-verification-evidence/v1",
            "plan": plan.model_dump(mode="json"),
            "results": [item.model_dump(mode="json") for item in results],
        },
    )
    return VerificationRunReport(
        run_id=selected_run,
        robot_id=plan.robot_id,
        status=status,
        case_results=results,
        evidence_ref=ArtifactLayout(artifacts.root).ref(evidence_path),
        started_at=started,
        completed_at=completed,
    )
