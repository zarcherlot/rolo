"""Registry-linked deterministic semantic rules for declared and observed ROS topics."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

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


@dataclass(frozen=True)
class TopicOperationMatch:
    """One registry Operation suggested by generic ROS topic evidence."""

    operation: str
    semantic_uri: str
    score: float
    evidence: tuple[str, ...]
    rationale: str


_TOPIC_TOKEN_RE = re.compile(r"[a-z0-9]+")
_TOPIC_STOP_TOKENS = {
    "app",
    "hw",
    "ros",
    "topic",
    "msg",
    "msgs",
    "message",
    "status",
    "sample",
    "snapshot",
    "read",
    "readings",
    "data",
    "the",
    "and",
    "or",
    "of",
}
_ENERGY_SIGNAL_TOKENS = frozenset(
    {"battery", "voltage", "current", "charge", "capacity", "soc", "power"}
)


def _topic_tokens(value: str) -> set[str]:
    return {
        token
        for token in _TOPIC_TOKEN_RE.findall(str(value).casefold())
        if token not in _TOPIC_STOP_TOKENS
    }


def _operation_terms(definition: Any) -> set[str]:
    values = [
        definition.operation,
        definition.description,
        *definition.capability_requirements,
        *definition.side_effects,
        *definition.semantic_units,
    ]
    return _topic_tokens(" ".join(str(value) for value in values))


def infer_topic_operations(
    topic: str,
    *,
    interface_type: str | None = None,
    max_matches: int = 1,
) -> list[TopicOperationMatch]:
    """Suggest registry Operations from topic/type evidence without vendor rules.

    This is deliberately a proposal layer.  It does not assert that a topic
    implements a contract: the resulting route remains unverified until target
    interface schema, provider identity, runtime revision, and conformance are
    collected.  The scorer uses registry-owned descriptions and capability
    requirements so a new platform can be handled without adding its topic
    names to this module.
    """

    if not str(topic).strip() or max_matches < 1:
        return []
    endpoint_tokens = _topic_tokens(topic)
    type_tokens = _topic_tokens(interface_type or "")
    evidence_tokens = endpoint_tokens | type_tokens
    if not evidence_tokens:
        return []
    if (
        "parameter" in endpoint_tokens
        and "events" in endpoint_tokens
    ) or "parameterevent" in type_tokens:
        # A ParameterEvent stream reports changes after they occur.  It does
        # not provide the request/response semantics needed by parameter get,
        # list, inspect, or validate Operations.  Treating the lexical token
        # "parameter" as current-value evidence creates a false capability.
        return []

    from rolo.stages.adapt.operation_registry import canonical_operation_registry

    matches: list[TopicOperationMatch] = []
    for definition in canonical_operation_registry().operations:
        if definition.layer not in {"app", "hw"}:
            continue
        if definition.contract_lifecycle.value not in {"GATEABLE", "RELEASED"}:
            continue
        terms = _operation_terms(definition)
        operation_tokens = _topic_tokens(definition.operation)
        domain_terms = operation_tokens | {
            token
            for token in terms
            if token
            in {
                "battery",
                "power",
                "voltage",
                "current",
                "charge",
                "capacity",
                "imu",
                "lidar",
                "camera",
                "odometry",
                "localization",
                "gnss",
                "telemetry",
            }
        }
        direct_overlap = endpoint_tokens & domain_terms
        type_overlap = type_tokens & terms
        signal_overlap = evidence_tokens & _ENERGY_SIGNAL_TOKENS
        energy_contract = terms & {"battery", "power", "voltage", "current", "charge", "capacity"}
        if definition.operation == "hw.power.battery.status" and not signal_overlap:
            # Generic telemetry (temperature, diagnostics, etc.) is not battery
            # evidence merely because the contract description mentions telemetry.
            continue
        generic_telemetry = "telemetry" in evidence_tokens and not signal_overlap
        if generic_telemetry and not definition.operation.startswith("app.telemetry."):
            # A generic telemetry stream should stay in the application telemetry
            # family; do not misclassify it as power/storage just because those
            # contracts use the word telemetry in their prose.
            continue
        if not direct_overlap and not (signal_overlap and energy_contract):
            continue
        score = (
            len(direct_overlap) * 6.0
            + len(type_overlap) * 2.0
            + len(terms & evidence_tokens) * 0.25
            + min(len(domain_terms), 4) * 0.5
        )
        if signal_overlap and "battery" in terms:
            # Voltage/current/charge are generic battery signals across ROS,
            # DDS, and vendor application stacks; this is not a vendor map.
            score += 3.0
        if definition.access == "write":
            # Do not let a lexical topic hint make a motion/control route look
            # stronger than a read-only observation without explicit command
            # evidence in the topic/type.
            score -= 2.0
        if score < 7.0:
            continue
        evidence = [
            *(f"topic:{token}" for token in sorted(direct_overlap)),
            *(f"type:{token}" for token in sorted(type_overlap)),
        ]
        matches.append(
            TopicOperationMatch(
                operation=definition.operation,
                semantic_uri=(
                    "semantic://heuristic/topic/"
                    + hashlib.sha256(
                        f"{topic}\0{interface_type or ''}\0{definition.operation}".encode()
                    ).hexdigest()[:16]
                ),
                score=score,
                evidence=tuple(sorted(set(evidence))),
                rationale=(
                    f"heuristic score={score:.2f}; topic={','.join(sorted(endpoint_tokens))}; "
                    f"type={','.join(sorted(type_tokens)) or 'none'}"
                ),
            )
        )
    telemetry_priority = {
        "app.telemetry.snapshot": 0,
        "app.telemetry.watch": 1,
        "app.telemetry.export": 2,
    }
    matches.sort(
        key=lambda item: (-item.score, telemetry_priority.get(item.operation, 9), item.operation)
    )
    if not matches:
        return []
    top = matches[0].score
    return [item for item in matches if item.score >= top - 1.0][:max_matches]


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
