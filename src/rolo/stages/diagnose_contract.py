"""Provider-neutral, evidence-bound Diagnose report contract."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator


class DiagnosisReport(BaseModel):
    """The minimum closed-loop record required before Diagnose is COMPLETE."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-diagnosis-report/v1"] = "rolo-diagnosis-report/v1"
    robot_id: str = Field(min_length=1, max_length=128)
    baseline: dict[str, JsonValue] = Field(min_length=1)
    observations: list[dict[str, JsonValue]] = Field(min_length=1, max_length=256)
    hypotheses: list[dict[str, JsonValue]] = Field(min_length=1, max_length=128)
    changes: list[dict[str, JsonValue]] = Field(min_length=1, max_length=128)
    smoke: dict[str, JsonValue] = Field(min_length=1)
    decision: Literal["COMMIT", "ROLLBACK", "INCONCLUSIVE"]
    episode_refs: list[str] = Field(min_length=1, max_length=256)
    limitations: list[str] = Field(default_factory=list, max_length=128)

    @field_validator("episode_refs")
    @classmethod
    def validate_episode_refs(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("diagnosis episode references must be unique")
        for reference in value:
            if not reference.startswith("artifact://"):
                raise ValueError("diagnosis episode references must use artifact://")
        return value

    @model_validator(mode="after")
    def validate_closed_loop(self) -> DiagnosisReport:
        if any(not item for item in self.observations + self.hypotheses + self.changes):
            raise ValueError("diagnosis observations, hypotheses, and changes cannot be empty")
        return self


def validate_structured_diagnosis_report(
    report: Mapping[str, object], *, robot_id: str | None = None
) -> DiagnosisReport:
    """Parse the strict contract and optionally bind it to the requested robot."""

    parsed = DiagnosisReport.model_validate(report)
    if robot_id is not None and parsed.robot_id != robot_id:
        raise ValueError("diagnosis report robot identity mismatch")
    return parsed
