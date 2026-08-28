"""Stage 2: constrained closed-loop diagnosis, tuning, and robot_use supervision."""

from rolo.stages.diagnose.service import (
    assess_diagnose,
    build_diagnosis_task,
    create_diagnosis_tool_consumer,
)
from rolo.stages.diagnose_contract import DiagnosisReport, validate_structured_diagnosis_report
from rolo.stages.handoffs import commit_diagnosis_handoff

__all__ = [
    "assess_diagnose",
    "build_diagnosis_task",
    "commit_diagnosis_handoff",
    "create_diagnosis_tool_consumer",
    "DiagnosisReport",
    "validate_structured_diagnosis_report",
]
