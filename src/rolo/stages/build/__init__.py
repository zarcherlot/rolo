"""Stage 1: install, discover, build the canonical CLI, and construct the State Graph."""

from rolo.stages.build.inputs import BuildInputs, BuildInputsStatus
from rolo.stages.build.service import BuildStageService, assess_build

__all__ = ["BuildInputs", "BuildInputsStatus", "BuildStageService", "assess_build"]
