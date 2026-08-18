from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class HealthState(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"


class RobotUseVerdict(str, Enum):
    NORMAL = "NORMAL"
    SUSPECTED_FAILURE = "SUSPECTED_FAILURE"
    FAILURE = "FAILURE"
    UNKNOWN = "UNKNOWN"


class RobotUseModeState(str, Enum):
    DISABLED = "DISABLED"
    RECORDING = "RECORDING"
    POLLING = "POLLING"
    SUSPECTED = "SUSPECTED"
    CORROBORATING = "CORROBORATING"
    DEGRADED = "DEGRADED"
    ARCHIVED = "ARCHIVED"


class ImageFrame(BaseModel):
    timestamp: datetime
    image_url: str | None = None
    artifact_ref: str | None = None
    camera_id: str = "semantic://sensor/front_camera"

    @model_validator(mode="after")
    def require_source(self) -> ImageFrame:
        if not self.image_url and not self.artifact_ref:
            raise ValueError("image_url or artifact_ref is required")
        return self


class RobotUseRequest(BaseModel):
    schema_version: str = "robot-use-request/v1"
    request_id: str
    robot_id: str
    execution_id: str
    test_case_id: str | None = None
    window_start: datetime
    window_end: datetime
    frames: list[ImageFrame] = Field(min_length=1, max_length=16)
    task_contract: dict[str, Any]
    telemetry_summary: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_window(self) -> RobotUseRequest:
        if self.window_end <= self.window_start:
            raise ValueError("window_end must be after window_start")
        return self


class ObservedFact(BaseModel):
    frame_time: datetime | None = None
    fact: str


class CandidateCause(BaseModel):
    cause: str
    confidence: float = Field(ge=0.0, le=1.0)


class TimeInterval(BaseModel):
    start: datetime
    end: datetime


class RobotUseSupervision(BaseModel):
    schema_version: str = "robot-use-supervision/v1"
    request_id: str
    verdict: RobotUseVerdict
    failure_type: str | None = None
    first_abnormal_interval: TimeInterval | None = None
    expected_behavior: str
    observed_facts: list[ObservedFact] = Field(default_factory=list)
    candidate_causes: list[CandidateCause] = Field(default_factory=list)
    requested_checks: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    limitations: list[str] = Field(default_factory=list)
    model: str
    model_response_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class RobotCapability(BaseModel):
    schema_version: str
    robot_id: str
    adapter: str
    platform: dict[str, Any]
    geometry: dict[str, Any]
    sensors: dict[str, Any]
    features: dict[str, Any]


class HealthResponse(BaseModel):
    status: HealthState
    service: str = "rolo-control-plane"
    version: str
    robots: int
    robot_use_backend: str
    openai_key_configured: bool
    timestamp: datetime = Field(default_factory=utc_now)


class ErrorDetail(BaseModel):
    code: str
    message: str
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class DiscoveryStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"
    FAILED = "FAILED"


class ProbeResult(BaseModel):
    layer: str
    status: DiscoveryStatus
    data: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    observed_at: datetime = Field(default_factory=utc_now)


class ToolDescriptor(BaseModel):
    schema_version: str = "robot-tool/v1"
    operation: str
    canonical_cli: list[str]
    layer: str
    description: str
    risk: str = "R0"
    access: str = "read"
    idempotent: bool = True
    cancelable: bool = False
    availability: str
    adapter: str
    input_schema: dict[str, Any] = Field(default_factory=lambda: {"type": "object"})
    output_schema: dict[str, Any] = Field(default_factory=lambda: {"type": "object"})
    capability_requirements: list[str] = Field(default_factory=list)
    preconditions: list[str] = Field(default_factory=list)
    postconditions: list[str] = Field(default_factory=list)
    semantic_bindings: list[str] = Field(default_factory=list)
    side_effects: list[str] = Field(default_factory=list)
    resource_locks: list[str] = Field(default_factory=list)
    max_duration_s: float = 30.0
    rate_limit: str = "on_demand"
    error_codes: list[str] = Field(
        default_factory=lambda: ["UNAVAILABLE", "TIMEOUT", "PROBE_FAILED"]
    )
    retry_policy: str = "bounded_exponential_backoff_for_read_only_probe"
    compensation_operation: str | None = None
    observation_overhead: str = "bounded read-only probe"
    evidence: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class DiscoveryReport(BaseModel):
    schema_version: str = "robot-discovery/v1"
    discovery_id: str
    robot_id: str
    status: DiscoveryStatus
    platform: dict[str, Any]
    capability_manifest: dict[str, Any]
    probes: dict[str, ProbeResult]
    semantic_bindings: dict[str, dict[str, Any]] = Field(default_factory=dict)
    tool_catalog: list[ToolDescriptor] = Field(default_factory=list)
    software_summary: dict[str, Any] = Field(default_factory=dict)
    software_summary_ref: str = ""
    package_inventory_ref: str = ""
    source_roots: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
