"""Stage 3: optional autonomous verification and full regression."""

from rolo.stages.handoffs import commit_verification_handoff
from rolo.stages.verify.acceptance import (
    VerificationCase,
    VerificationCaseResult,
    VerificationOracle,
    VerificationPlan,
    VerificationRunReport,
    evaluate_oracle,
    run_verification_plan,
)
from rolo.stages.verify.legacy_adapter import (
    LegacyProviderEvidence,
    adapt_legacy_provider_evidence,
)
from rolo.stages.verify.service import (
    assess_verify,
    build_verification_task,
    create_verification_tool_consumer,
    publish_verification_plan,
)

__all__ = [
    "assess_verify",
    "build_verification_task",
    "commit_verification_handoff",
    "create_verification_tool_consumer",
    "publish_verification_plan",
    "VerificationCase",
    "VerificationCaseResult",
    "VerificationOracle",
    "VerificationPlan",
    "VerificationRunReport",
    "evaluate_oracle",
    "run_verification_plan",
    "LegacyProviderEvidence",
    "adapt_legacy_provider_evidence",
]
