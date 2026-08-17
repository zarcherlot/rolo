"""Shared configuration, domain models, artifacts, and robot registry."""

from rolo.core.artifacts import ArtifactStore
from rolo.core.config import Settings, get_settings
from rolo.core.registry import RobotRegistry

__all__ = ["ArtifactStore", "RobotRegistry", "Settings", "get_settings"]
