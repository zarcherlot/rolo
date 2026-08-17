"""Compatibility imports for Stage 1 enrollment APIs."""

from rolo.stages.build.enrollment import (
    PROFILE_ID_PATTERN,
    EnrollmentResult,
    EnrollmentService,
    UrdfProfile,
    UrdfSource,
    list_profiles,
    load_urdf_profile,
    load_urdf_source,
    resolve_profile_root,
)

__all__ = [
    "PROFILE_ID_PATTERN",
    "EnrollmentResult",
    "EnrollmentService",
    "UrdfProfile",
    "UrdfSource",
    "list_profiles",
    "load_urdf_profile",
    "load_urdf_source",
    "resolve_profile_root",
]
