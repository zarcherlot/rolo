from __future__ import annotations

import hashlib
import json
import re
from enum import Enum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from rolo.schema_subset import validate_object, validate_schema_definition

_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
_PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")
_CONTEXT_PLACEHOLDERS = {"operation", "robot_id", "input_json"}


class ContractLifecycle(str, Enum):
    DRAFT = "DRAFT"
    GATEABLE = "GATEABLE"
    RELEASED = "RELEASED"
    DEPRECATED = "DEPRECATED"


class OperationContract(BaseModel):
    """Product-owned semantics for one canonical operation."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-operation-contract/v1"] = "robot-operation-contract/v1"
    contract_id: str
    version: str
    lifecycle: ContractLifecycle
    operation: str
    layer: Literal["control", "hw", "linux", "middleware", "ros", "app"]
    description: str = Field(min_length=8)
    risk: Literal["R0", "R1", "R2", "R3"]
    access: Literal["read", "write"]
    idempotent: bool
    cancelable: bool
    max_duration_s: float = Field(gt=0)
    canonical_cli: list[str] = Field(min_length=1)
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    error_codes: list[str] = Field(min_length=1)
    capability_requirements: list[str] = Field(default_factory=list)
    preconditions: list[str] = Field(default_factory=list)
    postconditions: list[str] = Field(default_factory=list)
    semantic_units: dict[str, str] = Field(default_factory=dict)
    coordinate_frames: list[str] = Field(default_factory=list)
    time_semantics: str = "response observed_at uses UTC"
    side_effects: list[str] = Field(default_factory=list)
    resource_locks: list[str] = Field(default_factory=list)
    rate_limit: str = "on_demand"
    retry_policy: str = "none"
    compensation_operation: str | None = None

    @model_validator(mode="after")
    def validate_contract(self) -> OperationContract:
        if self.contract_id != self.operation:
            raise ValueError("contract_id must equal the canonical operation")
        if not _SEMVER.fullmatch(self.version):
            raise ValueError("contract version must be semantic version MAJOR.MINOR.PATCH")
        if self.access == "read" and self.risk != "R0":
            raise ValueError("read operations must be R0")
        if self.cancelable and self.access != "write":
            raise ValueError("only write operations may be cancelable")
        placeholders = {
            match
            for token in self.canonical_cli
            for match in _PLACEHOLDER.findall(token)
        }
        allowed_placeholders = _CONTEXT_PLACEHOLDERS | set(
            self.input_schema.get("properties", {})
        )
        if placeholders - allowed_placeholders:
            raise ValueError(f"unsupported canonical CLI placeholders: {sorted(placeholders)}")
        validate_schema_definition(self.input_schema, f"{self.operation} input")
        validate_schema_definition(self.output_schema, f"{self.operation} output")
        if not self.output_schema.get("properties"):
            raise ValueError("output schema must declare at least one property")
        return self

    @property
    def sha256(self) -> str:
        payload = json.dumps(
            self.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


class OperationContractCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-operation-contract-catalog/v1"] = (
        "robot-operation-contract-catalog/v1"
    )
    contracts: list[OperationContract]

    @model_validator(mode="after")
    def reject_duplicates(self) -> OperationContractCatalog:
        operations = [contract.operation for contract in self.contracts]
        if len(operations) != len(set(operations)):
            raise ValueError("operation contract catalog contains duplicates")
        return self

    @property
    def sha256(self) -> str:
        payload = json.dumps(
            {contract.operation: contract.sha256 for contract in self.contracts},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def by_operation(self) -> dict[str, OperationContract]:
        return {contract.operation: contract for contract in self.contracts}


def default_contract_root() -> Path:
    return Path(__file__).with_name("operation_contracts")


def load_operation_contracts(root: Path | None = None) -> OperationContractCatalog:
    contract_root = (root or default_contract_root()).resolve()
    contracts: list[OperationContract] = []
    for path in sorted(contract_root.glob("*.yaml")):
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("schema_version") != (
            "robot-operation-contract-set/v1"
        ):
            raise ValueError(f"invalid operation contract set: {path}")
        values = payload.get("contracts")
        if not isinstance(values, list):
            raise ValueError(f"operation contract set requires contracts: {path}")
        for index, value in enumerate(values):
            try:
                contracts.append(OperationContract.model_validate(value))
            except ValueError as exc:
                raise ValueError(f"invalid contract {path}:{index + 1}: {exc}") from exc
    if not contracts:
        raise ValueError(f"no operation contracts found under {contract_root}")
    return OperationContractCatalog(contracts=sorted(contracts, key=lambda item: item.operation))


def compatibility_issues(previous: OperationContract, current: OperationContract) -> list[str]:
    """Return conservative source-compatibility problems between contract versions."""
    issues: list[str] = []
    if previous.operation != current.operation:
        return ["operation identity changed"]
    previous_major = int(previous.version.split(".", 1)[0])
    current_major = int(current.version.split(".", 1)[0])
    if current_major < previous_major:
        issues.append("contract major version decreased")
    if previous.access != current.access or previous.risk != current.risk:
        issues.append("access or risk policy changed")
    old_input = previous.input_schema.get("properties", {})
    new_input = current.input_schema.get("properties", {})
    removed_input = sorted(set(old_input) - set(new_input))
    if removed_input:
        issues.append(f"input properties removed: {removed_input}")
    new_required = set(current.input_schema.get("required", [])) - set(
        previous.input_schema.get("required", [])
    )
    if new_required:
        issues.append(f"new required input properties: {sorted(new_required)}")
    old_output = previous.output_schema.get("properties", {})
    new_output = current.output_schema.get("properties", {})
    removed_output = sorted(set(old_output) - set(new_output))
    if removed_output:
        issues.append(f"output properties removed: {removed_output}")
    if issues and current_major <= previous_major:
        issues.append("breaking changes require a new major version")
    return issues


def render_canonical_cli(
    contract: OperationContract,
    *,
    robot_id: str,
    payload: dict[str, Any],
) -> list[str]:
    """Render a contract's argv template without shell interpolation."""
    validate_object(payload, contract.input_schema, f"{contract.operation} input")
    values: dict[str, Any] = {
        "operation": contract.operation,
        "robot_id": robot_id,
        "input_json": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        **payload,
    }
    rendered: list[str] = []
    for token in contract.canonical_cli:
        matches = _PLACEHOLDER.findall(token)
        missing = sorted({name for name in matches if name not in values})
        if missing:
            raise ValueError(f"missing canonical CLI values: {missing}")
        rendered.append(
            _PLACEHOLDER.sub(lambda match: str(values[match.group(1)]), token)
        )
    return rendered


def render_contract_catalog(catalog: OperationContractCatalog) -> str:
    lines = [
        "# Authored Operation Contracts",
        "",
        "This document is generated from `src/rolo/operation_contracts/*.yaml`. ",
        "`RELEASED` contracts back built-in operations; `GATEABLE` contracts may be ",
        "implemented and promoted by Adapt. The remaining product vocabulary stays `DRAFT` ",
        "and cannot become `VERIFIED` until an authored contract is added.",
        "",
        f"Catalog SHA-256: `{catalog.sha256}`",
        "",
        "| Operation | Lifecycle | Version | Contract SHA-256 |",
        "|---|---|---|---|",
    ]
    lines.extend(
        f"| `{contract.operation}` | {contract.lifecycle.value} | `{contract.version}` | "
        f"`{contract.sha256}` |"
        for contract in catalog.contracts
    )
    lines.append("")
    for contract in catalog.contracts:
        lines.extend(
            [
                f"## `{contract.operation}`",
                "",
                contract.description,
                "",
                f"- Lifecycle/version: `{contract.lifecycle.value}` / `{contract.version}`",
                f"- Layer/access/risk: `{contract.layer}` / `{contract.access}` / "
                f"`{contract.risk}`",
                f"- Idempotent/cancelable: `{str(contract.idempotent).lower()}` / "
                f"`{str(contract.cancelable).lower()}`",
                f"- Maximum duration: `{contract.max_duration_s:g}s`",
                f"- Canonical CLI template: `{' '.join(contract.canonical_cli)}`",
                f"- Error codes: `{', '.join(contract.error_codes)}`",
                f"- Contract SHA-256: `{contract.sha256}`",
                "",
                "Input schema:",
                "",
                "```json",
                json.dumps(contract.input_schema, ensure_ascii=False, indent=2),
                "```",
                "",
                "Output schema:",
                "",
                "```json",
                json.dumps(contract.output_schema, ensure_ascii=False, indent=2),
                "```",
                "",
            ]
        )
    return "\n".join(lines)
