"""Deterministic, product-owned semantic rules for application CLIs.

The rules are deliberately project-neutral.  They consume only a declared
console entrypoint and an exact target-observed, self-described CLI route.  A
matching name is applicability evidence, not proof that invoking the program
will satisfy an Operation contract; Adapter conformance remains mandatory.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
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


def application_cli_rule_path() -> Path:
    return Path(__file__).with_name("application_cli_operation_rules.yaml")


@lru_cache(maxsize=1)
def load_application_cli_operation_rules() -> ApplicationCliOperationRuleSet:
    rules = ApplicationCliOperationRuleSet.model_validate(
        yaml.safe_load(application_cli_rule_path().read_text(encoding="utf-8"))
    )
    from rolo.stages.adapt.operation_registry import canonical_operation_registry

    known = {item.operation for item in canonical_operation_registry().operations}
    unknown = sorted(
        operation for rule in rules.rules for operation in rule.operations if operation not in known
    )
    if unknown:
        raise ValueError(f"application CLI rules reference unknown Operations: {unknown}")
    return rules


def matching_application_cli_rules(value: str) -> list[ApplicationCliOperationRule]:
    tokens = executable_tokens(value)
    return [
        rule
        for rule in load_application_cli_operation_rules().rules
        if all(tokens.intersection(group) for group in rule.executable_token_groups)
        and not tokens.intersection(rule.excluded_tokens)
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
            for rule in matching_application_cli_rules(route.endpoint):
                semantic_uri = rule.semantic_uri
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
                    "semantic_rule_id": rule.rule_id,
                    "operations": list(rule.operations),
                    "route_kind": "cli",
                    "resource_id": route.resource_id,
                    "observed": True,
                }
        return bindings
