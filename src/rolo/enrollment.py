"""Compatibility imports for Stage 1 enrollment APIs."""

from rolo.stages.deploy.enrollment import (
    PROFILE_ID_PATTERN,
    EnrollmentResult,
    EnrollmentService,
    list_profiles,
    resolve_profile_root,
)

__all__ = [
    "PROFILE_ID_PATTERN",
    "EnrollmentResult",
    "EnrollmentService",
    "list_profiles",
    "resolve_profile_root",
]
