from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rolo.core.models import ToolDescriptor, utc_now
from rolo.runtime_context import AdapterRuntimeContext
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

    model_config = ConfigDict(extra="forbid")

    adapter_manifest: str
    adapter_package: str
    state_graph: str
    conformance_report: str


class AdapterAgentFile(BaseModel):
    """Bounded file payload returned through Codex's structured final message."""

    model_config = ConfigDict(extra="forbid")

    path: str
    encoding: Literal["base64"]
    content: str = Field(max_length=24_000_000)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class AdapterAgentResult(BaseModel):
    """Structured final message produced by the Stage 1 Adapter Agent."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[
        "robot-adapter-agent-result/v1", "robot-adapter-agent-result/v2"
    ]
    summary: str
    completed_tasks: list[str]
    changed_files: list[str]
    validation: list[str]
    blockers: list[str]
    handoff_ready: bool
    outputs: AdapterOutputRefs | None
    files: list[AdapterAgentFile]

    @model_validator(mode="after")
    def require_structured_files_for_v2_handoff(self) -> AdapterAgentResult:
        if self.schema_version == "robot-adapter-agent-result/v2" and self.handoff_ready:
            if self.outputs is None or not self.files:
                raise ValueError("Adapter Agent result v2 handoff requires outputs and files")
        return self


class AdapterBundleOperation(BaseModel):
    """One canonical operation exported by an isolated adapter executable."""

    model_config = ConfigDict(extra="forbid")

    operation: str
    entrypoint: str
    contract_version: str
    contract_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class AdapterBundleFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    role: Literal["ENTRYPOINT", "SUPPORT"] = "SUPPORT"


class AdapterBundleManifest(BaseModel):
    """Immutable contract between a generated adapter and the rolo runtime."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-adapter-bundle/v1", "robot-adapter-bundle/v2"] = (
        "robot-adapter-bundle/v2"
    )
    bundle_id: str
    bundle_version: str
    robot_id: str
    discovery_id: str
    runtime_protocol: Literal["robot-adapter-rpc/v1"] = "robot-adapter-rpc/v1"
    package_file: str
    package_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    files: list[AdapterBundleFile] = Field(default_factory=list)
    operations: list[AdapterBundleOperation] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_file_manifest(self) -> AdapterBundleManifest:
        if not self.files:
            if self.schema_version == "robot-adapter-bundle/v2":
                raise ValueError("adapter bundle v2 requires a file manifest")
            return self
        paths = [item.path for item in self.files]
        if len(paths) != len(set(paths)):
            raise ValueError("adapter bundle file manifest contains duplicate paths")
        entrypoints = [item for item in self.files if item.role == "ENTRYPOINT"]
        if len(entrypoints) != 1 or entrypoints[0].path != self.package_file:
            raise ValueError("adapter bundle must declare exactly one matching entrypoint file")
        if entrypoints[0].sha256 != self.package_sha256:
            raise ValueError("adapter bundle entrypoint digest mismatch")
        return self

    def declared_files(self) -> list[AdapterBundleFile]:
        if self.files:
            return self.files
        return [
            AdapterBundleFile(
                path=self.package_file,
                sha256=self.package_sha256,
                role="ENTRYPOINT",
            )
        ]


class PublishedAdapterFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    role: Literal["ENTRYPOINT", "SUPPORT"] = "SUPPORT"


class AdapterReleaseManifest(BaseModel):
    """Files published together after the independent Adapt gate passes."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-adapter-release/v2"] = "robot-adapter-release/v2"
    release_id: str
    robot_id: str
    discovery_id: str
    target_fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    runtime_environment: AdapterRuntimeContext = Field(default_factory=AdapterRuntimeContext)
    bundle_manifest: str
    bundle_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    adapter_package: str
    adapter_package_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    adapter_files: list[PublishedAdapterFile] = Field(default_factory=list)
    tool_catalog: str
    tool_catalog_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    state_graph: str
    state_graph_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    conformance_report: str
    conformance_report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    gate_report: str
    gate_report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    published_at: datetime = Field(default_factory=utc_now)

class AdapterReleaseIndex(BaseModel):
    """Atomic pointer to the only adapter release eligible for runtime use."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-adapter-release-index/v1"] = "robot-adapter-release-index/v1"
    robot_id: str
    release_id: str
    manifest: str
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    published_at: datetime = Field(default_factory=utc_now)


class ConformanceScope(str, Enum):
    LOCAL_STATIC = "LOCAL_STATIC"
    TARGET_RUNTIME_READONLY = "TARGET_RUNTIME_READONLY"
    PHYSICAL_HARDWARE = "PHYSICAL_HARDWARE"
    # Legacy report labels are accepted for migration, but are never treated
    # as independently verified by the Adapt gate.
    TARGET_RUNTIME = "TARGET_RUNTIME"
    PHYSICAL = "PHYSICAL"


class OperationConformance(BaseModel):
    """Adapter Agent local-static declarations; never physical or runtime proof."""
    model_config = ConfigDict(extra="forbid")

    operation: str
    schema_valid: bool
    errors_valid: bool
    idempotency_valid: bool
    cancellation_valid: bool
    validation_scopes: list[ConformanceScope] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def discard_v1_runtime_claims(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        migrated = dict(value)
        migrated.pop("safety_valid", None)
        migrated.pop("physical_result_valid", None)
        # Keep newer scope values in v2/v3 audit artifacts.  Legacy v1 runtime
        # and physical claims were never independently verifiable and remain
        # discarded during migration.
        allowed_scopes = {item.value for item in ConformanceScope}
        if migrated.get("schema_version") == "robot-adapter-conformance/v1":
            allowed_scopes = {ConformanceScope.LOCAL_STATIC.value}
        migrated["validation_scopes"] = [
            scope for scope in migrated.get("validation_scopes", []) if scope in allowed_scopes
        ]
        return migrated

    @property
    def agent_reported_passed(self) -> bool:
        return all(
            (
                self.schema_valid,
                self.errors_valid,
                self.idempotency_valid,
                self.cancellation_valid,
            )
        )


class AdapterConformanceReport(BaseModel):
    """Advisory Agent report retained as audit input to the independent Rolo gate."""
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[
        "robot-adapter-conformance/v1",
        "robot-adapter-conformance/v2",
        "robot-adapter-conformance/v3",
    ] = (
        "robot-adapter-conformance/v3"
    )
    owner: Literal["ADAPTER_AGENT"] = "ADAPTER_AGENT"
    coverage: Literal["BUNDLE_CANDIDATES_ONLY"] = "BUNDLE_CANDIDATES_ONLY"
    robot_id: str
    discovery_id: str
    operations: list[OperationConformance]


class StateGraphBaseline(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: Literal["robot-state-graph/v1", "robot-state-graph/v2"] = (
        "robot-state-graph/v2"
    )
    robot_id: str
    discovery_id: str
    owner: Literal["ADAPTER_AGENT", "ROLO_GATE"] = "ADAPTER_AGENT"
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]


class ToolCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-tool-catalog/v1"] = "robot-tool-catalog/v1"
    robot_id: str
    discovery_id: str
    contract_catalog_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
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
    release_ref: str
    release_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    promoted_at: datetime = Field(default_factory=utc_now)


class AdapterOutputSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[
        "robot-adapter-output-snapshot/v1", "robot-adapter-output-snapshot/v2"
    ] = "robot-adapter-output-snapshot/v2"
    run_id: str
    robot_id: str
    discovery_id: str
    adapter_manifest_ref: str
    adapter_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    adapter_package_ref: str
    adapter_package_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    adapter_files: list[PublishedAdapterFile] = Field(default_factory=list)
    state_graph_ref: str
    state_graph_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    conformance_report_ref: str
    conformance_report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="before")
    @classmethod
    def discard_v1_catalog(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        migrated = dict(value)
        migrated.pop("tool_catalog_ref", None)
        migrated.pop("tool_catalog_sha256", None)
        return migrated


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
    validation_scope: Literal["STRUCTURAL_ONLY", "TARGET_RUNTIME_READONLY"] = (
        "STRUCTURAL_ONLY"
    )
    checks: list[str] = Field(default_factory=list)
    error: str | None = None
    checked_at: datetime = Field(default_factory=utc_now)


class AdaptRunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-adapt-run-summary/v1"] = "robot-adapt-run-summary/v1"
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
    agent_requirement: AgentRequirement = AgentRequirement.ADAPTER_AGENT


class AdaptPlan(BaseModel):
    schema_version: Literal["robot-adapt-plan/v2", "robot-adapt-plan/v3"] = (
        "robot-adapt-plan/v3"
    )
    stage: str = "adapt"
    robot_id: str
    source_discovery_id: str
    status: AdaptPlanStatus
    tasks: list[AdaptTask]
    eligible_operations: list[str] = Field(default_factory=list)
    deferred_operations: dict[str, str] = Field(default_factory=dict)
    adapter_agent: AdapterAgentConfig = Field(default_factory=AdapterAgentConfig)
    semantic_context_ref: str = ""
    robot_wiki_ref: str = ""
    discovery_manifest_ref: str = ""
    discovery_manifest_sha256: str = ""
    heuristic_analysis_ref: str = ""
    created_at: datetime = Field(default_factory=utc_now)
