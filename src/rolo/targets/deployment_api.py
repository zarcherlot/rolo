from __future__ import annotations

import hashlib
import hmac
import re
import threading
from typing import Annotated, Literal

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from rolo.targets.adapt_jobs import (
    TargetAdaptJobRunner,
    TargetAdaptJobSpecStore,
    TargetAdaptJobSubmission,
    TargetAdaptJobSubmissionService,
    build_target_adapt_job_spec,
    resolve_target_adapt_project_evidence_binding,
    resolve_target_adapt_runtime_evidence_binding,
    resolve_target_adapt_source_discovery_binding,
)
from rolo.targets.agent_broker import (
    SessionAgentBroker,
    SessionAgentCommand,
    SessionAgentCommandReceipt,
    SessionAgentOpenRequest,
    SessionAgentSessionRecord,
    SessionAgentSessionStore,
    SessionAgentSubject,
    SessionAgentToolCatalog,
)
from rolo.targets.agent_readiness import (
    SessionAgentProductionReadinessReport,
    build_session_agent_production_readiness,
)
from rolo.targets.agent_runtime import (
    CodexSessionAgentProvider,
    SessionAgentRuntime,
    SessionAgentTurnRequest,
    SessionAgentTurnResult,
)
from rolo.targets.bootstrap_jobs import (
    TargetBootstrapJobRunner,
    TargetBootstrapJobSpecStore,
    TargetBootstrapJobSubmission,
    TargetBootstrapJobSubmissionIntentStore,
    TargetBootstrapJobSubmissionResult,
    TargetBootstrapPublicSubmissionService,
)
from rolo.targets.connection_assessment import TargetDeploymentJobRunner
from rolo.targets.deployment_jobs import (
    DeploymentEventRecord,
    DeploymentJobRecord,
    DeploymentJobStateConflict,
    DeploymentJobStore,
    sanitize_deployment_summary,
)
from rolo.targets.deployment_tui import (
    TargetDeploymentTui,
    TargetDeploymentTuiPage,
    TargetDeploymentWorkbenchSnapshot,
)
from rolo.targets.enrollment import CollectorEnrollmentPinRegistry
from rolo.targets.host_provisioning_jobs import (
    TargetHostProvisioningJobRunner,
    TargetHostProvisioningJobSpecStore,
    TargetHostProvisioningJobSubmission,
    TargetHostProvisioningJobSubmissionResult,
    TargetHostProvisioningSubmissionIntentStore,
    TargetHostProvisioningSubmissionService,
)
from rolo.targets.host_reconciliation_jobs import (
    TargetHostReconciliationJobRunner,
    TargetHostReconciliationJobSpecStore,
    TargetHostReconciliationJobSubmission,
    TargetHostReconciliationJobSubmissionResult,
    TargetHostReconciliationSubmissionIntentStore,
    TargetHostReconciliationSubmissionService,
)
from rolo.targets.host_rollback_jobs import (
    TargetHostRollbackJobSubmission,
    TargetHostRollbackJobSubmissionResult,
    TargetHostRollbackSubmissionIntentStore,
    TargetHostRollbackSubmissionService,
)
from rolo.targets.host_service_jobs import (
    TargetHostServiceJobRunner,
    TargetHostServiceJobSpecStore,
    TargetHostServiceJobSubmission,
    TargetHostServiceJobSubmissionResult,
    TargetHostServiceSubmissionIntentStore,
    TargetHostServiceSubmissionService,
)
from rolo.targets.host_service_reconciliation_jobs import (
    TargetHostServiceReconciliationJobRunner,
    TargetHostServiceReconciliationJobSpecStore,
    TargetHostServiceReconciliationJobSubmission,
    TargetHostServiceReconciliationJobSubmissionResult,
    TargetHostServiceReconciliationSubmissionIntentStore,
    TargetHostServiceReconciliationSubmissionService,
)
from rolo.targets.models import (
    ApprovalRequest,
    ApprovalStatus,
    DeploymentCommand,
    DeploymentCommandKind,
    InteractionSurface,
)
from rolo.targets.package_registry import TargetPackageRegistry
from rolo.targets.project_evidence_jobs import (
    TargetProjectEvidenceArtifactStore,
    TargetProjectEvidenceIntentStore,
    TargetProjectEvidenceJobRunner,
    TargetProjectEvidenceJobSpecStore,
    TargetProjectEvidenceJobSubmission,
    TargetProjectEvidenceJobSubmissionResult,
    TargetProjectEvidenceSubmissionService,
)
from rolo.targets.registration import (
    TargetRegistrationConflict,
    TargetRegistrationRequest,
    TargetRegistrationResult,
    TargetRegistrationService,
    target_connection_binding_sha256,
)
from rolo.targets.registry import TargetProfileRegistry
from rolo.targets.runtime_evidence_jobs import (
    TargetRuntimeEvidenceArtifactStore,
    TargetRuntimeEvidenceIntentStore,
    TargetRuntimeEvidenceJobRunner,
    TargetRuntimeEvidenceJobSpecStore,
    TargetRuntimeEvidenceJobSubmission,
    TargetRuntimeEvidenceJobSubmissionResult,
    TargetRuntimeEvidenceSubmissionService,
)
from rolo.targets.runtime_rollback_jobs import (
    TargetRuntimeRollbackIntentStore,
    TargetRuntimeRollbackJobRunner,
    TargetRuntimeRollbackJobSpecStore,
    TargetRuntimeRollbackJobSubmissionResult,
    TargetRuntimeRollbackSubmission,
    TargetRuntimeRollbackSubmissionService,
)
from rolo.targets.source_discovery_jobs import (
    TargetSourceDiscoveryArtifactStore,
    TargetSourceDiscoveryIntentStore,
    TargetSourceDiscoveryJobRunner,
    TargetSourceDiscoveryJobSpecStore,
    TargetSourceDiscoveryJobSubmission,
    TargetSourceDiscoveryJobSubmissionResult,
    TargetSourceDiscoverySubmissionService,
)

_PRINCIPAL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,127}$")
_IDEMPOTENCY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{7,127}$")
_TARGET_PERMISSION = "target:write"
_APPROVAL_PERMISSION = "approval:write"

deployment_router = APIRouter()
DEPLOYMENT_API_FEATURES = [
    "deployment.adapt-submission/v1",
    "deployment.approval-decision/v1",
    "deployment.bootstrap-submission/v1",
    "deployment.connection-assessment/v1",
    "deployment.auth-session/v1",
    "deployment.job-control/v1",
    "deployment.job-events/v1",
    "deployment.job-runner/v1",
    "deployment.host-provisioning/v1",
    "deployment.host-reconciliation/v1",
    "deployment.host-rollback/v1",
    "deployment.host-service/v1",
    "deployment.host-service-reconciliation/v1",
    "deployment.project-evidence/v1",
    "deployment.runtime-evidence/v1",
    "deployment.source-discovery/v1",
    "deployment.runtime-rollback/v1",
    "deployment.session-agent-broker/v1",
    "deployment.session-agent-readiness/v1",
    "deployment.session-agent-turn/v1",
    "deployment.target-registration/v1",
    "deployment.workbench-read-model/v1",
]

_AGENT_BROKER_LOCK = threading.RLock()


class DeploymentJobSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-deployment-job-submission/v1"] = (
        "rolo-deployment-job-submission/v1"
    )
    workspace_root: str | None = Field(default=None, min_length=1, max_length=4096)
    active_probe: Literal["none", "help", "runtime-readonly"] = "runtime-readonly"
    run_adapter_agent: bool = True
    parameters_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class DeploymentEventPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-deployment-event-page/v1"] = "rolo-deployment-event-page/v1"
    job_id: str = Field(pattern=r"^deployment-[0-9a-f]{32}$")
    after_sequence: int = Field(ge=0)
    next_sequence: int = Field(ge=0)
    items: list[DeploymentEventRecord]


class DeploymentApprovalDecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-deployment-approval-decision-input/v1"] = (
        "rolo-deployment-approval-decision-input/v1"
    )
    approve: bool
    reason: str = Field(min_length=1, max_length=1000)


class TargetConnectionAssessmentSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-connection-assessment-submission/v1"] = (
        "rolo-target-connection-assessment-submission/v1"
    )
    active_probe: Literal["none", "help", "runtime-readonly"] = "runtime-readonly"


class DeploymentApiSession(BaseModel):
    """Authenticated, secret-free identity projection for deployment-control clients."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-deployment-api-session/v1"] = "rolo-deployment-api-session/v1"
    principal: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,127}$")
    permissions: list[Literal["approval:write", "target:write"]]
    authentication: Literal["bearer"] = "bearer"
    token_persistence: Literal["client-memory-only"] = "client-memory-only"


class TargetBootstrapApiSubmissionResult(BaseModel):
    """Browser-safe Bootstrap receipt; internal package paths and key bytes stay private."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-bootstrap-api-submission-result/v1"] = (
        "rolo-target-bootstrap-api-submission-result/v1"
    )
    job: DeploymentJobRecord
    approval: ApprovalRequest
    package_ref: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}@[0-9a-f]{64}$")
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class TargetRuntimeRollbackApiSubmissionResult(BaseModel):
    """Browser-safe receipt for an R3 target runtime rollback submission."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-runtime-rollback-api-result/v1"] = (
        "rolo-target-runtime-rollback-api-result/v1"
    )
    job: DeploymentJobRecord
    approval: ApprovalRequest
    package_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
    expected_current_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_previous_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class TargetHostProvisioningApiSubmissionResult(BaseModel):
    """Secret-closed receipt for an R3 target host provisioning submission."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-host-provisioning-api-result/v1"] = (
        "rolo-target-host-provisioning-api-result/v1"
    )
    job: DeploymentJobRecord
    approval: ApprovalRequest
    plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class TargetHostReconciliationApiSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-host-reconciliation-api-submission/v1"] = (
        "rolo-target-host-reconciliation-api-submission/v1"
    )
    approver_principal: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,127}$")
    approval_ttl_s: int = Field(default=900, ge=60, le=86_400)


class TargetHostReconciliationApiSubmissionResult(BaseModel):
    """Secret-closed receipt for an R2 privileged read-only reconciliation."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-host-reconciliation-api-result/v1"] = (
        "rolo-target-host-reconciliation-api-result/v1"
    )
    job: DeploymentJobRecord
    approval: ApprovalRequest
    original_job_id: str = Field(pattern=r"^deployment-[0-9a-f]{32}$")
    plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class TargetHostRollbackApiSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-host-rollback-api-submission/v1"] = (
        "rolo-target-host-rollback-api-submission/v1"
    )
    rollback_to_host_job_id: str = Field(pattern=r"^deployment-[0-9a-f]{32}$")
    approver_principal: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,127}$")
    approval_ttl_s: int = Field(default=900, ge=60, le=86_400)


class TargetHostRollbackApiSubmissionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-host-rollback-api-result/v1"] = (
        "rolo-target-host-rollback-api-result/v1"
    )
    job: DeploymentJobRecord
    approval: ApprovalRequest
    current_host_job_id: str = Field(pattern=r"^deployment-[0-9a-f]{32}$")
    rollback_to_host_job_id: str = Field(pattern=r"^deployment-[0-9a-f]{32}$")
    rollback_plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class TargetHostServiceApiSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-host-service-api-submission/v1"] = (
        "rolo-target-host-service-api-submission/v1"
    )
    host_configuration_job_id: str = Field(pattern=r"^deployment-[0-9a-f]{32}$")
    bootstrap_job_id: str = Field(pattern=r"^deployment-[0-9a-f]{32}$")
    approver_principal: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,127}$")
    approval_ttl_s: int = Field(default=900, ge=60, le=86_400)


class TargetHostServiceApiSubmissionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-host-service-api-result/v1"] = (
        "rolo-target-host-service-api-result/v1"
    )
    job: DeploymentJobRecord
    approval: ApprovalRequest
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class TargetHostServiceReconciliationApiSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[
        "rolo-target-host-service-reconciliation-api-submission/v1"
    ] = "rolo-target-host-service-reconciliation-api-submission/v1"
    approver_principal: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,127}$")
    approval_ttl_s: int = Field(default=900, ge=60, le=86_400)


class TargetHostServiceReconciliationApiSubmissionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[
        "rolo-target-host-service-reconciliation-api-result/v1"
    ] = "rolo-target-host-service-reconciliation-api-result/v1"
    job: DeploymentJobRecord
    approval: ApprovalRequest
    original_job_id: str = Field(pattern=r"^deployment-[0-9a-f]{32}$")
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def _job_store(request: Request) -> DeploymentJobStore:
    return DeploymentJobStore(
        request.app.state.runtime.settings.rolo_artifact_dir / "deployment-jobs"
    )


def _registration_service(request: Request) -> TargetRegistrationService:
    registry = TargetProfileRegistry(request.app.state.runtime.settings.target_profile_dir)
    return TargetRegistrationService(registry)


def _deployment_workbench(request: Request) -> TargetDeploymentTui:
    settings = request.app.state.runtime.settings
    return TargetDeploymentTui(
        _registration_service(request),
        _job_store(request),
        TargetBootstrapJobSpecStore(settings.rolo_artifact_dir / "deployment-jobs" / "specs"),
        TargetRuntimeRollbackJobSpecStore(settings.rolo_artifact_dir / "deployment-jobs" / "specs"),
        TargetProjectEvidenceJobSpecStore(settings.rolo_artifact_dir / "deployment-jobs" / "specs"),
        TargetAdaptJobSpecStore(settings.rolo_artifact_dir / "deployment-jobs" / "specs"),
        TargetSourceDiscoveryJobSpecStore(settings.rolo_artifact_dir / "deployment-jobs" / "specs"),
        TargetRuntimeEvidenceJobSpecStore(settings.rolo_artifact_dir / "deployment-jobs" / "specs"),
    )


def _job_runner(request: Request) -> TargetDeploymentJobRunner:
    settings = request.app.state.runtime.settings
    store = _job_store(request)
    registrations = _registration_service(request)
    artifact_root = settings.rolo_artifact_dir / "deployment-jobs" / "artifacts"
    return TargetDeploymentJobRunner(
        store,
        registrations,
        artifact_root,
        bootstrap_runner=TargetBootstrapJobRunner(
            store,
            registrations,
            TargetBootstrapJobSpecStore(settings.rolo_artifact_dir / "deployment-jobs" / "specs"),
            artifact_root,
        ),
        adapt_runner=TargetAdaptJobRunner(
            store,
            registrations,
            TargetAdaptJobSpecStore(settings.rolo_artifact_dir / "deployment-jobs" / "specs"),
            artifact_root,
            settings=settings,
            project_evidence_artifacts=TargetProjectEvidenceArtifactStore(artifact_root),
            source_discovery_artifacts=TargetSourceDiscoveryArtifactStore(artifact_root),
            runtime_evidence_artifacts=TargetRuntimeEvidenceArtifactStore(artifact_root),
            collector_pins=CollectorEnrollmentPinRegistry(
                settings.target_profile_dir / "enrollment-v4"
            ),
        ),
        rollback_runner=TargetRuntimeRollbackJobRunner(
            store,
            registrations,
            TargetRuntimeRollbackJobSpecStore(
                settings.rolo_artifact_dir / "deployment-jobs" / "specs"
            ),
            artifact_root,
            authorization_signing_key_id=(settings.rolo_deployment_authorization_key_id),
            authorization_public_key_path=(settings.rolo_deployment_authorization_public_key_path),
            authorization_private_key_path=(
                settings.rolo_deployment_authorization_private_key_path
            ),
        ),
        project_evidence_runner=TargetProjectEvidenceJobRunner(
            store,
            registrations,
            TargetProjectEvidenceJobSpecStore(
                settings.rolo_artifact_dir / "deployment-jobs" / "specs"
            ),
            artifact_root,
            authorization_signing_key_id=(settings.rolo_deployment_authorization_key_id),
            authorization_public_key_path=(settings.rolo_deployment_authorization_public_key_path),
            authorization_private_key_path=(
                settings.rolo_deployment_authorization_private_key_path
            ),
        ),
        source_discovery_runner=TargetSourceDiscoveryJobRunner(
            store,
            registrations,
            TargetSourceDiscoveryJobSpecStore(
                settings.rolo_artifact_dir / "deployment-jobs" / "specs"
            ),
            artifact_root,
            authorization_signing_key_id=(settings.rolo_deployment_authorization_key_id),
            authorization_public_key_path=(settings.rolo_deployment_authorization_public_key_path),
            authorization_private_key_path=(
                settings.rolo_deployment_authorization_private_key_path
            ),
        ),
        runtime_evidence_runner=TargetRuntimeEvidenceJobRunner(
            store,
            registrations,
            TargetRuntimeEvidenceJobSpecStore(
                settings.rolo_artifact_dir / "deployment-jobs" / "specs"
            ),
            artifact_root,
            CollectorEnrollmentPinRegistry(settings.target_profile_dir / "enrollment-v4"),
            authorization_signing_key_id=(settings.rolo_deployment_authorization_key_id),
            authorization_public_key_path=(settings.rolo_deployment_authorization_public_key_path),
            authorization_private_key_path=(
                settings.rolo_deployment_authorization_private_key_path
            ),
        ),
        host_provisioning_runner=TargetHostProvisioningJobRunner(
            store,
            registrations,
            TargetHostProvisioningJobSpecStore(
                settings.rolo_artifact_dir / "deployment-jobs" / "specs"
            ),
            artifact_root,
        ),
        host_reconciliation_runner=TargetHostReconciliationJobRunner(
            store=store,
            registrations=registrations,
            specs=TargetHostReconciliationJobSpecStore(
                settings.rolo_artifact_dir / "deployment-jobs" / "specs"
            ),
            provisioning_specs=TargetHostProvisioningJobSpecStore(
                settings.rolo_artifact_dir / "deployment-jobs" / "specs"
            ),
            artifact_root=artifact_root,
        ),
        host_service_runner=TargetHostServiceJobRunner(
            store=store,
            registrations=registrations,
            specs=TargetHostServiceJobSpecStore(
                settings.rolo_artifact_dir / "deployment-jobs" / "specs"
            ),
            host_specs=TargetHostProvisioningJobSpecStore(
                settings.rolo_artifact_dir / "deployment-jobs" / "specs"
            ),
            bootstrap_specs=TargetBootstrapJobSpecStore(
                settings.rolo_artifact_dir / "deployment-jobs" / "specs"
            ),
            artifact_root=artifact_root,
        ),
        host_service_reconciliation_runner=TargetHostServiceReconciliationJobRunner(
            store=store,
            registrations=registrations,
            specs=TargetHostServiceReconciliationJobSpecStore(
                settings.rolo_artifact_dir / "deployment-jobs" / "specs"
            ),
            service_specs=TargetHostServiceJobSpecStore(
                settings.rolo_artifact_dir / "deployment-jobs" / "specs"
            ),
            artifact_root=artifact_root,
        ),
    )


def _bootstrap_submission_service(request: Request) -> TargetBootstrapPublicSubmissionService:
    settings = request.app.state.runtime.settings
    store = _job_store(request)
    return TargetBootstrapPublicSubmissionService(
        store=store,
        specs=TargetBootstrapJobSpecStore(settings.rolo_artifact_dir / "deployment-jobs" / "specs"),
        intents=TargetBootstrapJobSubmissionIntentStore(
            settings.rolo_artifact_dir / "deployment-jobs" / "bootstrap-intents"
        ),
        registrations=_registration_service(request),
        packages=TargetPackageRegistry(settings.target_package_registry_dir),
        authorization_key_id=settings.rolo_deployment_authorization_key_id,
        authorization_public_key_path=(settings.rolo_deployment_authorization_public_key_path),
    )


def _runtime_rollback_submission_service(
    request: Request,
) -> TargetRuntimeRollbackSubmissionService:
    settings = request.app.state.runtime.settings
    return TargetRuntimeRollbackSubmissionService(
        store=_job_store(request),
        specs=TargetRuntimeRollbackJobSpecStore(
            settings.rolo_artifact_dir / "deployment-jobs" / "specs"
        ),
        intents=TargetRuntimeRollbackIntentStore(
            settings.rolo_artifact_dir / "deployment-jobs" / "runtime-rollback-intents"
        ),
        registrations=_registration_service(request),
    )


def _host_provisioning_submission_service(
    request: Request,
) -> TargetHostProvisioningSubmissionService:
    settings = request.app.state.runtime.settings
    return TargetHostProvisioningSubmissionService(
        store=_job_store(request),
        specs=TargetHostProvisioningJobSpecStore(
            settings.rolo_artifact_dir / "deployment-jobs" / "specs"
        ),
        intents=TargetHostProvisioningSubmissionIntentStore(
            settings.rolo_artifact_dir / "deployment-jobs" / "host-provisioning-intents"
        ),
        registrations=_registration_service(request),
    )


def _host_reconciliation_submission_service(
    request: Request,
) -> TargetHostReconciliationSubmissionService:
    settings = request.app.state.runtime.settings
    spec_root = settings.rolo_artifact_dir / "deployment-jobs" / "specs"
    return TargetHostReconciliationSubmissionService(
        store=_job_store(request),
        specs=TargetHostReconciliationJobSpecStore(spec_root),
        provisioning_specs=TargetHostProvisioningJobSpecStore(spec_root),
        intents=TargetHostReconciliationSubmissionIntentStore(
            settings.rolo_artifact_dir
            / "deployment-jobs"
            / "host-reconciliation-intents"
        ),
    )


def _host_rollback_submission_service(
    request: Request,
) -> TargetHostRollbackSubmissionService:
    settings = request.app.state.runtime.settings
    return TargetHostRollbackSubmissionService(
        store=_job_store(request),
        specs=TargetHostProvisioningJobSpecStore(
            settings.rolo_artifact_dir / "deployment-jobs" / "specs"
        ),
        intents=TargetHostRollbackSubmissionIntentStore(
            settings.rolo_artifact_dir / "deployment-jobs" / "host-rollback-intents"
        ),
        registrations=_registration_service(request),
    )


def _host_service_submission_service(
    request: Request,
) -> TargetHostServiceSubmissionService:
    settings = request.app.state.runtime.settings
    spec_root = settings.rolo_artifact_dir / "deployment-jobs" / "specs"
    return TargetHostServiceSubmissionService(
        store=_job_store(request),
        specs=TargetHostServiceJobSpecStore(spec_root),
        intents=TargetHostServiceSubmissionIntentStore(
            settings.rolo_artifact_dir / "deployment-jobs" / "host-service-intents"
        ),
        host_specs=TargetHostProvisioningJobSpecStore(spec_root),
        bootstrap_specs=TargetBootstrapJobSpecStore(spec_root),
        registrations=_registration_service(request),
    )


def _host_service_reconciliation_submission_service(
    request: Request,
) -> TargetHostServiceReconciliationSubmissionService:
    settings = request.app.state.runtime.settings
    spec_root = settings.rolo_artifact_dir / "deployment-jobs" / "specs"
    return TargetHostServiceReconciliationSubmissionService(
        store=_job_store(request),
        specs=TargetHostServiceReconciliationJobSpecStore(spec_root),
        intents=TargetHostServiceReconciliationSubmissionIntentStore(
            settings.rolo_artifact_dir
            / "deployment-jobs"
            / "host-service-reconciliation-intents"
        ),
        service_specs=TargetHostServiceJobSpecStore(spec_root),
    )


def _project_evidence_submission_service(
    request: Request,
) -> TargetProjectEvidenceSubmissionService:
    settings = request.app.state.runtime.settings
    return TargetProjectEvidenceSubmissionService(
        store=_job_store(request),
        specs=TargetProjectEvidenceJobSpecStore(
            settings.rolo_artifact_dir / "deployment-jobs" / "specs"
        ),
        intents=TargetProjectEvidenceIntentStore(
            settings.rolo_artifact_dir / "deployment-jobs" / "project-evidence-intents"
        ),
        registrations=_registration_service(request),
    )


def _source_discovery_submission_service(
    request: Request,
) -> TargetSourceDiscoverySubmissionService:
    settings = request.app.state.runtime.settings
    return TargetSourceDiscoverySubmissionService(
        store=_job_store(request),
        specs=TargetSourceDiscoveryJobSpecStore(
            settings.rolo_artifact_dir / "deployment-jobs" / "specs"
        ),
        intents=TargetSourceDiscoveryIntentStore(
            settings.rolo_artifact_dir / "deployment-jobs" / "source-discovery-intents"
        ),
        registrations=_registration_service(request),
    )


def _runtime_evidence_submission_service(
    request: Request,
) -> TargetRuntimeEvidenceSubmissionService:
    settings = request.app.state.runtime.settings
    return TargetRuntimeEvidenceSubmissionService(
        store=_job_store(request),
        specs=TargetRuntimeEvidenceJobSpecStore(
            settings.rolo_artifact_dir / "deployment-jobs" / "specs"
        ),
        intents=TargetRuntimeEvidenceIntentStore(
            settings.rolo_artifact_dir / "deployment-jobs" / "runtime-evidence-intents"
        ),
        registrations=_registration_service(request),
        pins=CollectorEnrollmentPinRegistry(settings.target_profile_dir / "enrollment-v4"),
    )


def _session_agent_broker(request: Request) -> SessionAgentBroker:
    """Return one broker per runtime root so in-process command serialization is shared."""

    settings = request.app.state.runtime.settings
    cache_key = str(settings.rolo_artifact_dir.expanduser().absolute())
    cached = getattr(request.app.state, "session_agent_broker", None)
    if cached is not None and cached[0] == cache_key:
        return cached[1]
    with _AGENT_BROKER_LOCK:
        cached = getattr(request.app.state, "session_agent_broker", None)
        if cached is not None and cached[0] == cache_key:
            return cached[1]
        jobs = _job_store(request)
        registrations = _registration_service(request)
        broker = SessionAgentBroker(
            sessions=SessionAgentSessionStore(
                settings.rolo_artifact_dir / "deployment-jobs" / "agent-sessions"
            ),
            registrations=registrations,
            jobs=jobs,
            adapt_specs=TargetAdaptJobSpecStore(
                settings.rolo_artifact_dir / "deployment-jobs" / "specs"
            ),
            bootstrap_submissions=_bootstrap_submission_service(request),
            rollback_submissions=_runtime_rollback_submission_service(request),
            project_evidence_submissions=(_project_evidence_submission_service(request)),
            project_evidence_artifacts=TargetProjectEvidenceArtifactStore(
                settings.rolo_artifact_dir / "deployment-jobs" / "artifacts"
            ),
            source_discovery_submissions=(_source_discovery_submission_service(request)),
            source_discovery_artifacts=TargetSourceDiscoveryArtifactStore(
                settings.rolo_artifact_dir / "deployment-jobs" / "artifacts"
            ),
            runtime_evidence_submissions=(_runtime_evidence_submission_service(request)),
            runtime_evidence_artifacts=TargetRuntimeEvidenceArtifactStore(
                settings.rolo_artifact_dir / "deployment-jobs" / "artifacts"
            ),
            collector_pins=CollectorEnrollmentPinRegistry(
                settings.target_profile_dir / "enrollment-v4"
            ),
            job_runner=_job_runner(request),
            workbench=_deployment_workbench(request),
        )
        request.app.state.session_agent_broker = (cache_key, broker)
        return broker


def _session_agent_runtime(request: Request) -> SessionAgentRuntime:
    settings = request.app.state.runtime.settings
    if not settings.rolo_session_agent_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Session Agent is disabled",
        )
    if settings.rolo_session_agent_api_key is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Session Agent requires a dedicated provider API key",
        )
    cache_key = id(settings)
    cached = getattr(request.app.state, "session_agent_runtime", None)
    if cached is not None and cached[0] == cache_key:
        return cached[1]
    with _AGENT_BROKER_LOCK:
        cached = getattr(request.app.state, "session_agent_runtime", None)
        if cached is not None and cached[0] == cache_key:
            return cached[1]
        runtime = SessionAgentRuntime(
            _session_agent_broker(request),
            CodexSessionAgentProvider(
                api_key=settings.rolo_session_agent_api_key,
                model=settings.rolo_session_agent_model,
                base_url=settings.rolo_session_agent_base_url,
                executable=settings.rolo_session_agent_executable,
                timeout_s=settings.rolo_session_agent_provider_timeout_s,
            ),
        )
        request.app.state.session_agent_runtime = (cache_key, runtime)
        return runtime


def _session_agent_readiness(request: Request) -> SessionAgentProductionReadinessReport:
    settings = request.app.state.runtime.settings
    return build_session_agent_production_readiness(
        enabled=settings.rolo_session_agent_enabled,
        provider_api_key_configured=settings.rolo_session_agent_api_key is not None,
        base_url=settings.rolo_session_agent_base_url,
        executable=settings.rolo_session_agent_executable,
        model=settings.rolo_session_agent_model,
        provider_timeout_s=settings.rolo_session_agent_provider_timeout_s,
        catalog_sha256=_session_agent_broker(request).catalog.canonical_sha256(),
    )


def _authenticate_identity(
    request: Request,
    *,
    principal: str | None,
) -> tuple[str, set[str]]:
    settings = request.app.state.runtime.settings
    token = settings.rolo_api_token
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mutating deployment API requires ROLO_API_TOKEN",
        )
    authorization = request.headers.get("authorization", "")
    supplied = authorization.removeprefix("Bearer ") if authorization.startswith("Bearer ") else ""
    if not supplied or not hmac.compare_digest(supplied, token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API token",
        )
    if principal is None or _PRINCIPAL.fullmatch(principal) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Rolo-Principal is required and must be canonical",
        )
    bound_principal = settings.rolo_api_token_principal
    if bound_principal is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mutating deployment API token has no configured principal",
        )
    if not hmac.compare_digest(principal, bound_principal):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API token is not bound to the supplied principal",
        )
    bound_permissions = {
        item.strip() for item in settings.rolo_api_token_permissions.split(",") if item.strip()
    }
    return principal, bound_permissions


def _write_identity(
    request: Request,
    *,
    required_permission: str,
    idempotency_key: str | None,
    principal: str | None,
    permissions: str | None,
) -> tuple[str, str]:
    canonical_principal, bound_permissions = _authenticate_identity(
        request,
        principal=principal,
    )
    granted = {item.strip() for item in (permissions or "").split(",") if item.strip()}
    if required_permission not in granted or required_permission not in bound_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing deployment permission: {required_permission}",
        )
    if idempotency_key is None or _IDEMPOTENCY.fullmatch(idempotency_key) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key is required and must be canonical",
        )
    return canonical_principal, idempotency_key


def _agent_subject(
    request: Request,
    *,
    principal: str | None,
    permissions: str | None,
) -> SessionAgentSubject:
    canonical_principal, bound_permissions = _authenticate_identity(
        request,
        principal=principal,
    )
    granted = sorted(item.strip() for item in (permissions or "").split(",") if item.strip())
    if len(granted) != len(set(granted)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session Agent permissions must be unique",
        )
    unsupported = set(granted) - {_TARGET_PERMISSION}
    if unsupported:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Session Agent cannot receive approval or unknown permissions",
        )
    if not set(granted).issubset(bound_permissions):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Session Agent requested an unbound permission",
        )
    return SessionAgentSubject(
        principal=canonical_principal,
        permissions=granted,
    )


def build_deployment_command(
    *,
    target_id: str,
    command_kind: DeploymentCommandKind,
    submission: DeploymentJobSubmission,
    requested_by: str,
    interaction_surface: InteractionSurface,
    idempotency_key: str,
) -> DeploymentCommand:
    """One builder shared by API, CLI, TUI and future natural-language adapters."""

    return DeploymentCommand(
        command=command_kind,
        target_id=target_id,
        workspace_root=submission.workspace_root,
        active_probe=submission.active_probe,
        run_adapter_agent=(
            submission.run_adapter_agent
            if command_kind
            in {DeploymentCommandKind.ADAPT, DeploymentCommandKind.BOOTSTRAP_AND_ADAPT}
            else False
        ),
        requested_by=requested_by,
        interaction_surface=interaction_surface,
        idempotency_key=idempotency_key,
        parameters_sha256=submission.parameters_sha256,
    )


def _create_job(
    request: Request,
    *,
    target_id: str,
    command_kind: DeploymentCommandKind,
    submission: DeploymentJobSubmission,
    idempotency_key: str | None,
    principal: str | None,
    permissions: str | None,
) -> DeploymentJobRecord:
    requested_by, canonical_key = _write_identity(
        request,
        required_permission=_TARGET_PERMISSION,
        idempotency_key=idempotency_key,
        principal=principal,
        permissions=permissions,
    )
    try:
        _registration_service(request).load(target_id)
        command = build_deployment_command(
            target_id=target_id,
            command_kind=command_kind,
            submission=submission,
            requested_by=requested_by,
            interaction_surface=InteractionSurface.API,
            idempotency_key=canonical_key,
        )
        return _job_store(request).create_job(command)
    except DeploymentJobStateConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@deployment_router.post(
    "/v1/targets",
    response_model=TargetRegistrationResult,
    status_code=status.HTTP_201_CREATED,
)
async def register_target(
    registration: TargetRegistrationRequest,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    principal: Annotated[str | None, Header(alias="X-Rolo-Principal")] = None,
    permissions: Annotated[str | None, Header(alias="X-Rolo-Permissions")] = None,
) -> TargetRegistrationResult:
    canonical_principal, canonical_key = _write_identity(
        request,
        required_permission=_TARGET_PERMISSION,
        idempotency_key=idempotency_key,
        principal=principal,
        permissions=permissions,
    )
    try:
        return _registration_service(request).register(
            registration,
            principal=canonical_principal,
            idempotency_key=canonical_key,
        )
    except TargetRegistrationConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@deployment_router.get(
    "/v1/targets",
    response_model=list[TargetRegistrationRequest],
)
async def list_registered_targets(request: Request) -> list[TargetRegistrationRequest]:
    service = _registration_service(request)
    return [service.load(item.target_id) for item in service.registry.list_targets()]


@deployment_router.get(
    "/v1/deployment-session",
    response_model=DeploymentApiSession,
)
async def get_deployment_session(
    request: Request,
    response: Response,
    principal: Annotated[str | None, Header(alias="X-Rolo-Principal")] = None,
) -> DeploymentApiSession:
    """Verify an operator token before any deployment mutation is attempted."""

    canonical_principal, bound_permissions = _authenticate_identity(
        request,
        principal=principal,
    )
    response.headers["Cache-Control"] = "no-store"
    supported_permissions = sorted(
        bound_permissions.intersection({_TARGET_PERMISSION, _APPROVAL_PERMISSION})
    )
    return DeploymentApiSession(
        principal=canonical_principal,
        permissions=supported_permissions,
    )


@deployment_router.get(
    "/v1/session-agent/catalog",
    response_model=SessionAgentToolCatalog,
)
async def get_session_agent_catalog(
    request: Request,
    response: Response,
    principal: Annotated[str | None, Header(alias="X-Rolo-Principal")] = None,
    permissions: Annotated[str | None, Header(alias="X-Rolo-Permissions")] = None,
) -> SessionAgentToolCatalog:
    _agent_subject(request, principal=principal, permissions=permissions)
    response.headers["Cache-Control"] = "no-store"
    return _session_agent_broker(request).catalog


@deployment_router.get(
    "/v1/session-agent/readiness",
    response_model=SessionAgentProductionReadinessReport,
)
async def get_session_agent_readiness(
    request: Request,
    response: Response,
    principal: Annotated[str | None, Header(alias="X-Rolo-Principal")] = None,
    permissions: Annotated[str | None, Header(alias="X-Rolo-Permissions")] = None,
) -> SessionAgentProductionReadinessReport:
    _agent_subject(request, principal=principal, permissions=permissions)
    response.headers["Cache-Control"] = "no-store"
    return _session_agent_readiness(request)


@deployment_router.post(
    "/v1/session-agent/sessions",
    response_model=SessionAgentSessionRecord,
    status_code=status.HTTP_201_CREATED,
)
async def open_session_agent_session(
    submission: SessionAgentOpenRequest,
    request: Request,
    response: Response,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    principal: Annotated[str | None, Header(alias="X-Rolo-Principal")] = None,
    permissions: Annotated[str | None, Header(alias="X-Rolo-Permissions")] = None,
) -> SessionAgentSessionRecord:
    subject = _agent_subject(request, principal=principal, permissions=permissions)
    if idempotency_key is None or _IDEMPOTENCY.fullmatch(idempotency_key) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key is required and must be canonical",
        )
    try:
        result = await run_in_threadpool(
            _session_agent_broker(request).open_session,
            subject,
            submission,
            idempotency_key=idempotency_key,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session Agent target not found",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    response.headers["Cache-Control"] = "no-store"
    return result


@deployment_router.post(
    "/v1/session-agent/turns",
    response_model=SessionAgentTurnResult,
)
async def run_session_agent_turn(
    submission: SessionAgentTurnRequest,
    request: Request,
    response: Response,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    principal: Annotated[str | None, Header(alias="X-Rolo-Principal")] = None,
    permissions: Annotated[str | None, Header(alias="X-Rolo-Permissions")] = None,
) -> SessionAgentTurnResult:
    subject = _agent_subject(request, principal=principal, permissions=permissions)
    if idempotency_key is None or _IDEMPOTENCY.fullmatch(idempotency_key) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key is required and must be canonical",
        )
    try:
        result = await run_in_threadpool(
            _session_agent_runtime(request).run,
            subject,
            submission,
            idempotency_key=idempotency_key,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session Agent target not found",
        ) from exc
    except (RuntimeError, TimeoutError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    response.headers["Cache-Control"] = "no-store"
    return result


@deployment_router.get(
    "/v1/session-agent/sessions/{session_id}",
    response_model=SessionAgentSessionRecord,
)
async def get_session_agent_session(
    session_id: str,
    request: Request,
    response: Response,
    principal: Annotated[str | None, Header(alias="X-Rolo-Principal")] = None,
    permissions: Annotated[str | None, Header(alias="X-Rolo-Permissions")] = None,
) -> SessionAgentSessionRecord:
    subject = _agent_subject(request, principal=principal, permissions=permissions)
    try:
        result = await run_in_threadpool(
            _session_agent_broker(request).get_session,
            session_id,
            subject,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Session Agent subject mismatch",
        ) from exc
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session Agent session not found",
        ) from exc
    response.headers["Cache-Control"] = "no-store"
    return result


@deployment_router.post(
    "/v1/session-agent/sessions/{session_id}/commands",
    response_model=SessionAgentCommandReceipt,
)
async def execute_session_agent_command(
    session_id: str,
    command: SessionAgentCommand,
    request: Request,
    response: Response,
    principal: Annotated[str | None, Header(alias="X-Rolo-Principal")] = None,
    permissions: Annotated[str | None, Header(alias="X-Rolo-Permissions")] = None,
) -> SessionAgentCommandReceipt:
    subject = _agent_subject(request, principal=principal, permissions=permissions)
    try:
        result = await run_in_threadpool(
            _session_agent_broker(request).execute,
            session_id,
            subject,
            command,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session Agent record not found",
        ) from exc
    except (RuntimeError, TimeoutError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    response.headers["Cache-Control"] = "no-store"
    return result


@deployment_router.post(
    "/v1/session-agent/sessions/{session_id}/cancel",
    response_model=SessionAgentSessionRecord,
)
async def cancel_session_agent_session(
    session_id: str,
    request: Request,
    response: Response,
    principal: Annotated[str | None, Header(alias="X-Rolo-Principal")] = None,
    permissions: Annotated[str | None, Header(alias="X-Rolo-Permissions")] = None,
) -> SessionAgentSessionRecord:
    subject = _agent_subject(request, principal=principal, permissions=permissions)
    try:
        result = await run_in_threadpool(
            _session_agent_broker(request).cancel_session,
            session_id,
            subject,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Session Agent subject mismatch",
        ) from exc
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session Agent session not found",
        ) from exc
    response.headers["Cache-Control"] = "no-store"
    return result


@deployment_router.get(
    "/v1/deployment-workbench",
    response_model=TargetDeploymentWorkbenchSnapshot,
)
async def get_deployment_workbench(
    request: Request,
    page: TargetDeploymentTuiPage = TargetDeploymentTuiPage.FLEET,
    target_id: str | None = None,
    job_id: str | None = None,
    approval_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> TargetDeploymentWorkbenchSnapshot:
    """Return the secret-closed GUI/TUI deployment projection from persistent stores."""

    try:
        return _deployment_workbench(request).workbench_snapshot(
            page,
            target_id=target_id,
            job_id=job_id,
            approval_id=approval_id,
            limit=limit,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deployment workbench record not found",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@deployment_router.get(
    "/v1/targets/{target_id}",
    response_model=TargetRegistrationRequest,
)
async def get_registered_target(
    target_id: str,
    request: Request,
) -> TargetRegistrationRequest:
    try:
        return _registration_service(request).load(target_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target not found",
        ) from exc


@deployment_router.post(
    "/v1/targets/{target_id}/connection-assessments",
    response_model=DeploymentJobRecord,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_connection_assessment(
    target_id: str,
    submission: TargetConnectionAssessmentSubmission,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    principal: Annotated[str | None, Header(alias="X-Rolo-Principal")] = None,
    permissions: Annotated[str | None, Header(alias="X-Rolo-Permissions")] = None,
) -> DeploymentJobRecord:
    try:
        registration = _registration_service(request).load(target_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target not found",
        ) from exc
    parameters_sha256 = target_connection_binding_sha256(
        registration.target,
        registration.connection,
    )
    return _create_job(
        request,
        target_id=target_id,
        command_kind=DeploymentCommandKind.ASSESS_CONNECTION,
        submission=DeploymentJobSubmission(
            active_probe=submission.active_probe,
            run_adapter_agent=False,
            parameters_sha256=parameters_sha256,
        ),
        idempotency_key=idempotency_key,
        principal=principal,
        permissions=permissions,
    )


@deployment_router.post(
    "/v1/targets/{target_id}/bootstrap-jobs",
    response_model=TargetBootstrapApiSubmissionResult,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_bootstrap_job(
    target_id: str,
    submission: TargetBootstrapJobSubmission,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    principal: Annotated[str | None, Header(alias="X-Rolo-Principal")] = None,
    permissions: Annotated[str | None, Header(alias="X-Rolo-Permissions")] = None,
) -> TargetBootstrapApiSubmissionResult:
    canonical_principal, canonical_key = _write_identity(
        request,
        required_permission=_TARGET_PERMISSION,
        idempotency_key=idempotency_key,
        principal=principal,
        permissions=permissions,
    )
    try:
        result: TargetBootstrapJobSubmissionResult = await run_in_threadpool(
            _bootstrap_submission_service(request).submit,
            target_id=target_id,
            submission=submission,
            requested_by=canonical_principal,
            interaction_surface=InteractionSurface.API,
            idempotency_key=canonical_key,
        )
        return TargetBootstrapApiSubmissionResult(
            job=result.job,
            approval=result.approval,
            package_ref=submission.package_ref,
            manifest_sha256=result.spec.manifest_sha256,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target or package not found",
        ) from exc
    except (DeploymentJobStateConflict, OSError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@deployment_router.post(
    "/v1/targets/{target_id}/host-provisioning-jobs",
    response_model=TargetHostProvisioningApiSubmissionResult,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_target_host_provisioning_job(
    target_id: str,
    submission: TargetHostProvisioningJobSubmission,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    principal: Annotated[str | None, Header(alias="X-Rolo-Principal")] = None,
    permissions: Annotated[str | None, Header(alias="X-Rolo-Permissions")] = None,
) -> TargetHostProvisioningApiSubmissionResult:
    canonical_principal, canonical_key = _write_identity(
        request,
        required_permission=_TARGET_PERMISSION,
        idempotency_key=idempotency_key,
        principal=principal,
        permissions=permissions,
    )
    try:
        result: TargetHostProvisioningJobSubmissionResult = await run_in_threadpool(
            _host_provisioning_submission_service(request).submit,
            target_id=target_id,
            submission=submission,
            requested_by=canonical_principal,
            interaction_surface=InteractionSurface.API,
            idempotency_key=canonical_key,
        )
        return TargetHostProvisioningApiSubmissionResult(
            job=result.job,
            approval=result.approval,
            plan_sha256=result.spec.plan.canonical_sha256(),
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target not found",
        ) from exc
    except (DeploymentJobStateConflict, OSError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@deployment_router.post(
    "/v1/jobs/{original_job_id}/host-reconciliation-jobs",
    response_model=TargetHostReconciliationApiSubmissionResult,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_target_host_reconciliation_job(
    original_job_id: str,
    submission: TargetHostReconciliationApiSubmission,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    principal: Annotated[str | None, Header(alias="X-Rolo-Principal")] = None,
    permissions: Annotated[str | None, Header(alias="X-Rolo-Permissions")] = None,
) -> TargetHostReconciliationApiSubmissionResult:
    canonical_principal, canonical_key = _write_identity(
        request,
        required_permission=_TARGET_PERMISSION,
        idempotency_key=idempotency_key,
        principal=principal,
        permissions=permissions,
    )
    try:
        result: TargetHostReconciliationJobSubmissionResult = await run_in_threadpool(
            _host_reconciliation_submission_service(request).submit,
            submission=TargetHostReconciliationJobSubmission(
                original_job_id=original_job_id,
                approver_principal=submission.approver_principal,
                approval_ttl_s=submission.approval_ttl_s,
            ),
            requested_by=canonical_principal,
            interaction_surface=InteractionSurface.API,
            idempotency_key=canonical_key,
        )
        return TargetHostReconciliationApiSubmissionResult(
            job=result.job,
            approval=result.approval,
            original_job_id=result.spec.original_job_id,
            plan_sha256=result.spec.plan.canonical_sha256(),
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Host provisioning Job not found",
        ) from exc
    except (DeploymentJobStateConflict, OSError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@deployment_router.post(
    "/v1/jobs/{current_host_job_id}/host-rollback-jobs",
    response_model=TargetHostRollbackApiSubmissionResult,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_target_host_rollback_job(
    current_host_job_id: str,
    submission: TargetHostRollbackApiSubmission,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    principal: Annotated[str | None, Header(alias="X-Rolo-Principal")] = None,
    permissions: Annotated[str | None, Header(alias="X-Rolo-Permissions")] = None,
) -> TargetHostRollbackApiSubmissionResult:
    canonical_principal, canonical_key = _write_identity(
        request,
        required_permission=_TARGET_PERMISSION,
        idempotency_key=idempotency_key,
        principal=principal,
        permissions=permissions,
    )
    try:
        result: TargetHostRollbackJobSubmissionResult = await run_in_threadpool(
            _host_rollback_submission_service(request).submit,
            submission=TargetHostRollbackJobSubmission(
                current_host_job_id=current_host_job_id,
                rollback_to_host_job_id=submission.rollback_to_host_job_id,
                approver_principal=submission.approver_principal,
                approval_ttl_s=submission.approval_ttl_s,
            ),
            requested_by=canonical_principal,
            interaction_surface=InteractionSurface.API,
            idempotency_key=canonical_key,
        )
        return TargetHostRollbackApiSubmissionResult(
            job=result.job,
            approval=result.approval,
            current_host_job_id=result.current_host_job_id,
            rollback_to_host_job_id=result.rollback_to_host_job_id,
            rollback_plan_sha256=result.spec.plan.canonical_sha256(),
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Host configuration Job not found",
        ) from exc
    except (DeploymentJobStateConflict, OSError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@deployment_router.post(
    "/v1/host-service-jobs",
    response_model=TargetHostServiceApiSubmissionResult,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_target_host_service_job(
    submission: TargetHostServiceApiSubmission,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    principal: Annotated[str | None, Header(alias="X-Rolo-Principal")] = None,
    permissions: Annotated[str | None, Header(alias="X-Rolo-Permissions")] = None,
) -> TargetHostServiceApiSubmissionResult:
    canonical_principal, canonical_key = _write_identity(
        request,
        required_permission=_TARGET_PERMISSION,
        idempotency_key=idempotency_key,
        principal=principal,
        permissions=permissions,
    )
    try:
        result: TargetHostServiceJobSubmissionResult = await run_in_threadpool(
            _host_service_submission_service(request).submit,
            submission=TargetHostServiceJobSubmission(
                host_configuration_job_id=submission.host_configuration_job_id,
                bootstrap_job_id=submission.bootstrap_job_id,
                approver_principal=submission.approver_principal,
                approval_ttl_s=submission.approval_ttl_s,
            ),
            requested_by=canonical_principal,
            interaction_surface=InteractionSurface.API,
            idempotency_key=canonical_key,
        )
        return TargetHostServiceApiSubmissionResult(
            job=result.job,
            approval=result.approval,
            request_sha256=result.spec.request.canonical_sha256(),
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Host configuration or Bootstrap Job not found",
        ) from exc
    except (DeploymentJobStateConflict, OSError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@deployment_router.post(
    "/v1/jobs/{original_job_id}/host-service-reconciliation-jobs",
    response_model=TargetHostServiceReconciliationApiSubmissionResult,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_target_host_service_reconciliation_job(
    original_job_id: str,
    submission: TargetHostServiceReconciliationApiSubmission,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    principal: Annotated[str | None, Header(alias="X-Rolo-Principal")] = None,
    permissions: Annotated[str | None, Header(alias="X-Rolo-Permissions")] = None,
) -> TargetHostServiceReconciliationApiSubmissionResult:
    canonical_principal, canonical_key = _write_identity(
        request,
        required_permission=_TARGET_PERMISSION,
        idempotency_key=idempotency_key,
        principal=principal,
        permissions=permissions,
    )
    try:
        result: TargetHostServiceReconciliationJobSubmissionResult = (
            await run_in_threadpool(
                _host_service_reconciliation_submission_service(request).submit,
                submission=TargetHostServiceReconciliationJobSubmission(
                    original_job_id=original_job_id,
                    approver_principal=submission.approver_principal,
                    approval_ttl_s=submission.approval_ttl_s,
                ),
                requested_by=canonical_principal,
                interaction_surface=InteractionSurface.API,
                idempotency_key=canonical_key,
            )
        )
        return TargetHostServiceReconciliationApiSubmissionResult(
            job=result.job,
            approval=result.approval,
            original_job_id=result.spec.original_job_id,
            request_sha256=result.spec.request.canonical_sha256(),
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target service Job not found",
        ) from exc
    except (DeploymentJobStateConflict, OSError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@deployment_router.post(
    "/v1/targets/{target_id}/runtime-rollback-jobs",
    response_model=TargetRuntimeRollbackApiSubmissionResult,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_target_runtime_rollback_job(
    target_id: str,
    submission: TargetRuntimeRollbackSubmission,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    principal: Annotated[str | None, Header(alias="X-Rolo-Principal")] = None,
    permissions: Annotated[str | None, Header(alias="X-Rolo-Permissions")] = None,
) -> TargetRuntimeRollbackApiSubmissionResult:
    canonical_principal, canonical_key = _write_identity(
        request,
        required_permission=_TARGET_PERMISSION,
        idempotency_key=idempotency_key,
        principal=principal,
        permissions=permissions,
    )
    try:
        result: TargetRuntimeRollbackJobSubmissionResult = await run_in_threadpool(
            _runtime_rollback_submission_service(request).submit,
            target_id=target_id,
            submission=submission,
            requested_by=canonical_principal,
            interaction_surface=InteractionSurface.API,
            idempotency_key=canonical_key,
        )
        return TargetRuntimeRollbackApiSubmissionResult(
            job=result.job,
            approval=result.approval,
            package_id=result.spec.package_id,
            expected_current_manifest_sha256=(result.spec.expected_current_manifest_sha256),
            expected_previous_manifest_sha256=(result.spec.expected_previous_manifest_sha256),
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target not found",
        ) from exc
    except (DeploymentJobStateConflict, OSError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@deployment_router.post(
    "/v1/targets/{target_id}/adapt-jobs",
    response_model=DeploymentJobRecord,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_adapt_job(
    target_id: str,
    submission: TargetAdaptJobSubmission,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    principal: Annotated[str | None, Header(alias="X-Rolo-Principal")] = None,
    permissions: Annotated[str | None, Header(alias="X-Rolo-Permissions")] = None,
) -> DeploymentJobRecord:
    canonical_principal, canonical_key = _write_identity(
        request,
        required_permission=_TARGET_PERMISSION,
        idempotency_key=idempotency_key,
        principal=principal,
        permissions=permissions,
    )
    try:
        registration = _registration_service(request).load(target_id)
        settings = request.app.state.runtime.settings
        binding = None
        if submission.project_evidence_job_id is not None:
            binding = resolve_target_adapt_project_evidence_binding(
                job_id=submission.project_evidence_job_id,
                target_id=target_id,
                target_registration_sha256=target_connection_binding_sha256(
                    registration.target,
                    registration.connection,
                ),
                jobs=_job_store(request),
                artifacts=TargetProjectEvidenceArtifactStore(
                    settings.rolo_artifact_dir / "deployment-jobs" / "artifacts"
                ),
                max_age_s=submission.project_evidence_max_age_s,
            )
        source_binding = None
        if submission.source_discovery_job_id is not None:
            if binding is None:
                raise ValueError(
                    "source discovery binding requires project evidence workspace binding"
                )
            source_binding = resolve_target_adapt_source_discovery_binding(
                job_id=submission.source_discovery_job_id,
                target_id=target_id,
                target_registration_sha256=target_connection_binding_sha256(
                    registration.target,
                    registration.connection,
                ),
                workspace_sha256=binding.workspace_sha256,
                jobs=_job_store(request),
                artifacts=TargetSourceDiscoveryArtifactStore(
                    settings.rolo_artifact_dir / "deployment-jobs" / "artifacts"
                ),
                max_age_s=submission.source_discovery_max_age_s,
            )
        runtime_binding = None
        if submission.runtime_evidence_job_id is not None:
            runtime_binding = resolve_target_adapt_runtime_evidence_binding(
                job_id=submission.runtime_evidence_job_id,
                target_id=target_id,
                target_registration_sha256=target_connection_binding_sha256(
                    registration.target,
                    registration.connection,
                ),
                jobs=_job_store(request),
                artifacts=TargetRuntimeEvidenceArtifactStore(
                    settings.rolo_artifact_dir / "deployment-jobs" / "artifacts"
                ),
                pins=CollectorEnrollmentPinRegistry(settings.target_profile_dir / "enrollment-v4"),
                max_age_s=submission.runtime_evidence_max_age_s,
            )
        spec = build_target_adapt_job_spec(
            registration,
            submission,
            project_evidence=binding,
            source_discovery=source_binding,
            runtime_evidence=runtime_binding,
        )
        return TargetAdaptJobSubmissionService(
            _job_store(request),
            TargetAdaptJobSpecStore(settings.rolo_artifact_dir / "deployment-jobs" / "specs"),
        ).submit(
            spec,
            requested_by=canonical_principal,
            interaction_surface=InteractionSurface.API,
            idempotency_key=canonical_key,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target not found",
        ) from exc
    except (DeploymentJobStateConflict, OSError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@deployment_router.post(
    "/v1/targets/{target_id}/project-evidence-jobs",
    response_model=TargetProjectEvidenceJobSubmissionResult,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_project_evidence_job(
    target_id: str,
    submission: TargetProjectEvidenceJobSubmission,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    principal: Annotated[str | None, Header(alias="X-Rolo-Principal")] = None,
    permissions: Annotated[str | None, Header(alias="X-Rolo-Permissions")] = None,
) -> TargetProjectEvidenceJobSubmissionResult:
    canonical_principal, canonical_key = _write_identity(
        request,
        required_permission=_TARGET_PERMISSION,
        idempotency_key=idempotency_key,
        principal=principal,
        permissions=permissions,
    )
    try:
        return _project_evidence_submission_service(request).submit(
            target_id=target_id,
            submission=submission,
            requested_by=canonical_principal,
            interaction_surface=InteractionSurface.API,
            idempotency_key=canonical_key,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target not found",
        ) from exc
    except (DeploymentJobStateConflict, OSError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@deployment_router.post(
    "/v1/targets/{target_id}/source-discovery-jobs",
    response_model=TargetSourceDiscoveryJobSubmissionResult,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_source_discovery_job(
    target_id: str,
    submission: TargetSourceDiscoveryJobSubmission,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    principal: Annotated[str | None, Header(alias="X-Rolo-Principal")] = None,
    permissions: Annotated[str | None, Header(alias="X-Rolo-Permissions")] = None,
) -> TargetSourceDiscoveryJobSubmissionResult:
    canonical_principal, canonical_key = _write_identity(
        request,
        required_permission=_TARGET_PERMISSION,
        idempotency_key=idempotency_key,
        principal=principal,
        permissions=permissions,
    )
    try:
        return _source_discovery_submission_service(request).submit(
            target_id=target_id,
            submission=submission,
            requested_by=canonical_principal,
            interaction_surface=InteractionSurface.API,
            idempotency_key=canonical_key,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target not found",
        ) from exc
    except (DeploymentJobStateConflict, OSError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@deployment_router.post(
    "/v1/targets/{target_id}/runtime-evidence-jobs",
    response_model=TargetRuntimeEvidenceJobSubmissionResult,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_runtime_evidence_job(
    target_id: str,
    submission: TargetRuntimeEvidenceJobSubmission,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    principal: Annotated[str | None, Header(alias="X-Rolo-Principal")] = None,
    permissions: Annotated[str | None, Header(alias="X-Rolo-Permissions")] = None,
) -> TargetRuntimeEvidenceJobSubmissionResult:
    canonical_principal, canonical_key = _write_identity(
        request,
        required_permission=_TARGET_PERMISSION,
        idempotency_key=idempotency_key,
        principal=principal,
        permissions=permissions,
    )
    try:
        return _runtime_evidence_submission_service(request).submit(
            target_id=target_id,
            submission=submission,
            requested_by=canonical_principal,
            interaction_surface=InteractionSurface.API,
            idempotency_key=canonical_key,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target not found",
        ) from exc
    except (DeploymentJobStateConflict, OSError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@deployment_router.get("/v1/jobs/{job_id}", response_model=DeploymentJobRecord)
async def get_deployment_job(job_id: str, request: Request) -> DeploymentJobRecord:
    try:
        return _job_store(request).load_job(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@deployment_router.get("/v1/jobs/{job_id}/events")
async def get_deployment_events(
    job_id: str,
    request: Request,
    after_sequence: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    output: Annotated[Literal["json", "sse"], Query(alias="format")] = "json",
) -> Response:
    store = _job_store(request)
    try:
        store.load_job(job_id)
        if output == "sse":
            return StreamingResponse(
                store.iter_sse(job_id, after_sequence=after_sequence, limit=limit),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
            )
        items = store.read_events(
            job_id,
            after_sequence=after_sequence,
            limit=limit,
        )
        page = DeploymentEventPage(
            job_id=job_id,
            after_sequence=after_sequence,
            next_sequence=items[-1].sequence if items else after_sequence,
            items=items,
        )
        return JSONResponse(content=page.model_dump(mode="json"))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@deployment_router.post(
    "/v1/jobs/{job_id}/cancel",
    response_model=DeploymentJobRecord,
)
async def cancel_deployment_job(
    job_id: str,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    principal: Annotated[str | None, Header(alias="X-Rolo-Principal")] = None,
    permissions: Annotated[str | None, Header(alias="X-Rolo-Permissions")] = None,
) -> DeploymentJobRecord:
    _write_identity(
        request,
        required_permission=_TARGET_PERMISSION,
        idempotency_key=idempotency_key,
        principal=principal,
        permissions=permissions,
    )
    store = _job_store(request)
    try:
        current = store.load_job(job_id)
        return current if current.cancel_requested else store.request_cancel(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found") from exc
    except DeploymentJobStateConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@deployment_router.post(
    "/v1/jobs/{job_id}/run",
    response_model=DeploymentJobRecord,
)
async def run_deployment_job(
    job_id: str,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    principal: Annotated[str | None, Header(alias="X-Rolo-Principal")] = None,
    permissions: Annotated[str | None, Header(alias="X-Rolo-Permissions")] = None,
) -> DeploymentJobRecord:
    _write_identity(
        request,
        required_permission=_TARGET_PERMISSION,
        idempotency_key=idempotency_key,
        principal=principal,
        permissions=permissions,
    )
    try:
        return await run_in_threadpool(_job_runner(request).run, job_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found") from exc
    except (DeploymentJobStateConflict, OSError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@deployment_router.post("/v1/approvals/{approval_id}/decisions")
async def decide_deployment_approval(
    approval_id: str,
    decision_input: DeploymentApprovalDecisionInput,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    principal: Annotated[str | None, Header(alias="X-Rolo-Principal")] = None,
    permissions: Annotated[str | None, Header(alias="X-Rolo-Permissions")] = None,
) -> JSONResponse:
    canonical_principal, canonical_key = _write_identity(
        request,
        required_permission=_APPROVAL_PERMISSION,
        idempotency_key=idempotency_key,
        principal=principal,
        permissions=permissions,
    )
    store = _job_store(request)
    decision_id = (
        "decision-" + hashlib.sha256(f"{approval_id}:{canonical_key}".encode()).hexdigest()[:32]
    )
    try:
        try:
            decision = store.decide_approval(
                approval_id,
                principal=canonical_principal,
                approve=decision_input.approve,
                reason=decision_input.reason,
                decision_id=decision_id,
            )
        except FileExistsError:
            decision = store.load_approval_decision(approval_id)
            expected_status = (
                ApprovalStatus.APPROVED if decision_input.approve else ApprovalStatus.REJECTED
            )
            if (
                decision.decision_id != decision_id
                or decision.principal != canonical_principal
                or decision.status != expected_status
                or decision.sanitized_reason != sanitize_deployment_summary(decision_input.reason)
            ):
                raise DeploymentJobStateConflict(
                    "approval already has a different decision"
                ) from None
        return JSONResponse(content=decision.model_dump(mode="json"))
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval not found",
        ) from exc
    except (DeploymentJobStateConflict, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
