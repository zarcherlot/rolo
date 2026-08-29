"""Heuristic semantic inference for application CLIs.

CLI names are useful hints, but they are not an API contract.  This module
therefore combines the executable name with the target's bounded ``--help``
summary and the canonical Operation Registry.  No vendor-specific or static
operation mapping table is consulted.  The resulting binding is still only
``DISCOVERED_UNVERIFIED`` and must pass the normal Adapter conformance gate.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from rolo.core.models import ProbeResult, RouteEvidence
from rolo.stages.adapt.routes import probe_routes


def executable_tokens(value: str) -> set[str]:
    """Tokenize a portable entrypoint name without preserving vendor prefixes."""
    return set(re.findall(r"[a-z0-9]+", canonical_executable_name(value).casefold()))


def canonical_executable_name(value: str) -> str:
    # Evidence can cross OS boundaries in remote mode.  Do not interpret the
    # target path with the controller's native Path flavour.
    name = str(value).replace("\\", "/").rsplit("/", 1)[-1]
    for suffix in (".exe", ".cmd", ".bat", ".ps1", ".py"):
        if name.casefold().endswith(suffix):
            return name[: -len(suffix)]
    return name


class ApplicationCliOperationRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    executable_token_groups: list[list[str]] = Field(min_length=1)
    excluded_tokens: list[str] = Field(default_factory=list)
    semantic_uri: str = Field(pattern=r"^semantic://")
    operations: list[str] = Field(min_length=1)

    @field_validator("executable_token_groups")
    @classmethod
    def require_canonical_token_groups(cls, value: list[list[str]]) -> list[list[str]]:
        if any(not group for group in value):
            raise ValueError("CLI rule token groups cannot be empty")
        canonical = [sorted(set(token.casefold() for token in group)) for group in value]
        if canonical != sorted(canonical):
            raise ValueError("CLI rule token groups must be unique and sorted")
        return canonical

    @field_validator("excluded_tokens", "operations")
    @classmethod
    def require_unique_values(cls, value: list[str]) -> list[str]:
        if value != sorted(set(value)):
            raise ValueError("CLI rule collections must be unique and sorted")
        return value


class ApplicationCliOperationRuleSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(pattern=r"^rolo-application-cli-operation-rules/v\d+$")
    rules: list[ApplicationCliOperationRule] = Field(min_length=1)

    @model_validator(mode="after")
    def require_unique_rules(self) -> ApplicationCliOperationRuleSet:
        identities = [item.rule_id for item in self.rules]
        if identities != sorted(set(identities)):
            raise ValueError("CLI semantic rule IDs must be unique and sorted")
        return self


@dataclass(frozen=True)
class CliOperationMatch:
    """One registry Operation suggested by CLI/help evidence."""

    operation: str
    semantic_uri: str
    score: float
    evidence: tuple[str, ...]
    rationale: str


_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOP_TOKENS = {
    "app",
    "application",
    "cli",
    "command",
    "commands",
    "robotctl",
    "tool",
    "invoke",
    "operation",
    "route",
    "control",
    "hw",
    "linux",
    "middleware",
    "ros",
    "read",
    "write",
    "target",
    "bounded",
    "one",
    "selected",
    "the",
    "and",
    "or",
    "for",
    "with",
    "from",
    "into",
    "without",
    "metadata",
}

# These are lexical equivalence classes, not Operation-to-command rules.  They
# let ``find`` and ``enumerate`` contribute to a registry ``list`` operation,
# while the registry description remains the source of the actual semantics.
_LEXICAL_CLASSES: dict[str, frozenset[str]] = {
    "list": frozenset(
        {
            "list",
            "lists",
            "find",
            "discover",
            "enumerate",
            "scan",
            "detect",
            "inventory",
            "available",
        }
    ),
    "inspect": frozenset(
        {"inspect", "describe", "details", "detail", "metadata", "information", "info"}
    ),
    "status": frozenset(
        {"status", "state", "health", "check", "diagnostic", "diagnostics", "ready", "readiness"}
    ),
    "snapshot": frozenset({"snapshot", "capture", "frame", "image", "photo", "sample", "read"}),
    "stream": frozenset({"stream", "streaming", "watch", "monitor", "video"}),
    "calibrate": frozenset({"calibrate", "calibration"}),
    "start": frozenset({"start", "launch", "begin", "open", "enable"}),
    "stop": frozenset({"stop", "close", "disable", "cancel", "shutdown"}),
    "control": frozenset(
        {"control", "teleop", "teleoperate", "move", "motion", "command", "rollout"}
    ),
}
_CLASS_BY_TOKEN = {
    token: semantic_class
    for semantic_class, tokens in _LEXICAL_CLASSES.items()
    for token in tokens
}
_DOMAIN_ALIASES: dict[str, frozenset[str]] = {
    "camera": frozenset({"camera", "cameras", "opencv", "realsense", "image", "video"}),
    "actuator": frozenset({"actuator", "motor", "motors", "joint", "joints", "servo", "servos"}),
    "sensor": frozenset({"sensor", "sensors", "imu", "lidar", "gnss", "odometry"}),
    "config": frozenset({"config", "configuration", "settings", "parameters", "parameter"}),
    "dataset": frozenset({"dataset", "datasets", "episode", "episodes"}),
}
_GENERIC_TOOL_TOKENS = {
    "help",
    "version",
    "about",
    "convert",
    "dataset",
    "datasets",
    "train",
    "training",
    "eval",
    "evaluate",
    "tokenizer",
    "annotate",
    "edit",
    "viz",
    "visualize",
}
_SIDE_EFFECTING_ENDPOINT_TOKENS = {
    "calibrate",
    "control",
    "edit",
    "record",
    "replay",
    "rollout",
    "setup",
    "teleop",
    "teleoperate",
    "train",
}


def _semantic_tokens(value: str) -> set[str]:
    """Normalize hyphenated words without guessing inside vendor prefixes."""
    tokens = set(_TOKEN_RE.findall(str(value).casefold())) - _STOP_TOKENS
    normalized = set(tokens)
    for token in tokens:
        if len(token) > 4 and token.endswith("s"):
            normalized.add(token[:-1])
    for canonical, aliases in _DOMAIN_ALIASES.items():
        if normalized & aliases:
            normalized.add(canonical)
    return normalized


@lru_cache(maxsize=1)
def _registry_operations() -> tuple[str, ...]:
    from rolo.stages.adapt.operation_registry import canonical_operation_registry

    return tuple(item.operation for item in canonical_operation_registry().operations)


def _operation_terms(definition: Any) -> set[str]:
    values = [
        definition.operation,
        definition.description,
        *definition.capability_requirements,
        *definition.side_effects,
    ]
    return _semantic_tokens(" ".join(values))


def _semantic_classes(tokens: set[str]) -> set[str]:
    return {_CLASS_BY_TOKEN[token] for token in tokens if token in _CLASS_BY_TOKEN}


def infer_application_cli_operations(
    endpoint: str,
    *,
    usage: Sequence[str] = (),
    parameters: Sequence[str] = (),
    subcommands: Sequence[str] = (),
    help_text: str = "",
    max_matches: int = 3,
) -> list[CliOperationMatch]:
    """Infer Operations from a CLI name plus bounded ``--help`` evidence.

    The scorer is intentionally conservative: a candidate needs a domain
    overlap with a canonical Operation and an action/help signal.  Generic
    package tooling (training, dataset conversion, version reporting, etc.) is
    retained as evidence but does not become an application Operation merely
    because its executable name contains ``robot`` or ``info``.
    """
    from rolo.stages.adapt.operation_registry import canonical_operation_registry

    endpoint_tokens = _semantic_tokens(endpoint)
    help_tokens = _semantic_tokens(
        " ".join([*usage, *parameters, *subcommands, help_text])
    )
    all_tokens = endpoint_tokens | help_tokens
    endpoint_domain_hints = {
        token
        for token in endpoint_tokens
        for aliases in _DOMAIN_ALIASES.values()
        if token in aliases
    }
    if endpoint_tokens & {"info", "version", "about", "help"} and not endpoint_domain_hints:
        return []
    endpoint_classes = _semantic_classes(endpoint_tokens)
    help_classes = _semantic_classes(help_tokens)
    classes = endpoint_classes | help_classes
    generic_tool_signal = bool(endpoint_tokens & _GENERIC_TOOL_TOKENS)
    strong_help = bool(help_text.strip() or usage or subcommands)
    results: list[CliOperationMatch] = []
    for definition in canonical_operation_registry().operations:
        if definition.contract_lifecycle.value not in {"GATEABLE", "RELEASED"}:
            continue
        terms = _operation_terms(definition)
        # Keep operation identifiers' domain nouns literal.  Synonym expansion
        # is applied to help evidence, but must not turn ``parameter`` into
        # ``config`` and make every package-info command look like a parameter
        # API.
        operation_tokens = set(_TOKEN_RE.findall(definition.operation.casefold())) - _STOP_TOKENS
        # A command's entrypoint is stronger evidence than prose in ``--help``.
        # Read-only inventory/status Operations must not be inferred from
        # entrypoints whose primary verb is mutating or motion-producing.
        if definition.access == "read" and (
            endpoint_tokens & _SIDE_EFFECTING_ENDPOINT_TOKENS
        ):
            continue
        # Emergency stop is intentionally not part of the generic lexical
        # ``stop`` class: mapping it requires the explicit emergency-stop
        # intent in the endpoint or an exposed subcommand.
        if definition.operation == "app.safety.emergency_stop":
            explicit_tokens = endpoint_tokens | _semantic_tokens(" ".join(subcommands))
            if not {"emergency", "stop"} <= explicit_tokens:
                continue
        domain_terms = {
            token
            for token in operation_tokens
            if token not in _CLASS_BY_TOKEN and token not in {"status", "inspect", "snapshot"}
        }
        domain_overlap = domain_terms & all_tokens
        if not domain_overlap:
            continue
        endpoint_domain_overlap = domain_terms & endpoint_tokens
        # Usage lines repeat the executable name; do not count that repetition
        # as independent help evidence (otherwise ``robot-tool`` beats a
        # camera-specific description simply because it contains ``robot``).
        help_domain_overlap = domain_terms & (help_tokens - endpoint_tokens)
        operation_classes = _semantic_classes(operation_tokens | terms)
        class_overlap = operation_classes & classes
        textual_overlap = terms & all_tokens
        score = (
            len(endpoint_domain_overlap) * 5.0
            + len(help_domain_overlap) * 6.5
            + len(class_overlap) * 8.0
            + len(textual_overlap) * 0.25
        )
        evidence: list[str] = []
        if endpoint_tokens & domain_terms:
            evidence.append(f"endpoint:{','.join(sorted(endpoint_tokens & domain_terms))}")
        if help_tokens & domain_terms:
            evidence.append(f"help:{','.join(sorted(help_tokens & domain_terms))}")
        if endpoint_classes & operation_classes:
            evidence.append(
                f"endpoint-class:{','.join(sorted(endpoint_classes & operation_classes))}"
            )
        if help_classes & operation_classes:
            evidence.append(f"help-class:{','.join(sorted(help_classes & operation_classes))}")
        if strong_help:
            score += 1.0
        # Package diagnostics and ML/data tooling must not turn into robot
        # health/status candidates from a compound name such as ``lerobot-info``.
        if generic_tool_signal and not (help_classes - {"status", "inspect"}):
            score -= 4.0
        if definition.layer in {"app", "hw"}:
            score += 0.5
        if score >= 8.0:
            results.append(
                CliOperationMatch(
                    operation=definition.operation,
                    semantic_uri=(
                        "semantic://cli/" + definition.operation.replace(".", "/")
                    ),
                    score=score,
                    evidence=tuple(sorted(set(evidence))),
                    rationale=(
                        f"heuristic score={score:.2f}; domain={','.join(sorted(domain_overlap))}; "
                        f"classes={','.join(sorted(class_overlap)) or 'none'}"
                    ),
                )
            )
    results.sort(key=lambda item: (-item.score, item.operation))
    if not results:
        return []
    # Do not emit a tied family of operations when help evidence only supports
    # one semantic intent.  Ties remain useful for the Agent only when the
    # command explicitly exposes multiple subcommands.
    top = results[0].score
    tied = [item for item in results if item.score >= top - 1.0]
    return tied[:max(1, max_matches if subcommands else 1)]


def load_application_cli_operation_rules() -> ApplicationCliOperationRuleSet:
    """Compatibility view for callers of the pre-heuristic API.

    Production discovery no longer loads ``application_cli_operation_rules.yaml``.
    The returned object is generated from the live Registry solely to keep old
    integrations able to inspect the API while they migrate to
    :func:`infer_application_cli_operations`.
    """
    operations = sorted(_registry_operations())
    return ApplicationCliOperationRuleSet(
        schema_version="rolo-application-cli-operation-rules/v1",
        rules=[
            ApplicationCliOperationRule(
                rule_id="heuristic_registry_compat",
                executable_token_groups=[["heuristic"]],
                semantic_uri="semantic://cli/heuristic",
                operations=operations,
            )
        ],
    )


def matching_application_cli_rules(value: str) -> list[ApplicationCliOperationRule]:
    """Compatibility adapter exposing heuristic matches as rule-shaped objects."""
    return [
        ApplicationCliOperationRule(
            rule_id="heuristic_" + match.operation.replace(".", "_"),
            executable_token_groups=[["heuristic"]],
            semantic_uri=match.semantic_uri,
            operations=[match.operation],
        )
        for match in infer_application_cli_operations(value)
    ]


class ApplicationCliRouteProvider:
    """Project-neutral provider for declared and target-observed CLI routes."""

    interface_type = "application/cli"

    def declared_routes(self, projects: Sequence[Mapping[str, Any]]) -> list[RouteEvidence]:
        routes: dict[str, RouteEvidence] = {}
        for project in projects:
            root = str(project.get("root", "unknown"))
            for entrypoint in project.get("entrypoints", []):
                if not isinstance(entrypoint, Mapping):
                    continue
                raw_name = str(entrypoint.get("name", "")).strip()
                if not raw_name:
                    continue
                name = canonical_executable_name(raw_name)
                resource_id = f"cli:{name}"
                routes.setdefault(
                    resource_id,
                    RouteEvidence(
                        resource_id=resource_id,
                        kind="cli",
                        endpoint=name,
                        interface_type=self.interface_type,
                        evidence_origin="DECLARED_STATIC",
                        source=f"source:{root}#entrypoint/{name}",
                        limitations=[
                            "Source manifest declaration does not prove target installation, "
                            "self-description, or runtime availability"
                        ],
                    ),
                )
        return sorted(routes.values(), key=lambda item: item.resource_id)

    def observed_routes(
        self,
        records: Sequence[Any],
        *,
        bundle_payload_sha256: str,
        observed_at: datetime,
    ) -> list[RouteEvidence]:
        routes: dict[str, RouteEvidence] = {}
        for record in records:
            status = getattr(getattr(record, "help_probe", None), "status", None)
            if getattr(status, "value", status) != "SUCCEEDED":
                continue
            if not (record.usage or record.parameters or record.subcommands):
                # Exit code zero alone is not a self-description contract
                # (some entrypoints ignore --help and execute normal startup).
                continue
            interface = {
                "usage": sorted(set(record.usage)),
                "parameters": sorted(set(record.parameters)),
                "subcommands": sorted(set(record.subcommands)),
            }
            encoded = json.dumps(
                interface,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            interface_schema_sha256 = hashlib.sha256(encoded).hexdigest()
            canonical_name = canonical_executable_name(record.path)
            source = (
                f"target-evidence:{bundle_payload_sha256}#executable-help/{record.executable_id}"
            )
            for endpoint in sorted({canonical_name, record.path}):
                route = RouteEvidence(
                    resource_id=f"cli:{endpoint}",
                    kind="cli",
                    endpoint=endpoint,
                    interface_type=self.interface_type,
                    interface_schema_sha256=interface_schema_sha256,
                    provider_id=record.executable_id,
                    runtime_revision=record.executable_sha256,
                    observed_at=observed_at,
                    evidence_origin="OBSERVED_RUNTIME",
                    source=source,
                    limitations=[
                        "Bounded --help proves route identity and self-description only; "
                        "Operation semantics still require mapping and Adapter conformance"
                    ],
                )
                routes[route.resource_id] = route
        return sorted(routes.values(), key=lambda item: item.resource_id)

    def semantic_bindings(
        self,
        application_probe: ProbeResult,
        linux_probe: ProbeResult,
        *,
        occupied_semantic_uris: set[str] | None = None,
    ) -> dict[str, dict[str, Any]]:
        occupied = set(occupied_semantic_uris or ())
        declared_cli_ids = {
            route.resource_id
            for route in probe_routes(application_probe)
            if route.kind == "cli" and not route.observed
        }
        bindings: dict[str, dict[str, Any]] = {}
        target_evidence = linux_probe.data.get("target_evidence", {})
        raw_help_records = (
            target_evidence.get("executable_help", [])
            if isinstance(target_evidence, Mapping)
            else []
        )
        help_records = {
            canonical_executable_name(str(item.get("path", ""))): item
            for item in raw_help_records
            if isinstance(item, Mapping) and item.get("path")
        }
        for route in probe_routes(linux_probe):
            if (
                route.kind != "cli"
                or not route.observed
                or route.interface_type != self.interface_type
                or route.resource_id not in declared_cli_ids
                or route.interface_schema_sha256 is None
                or route.provider_id is None
                or route.runtime_revision is None
            ):
                continue
            record = help_records.get(canonical_executable_name(route.endpoint), {})
            matches = infer_application_cli_operations(
                route.endpoint,
                usage=record.get("usage", []),
                parameters=record.get("parameters", []),
                subcommands=record.get("subcommands", []),
                help_text=str(record.get("output_text", "")),
            )
            for match in matches:
                semantic_uri = match.semantic_uri
                if semantic_uri in occupied or semantic_uri in bindings:
                    digest = hashlib.sha256(route.resource_id.encode("utf-8")).hexdigest()
                    semantic_uri = f"{semantic_uri}/{digest[:16]}"
                bindings[semantic_uri] = {
                    "transport": "application_cli",
                    "binding": route.endpoint,
                    "interface_type": route.interface_type,
                    "interface_schema_sha256": route.interface_schema_sha256,
                    "status": "DISCOVERED_UNVERIFIED",
                    "evidence": route.source,
                    "observed_at": route.observed_at,
                    "runtime_revision": route.runtime_revision,
                    "provider_id": route.provider_id,
                    "semantic_rule_id": f"heuristic:{match.operation}",
                    "mapping_score": match.score,
                    "mapping_rationale": match.rationale,
                    "mapping_evidence": list(match.evidence),
                    "operations": [match.operation],
                    "route_kind": "cli",
                    "resource_id": route.resource_id,
                    "observed": True,
                }
        return bindings
