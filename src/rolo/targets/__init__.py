"""Transport-neutral target inspection and bootstrap planning."""

from rolo.targets.approvals import (
    BootstrapApprovalDecision,
    BootstrapApprovalRequest,
    approve_bootstrap,
    bootstrap_plan_digest,
    request_bootstrap_approval,
)
from rolo.targets.bootstrap import (
    BootstrapExecutionResult,
    BootstrapTransport,
    LocalBootstrapTransport,
    SubprocessBootstrapTransport,
    execute_bootstrap,
)
from rolo.targets.executor import (
    LocalTargetExecutor,
    SshTargetExecutor,
    SubprocessCommandRunner,
    TargetExecutor,
    create_target_executor,
)
from rolo.targets.models import (
    BootstrapAction,
    BootstrapPlanStatus,
    CompanionStatus,
    TargetBootstrapPlan,
    TargetConnectionAssessment,
    TargetConnectionState,
    TargetRisk,
)
from rolo.targets.package import build_companion_package
from rolo.targets.profiles import (
    CredentialReference,
    HostKeyDecision,
    TargetProfile,
    TargetProfileStore,
)
from rolo.targets.signing import (
    CompanionManifest,
    ManifestVerificationResult,
    sign_companion_manifest,
    verify_companion_manifest,
)

__all__ = [
    "BootstrapAction",
    "BootstrapApprovalDecision",
    "BootstrapApprovalRequest",
    "BootstrapExecutionResult",
    "BootstrapTransport",
    "BootstrapPlanStatus",
    "CompanionStatus",
    "CompanionManifest",
    "CredentialReference",
    "HostKeyDecision",
    "LocalTargetExecutor",
    "LocalBootstrapTransport",
    "ManifestVerificationResult",
    "SshTargetExecutor",
    "SubprocessCommandRunner",
    "SubprocessBootstrapTransport",
    "TargetBootstrapPlan",
    "TargetConnectionAssessment",
    "TargetConnectionState",
    "TargetExecutor",
    "TargetRisk",
    "TargetProfile",
    "TargetProfileStore",
    "approve_bootstrap",
    "bootstrap_plan_digest",
    "create_target_executor",
    "execute_bootstrap",
    "request_bootstrap_approval",
    "sign_companion_manifest",
    "verify_companion_manifest",
    "build_companion_package",
]
