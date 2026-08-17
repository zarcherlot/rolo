from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from rolo.core.models import utc_now
from rolo.stages.contracts import AgentRequirement


class BuildPlanStatus(str, Enum):
    BLOCKED = "BLOCKED"
    REQUIRES_CODING = "REQUIRES_CODING"
    READY_FOR_CONFORMANCE = "READY_FOR_CONFORMANCE"


class CodingAgentConfig(BaseModel):
    """Secret-free provider selection persisted with a Stage 1 build plan."""

    provider: str = Field(default="codex", min_length=1)
    executor: str = Field(default="codex", min_length=1)
    base_url: str | None = None
    model: str | None = None
    api_key_env: str = "CODING_AGENT_API_KEY"
    api_key_configured: bool = False
    auto_install: bool = True
    require_auth: bool = True


class CodingAgentDependencyStatus(str, Enum):
    READY = "READY"
    INSTALLED = "INSTALLED"
    INSTALL_REQUIRED = "INSTALL_REQUIRED"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    UNSUPPORTED = "UNSUPPORTED"
    FAILED = "FAILED"


class CodingAgentDependencyReport(BaseModel):
    """Secret-free installation and authentication readiness evidence."""

    schema_version: str = "rolo-coding-agent-dependency/v1"
    executor: str
    provider: str
    status: CodingAgentDependencyStatus
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


class CodingAgentRunStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"


class CodingAgentResult(BaseModel):
    """Structured final message produced by the Stage 1 Coding Agent."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-coding-agent-result/v1"]
    summary: str
    completed_tasks: list[str]
    changed_files: list[str]
    validation: list[str]
    blockers: list[str]
    handoff_ready: bool


class CodingAgentRun(BaseModel):
    """Secret-free execution metadata retained for audit and diagnosis."""

    schema_version: str = "robot-coding-agent-run/v1"
    run_id: str
    robot_id: str
    source_discovery_id: str
    provider: str
    model: str | None = None
    status: CodingAgentRunStatus
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


class BuildTask(BaseModel):
    id: str
    description: str
    operations: list[str] = Field(default_factory=list)
    required_skill: str
    agent_requirement: AgentRequirement = AgentRequirement.CODING_AGENT


class BuildPlan(BaseModel):
    schema_version: str = "robot-build-plan/v1"
    stage: str = "build"
    robot_id: str
    source_discovery_id: str
    status: BuildPlanStatus
    tasks: list[BuildTask]
    required_skills: list[str]
    coding_agent: CodingAgentConfig = Field(default_factory=CodingAgentConfig)
    candidate_operations: list[str] = Field(default_factory=list)
    state_graph_baseline_required: bool = True
    handoff_ref: str
    created_at: datetime = Field(default_factory=utc_now)
