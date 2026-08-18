from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from rolo.core.models import ToolDescriptor, utc_now
from rolo.stages.contracts import AgentRequirement


class AdaptPlanStatus(str, Enum):
    BLOCKED = "BLOCKED"
    REQUIRES_CODING = "REQUIRES_CODING"


class AdapterAgentConfig(BaseModel):
    """Secret-free provider selection persisted with a Stage 1 Adapt plan."""

    provider: str = Field(default="codex", min_length=1)
    executor: str = Field(default="codex", min_length=1)
    base_url: str | None = None
    model: str | None = None
    api_key_env: str = "CODING_AGENT_API_KEY"
    api_key_configured: bool = False
    auto_install: bool = True
    require_auth: bool = True


class AdapterAgentDependencyStatus(str, Enum):
    READY = "READY"
    INSTALLED = "INSTALLED"
    INSTALL_REQUIRED = "INSTALL_REQUIRED"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    UNSUPPORTED = "UNSUPPORTED"
    FAILED = "FAILED"


class AdapterAgentDependencyReport(BaseModel):
    """Secret-free installation and authentication readiness evidence."""

    schema_version: Literal["robot-adapter-agent-dependency/v1"] = (
        "robot-adapter-agent-dependency/v1"
    )
    executor: str
    provider: str
    status: AdapterAgentDependencyStatus
    platform: str
    architecture: str
    executable: str | None = None
    version: str | None = None
    installed: bool = False
    install_attempted: bool = False
    install_source: str | None = None
    authentication: str = "NOT_CHECKED"
    messages: list[str] = Field(default_factory=list)
    checked_at: datetime = Field(default_factory=utc_now)

class AdapterAgentRunStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"


class AdapterOutputRefs(BaseModel):
    """Workspace-relative outputs proposed for independent promotion."""

    tool_catalog: str
    state_graph: str
    conformance_report: str


class AdapterAgentResult(BaseModel):
    """Structured final message produced by the Stage 1 Adapter Agent."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-adapter-agent-result/v1"]
    summary: str
    completed_tasks: list[str]
    changed_files: list[str]
    validation: list[str]
    blockers: list[str]
    handoff_ready: bool
    outputs: AdapterOutputRefs | None = None

class OperationConformance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: str
    schema_valid: bool
    errors_valid: bool
    idempotency_valid: bool
    cancellation_valid: bool
    safety_valid: bool
    physical_result_valid: bool | None = None
    evidence: list[str] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(
            (
                self.schema_valid,
                self.errors_valid,
                self.idempotency_valid,
                self.cancellation_valid,
                self.safety_valid,
            )
        )


class AdapterConformanceReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-adapter-conformance/v1"] = (
        "robot-adapter-conformance/v1"
    )
    robot_id: str
    discovery_id: str
    operations: list[OperationConformance]


class StateGraphBaseline(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: Literal["robot-state-graph/v1"] = "robot-state-graph/v1"
    robot_id: str
    discovery_id: str
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]


class ToolCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-tool-catalog/v1"] = "robot-tool-catalog/v1"
    robot_id: str
    discovery_id: str
    tools: list[ToolDescriptor]


class AdapterHandoff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-adapter-handoff/v1"] = "robot-adapter-handoff/v1"
    robot_id: str
    source_discovery_id: str
    source_agent_run_id: str
    discovery_manifest_ref: str
    discovery_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    tool_catalog_ref: str
    tool_catalog_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    state_graph_ref: str
    state_graph_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    conformance_report_ref: str
    conformance_report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    gate_report_ref: str
    gate_report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    promoted_at: datetime = Field(default_factory=utc_now)


class AdapterOutputSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-adapter-output-snapshot/v1"] = (
        "robot-adapter-output-snapshot/v1"
    )
    run_id: str
    robot_id: str
    discovery_id: str
    tool_catalog_ref: str
    tool_catalog_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    state_graph_ref: str
    state_graph_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    conformance_report_ref: str
    conformance_report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime = Field(default_factory=utc_now)


class AdaptGateStatus(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"


class AdaptGateReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-adapt-gate/v1"] = "robot-adapt-gate/v1"
    run_id: str
    robot_id: str
    discovery_id: str
    status: AdaptGateStatus
    checks: list[str] = Field(default_factory=list)
    error: str | None = None
    checked_at: datetime = Field(default_factory=utc_now)


class AdaptRunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-adapt-run-summary/v1"] = (
        "robot-adapt-run-summary/v1"
    )
    robot_id: str
    run_id: str
    status: Literal["COMPLETE"] = "COMPLETE"
    agent_run_ref: str
    snapshot_ref: str
    gate_ref: str
    handoff_ref: str


class AdaptLatestIndex(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-adapt-latest/v1"] = "robot-adapt-latest/v1"
    robot_id: str
    run_id: str
    handoff_ref: str
    handoff_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    published_at: datetime = Field(default_factory=utc_now)


class AdapterAgentRun(BaseModel):
    """Secret-free execution metadata retained for audit and diagnosis."""

    schema_version: Literal["robot-adapter-agent-run/v1"] = "robot-adapter-agent-run/v1"
    run_id: str
    robot_id: str
    source_discovery_id: str
    provider: str
    model: str | None = None
    status: AdapterAgentRunStatus
    workspace: str
    sandbox: str = "workspace-write"
    command: list[str]
    prompt_ref: str
    event_log_ref: str
    stderr_ref: str
    final_message_ref: str
    result_ref: str | None = None
    thread_id: str | None = None
    event_count: int = 0
    exit_code: int | None = None
    error: str | None = None
    started_at: datetime
    completed_at: datetime
    duration_s: float = Field(ge=0.0)

class AdaptTask(BaseModel):
    id: str
    description: str
    operations: list[str] = Field(default_factory=list)
    required_skill: str
    agent_requirement: AgentRequirement = AgentRequirement.ADAPTER_AGENT


class AdaptPlan(BaseModel):
    schema_version: Literal["robot-adapt-plan/v1"] = "robot-adapt-plan/v1"
    stage: str = "adapt"
    robot_id: str
    source_discovery_id: str
    status: AdaptPlanStatus
    tasks: list[AdaptTask]
    required_skills: list[str]
    adapter_agent: AdapterAgentConfig = Field(default_factory=AdapterAgentConfig)
    candidate_operations: list[str] = Field(default_factory=list)
    semantic_context_ref: str = ""
    unresolved_semantics: list[str] = Field(default_factory=list)
    semantic_value_candidates: int = 0
    active_discovery_report_ref: str = ""
    robot_wiki_ref: str = ""
    discovery_manifest_ref: str = ""
    discovery_manifest_sha256: str = ""
    state_graph_baseline_required: bool = True
    handoff_ref: str
    created_at: datetime = Field(default_factory=utc_now)
