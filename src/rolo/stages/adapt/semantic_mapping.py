"""Registry-linked deterministic semantic rules for declared and observed ROS topics."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SemanticOperationRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    topic_segments: list[str] = Field(min_length=1)
    topic_prefixes: list[str] = Field(default_factory=list)
    semantic_uri: str = Field(pattern=r"^semantic://")
    operations: list[str] = Field(default_factory=list)

    @field_validator("topic_segments", "topic_prefixes", "operations")
    @classmethod
    def require_unique_values(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("semantic rule collections must be unique")
        return sorted(value)


class SemanticOperationRuleSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(pattern=r"^rolo-semantic-operation-rules/v\d+$")
    rules: list[SemanticOperationRule] = Field(min_length=1)

    @model_validator(mode="after")
    def require_unique_rules(self) -> SemanticOperationRuleSet:
        rule_ids = [item.rule_id for item in self.rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("semantic rule IDs must be unique")
        return self


def semantic_operation_rule_path() -> Path:
    return Path(__file__).with_name("semantic_operation_rules.yaml")


@lru_cache(maxsize=1)
def load_semantic_operation_rules() -> SemanticOperationRuleSet:
    payload = yaml.safe_load(
        semantic_operation_rule_path().read_text(encoding="utf-8")
    )
    rules = SemanticOperationRuleSet.model_validate(payload)

    # Import lazily so discovery rules remain data, while the active 294-item
    # Registry is still the authority for every Operation identifier.
    from rolo.stages.adapt.operation_registry import canonical_operation_registry

    known = {item.operation for item in canonical_operation_registry().operations}
    unknown = sorted(
        operation
        for rule in rules.rules
        for operation in rule.operations
        if operation not in known
    )
    if unknown:
        raise ValueError(f"semantic rules reference unknown Operations: {unknown}")
    return rules


def matching_semantic_rules(topic: str) -> list[SemanticOperationRule]:
    segments = [segment for segment in topic.casefold().split("/") if segment]
    matches: list[SemanticOperationRule] = []
    for rule in load_semantic_operation_rules().rules:
        if any(token in segments for token in rule.topic_segments) or any(
            segment.startswith(prefix)
            for segment in segments
            for prefix in rule.topic_prefixes
        ):
            matches.append(rule)
    return matches
