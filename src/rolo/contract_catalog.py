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


class DataClassification(str, Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    SENSITIVE = "SENSITIVE"
    SECRET = "SECRET"


class ResultSemantics(str, Enum):
    OBSERVATION = "OBSERVATION"
    ACKNOWLEDGEMENT_ONLY = "ACKNOWLEDGEMENT_ONLY"
    SESSION_HANDLE = "SESSION_HANDLE"


class ObservationOverhead(str, Enum):
    NEGLIGIBLE = "NEGLIGIBLE"
    BOUNDED = "BOUNDED"
    ELEVATED = "ELEVATED"


class ExecutionMode(str, Enum):
    REQUEST_RESPONSE = "REQUEST_RESPONSE"
    BOUNDED_STREAM = "BOUNDED_STREAM"
    SESSION_START = "SESSION_START"
    SESSION_STOP = "SESSION_STOP"


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
    data_classification: DataClassification
    result_semantics: ResultSemantics = ResultSemantics.OBSERVATION
    observation_overhead: ObservationOverhead = ObservationOverhead.BOUNDED
    execution_mode: ExecutionMode = ExecutionMode.REQUEST_RESPONSE
    paired_operation: str | None = None
    replacement_operation: str | None = None
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
    requires_quiescence: bool = False

    @model_validator(mode="after")
    def validate_contract(self) -> OperationContract:
        if self.contract_id != self.operation:
            raise ValueError("contract_id must equal the canonical operation")
        if not _SEMVER.fullmatch(self.version):
            raise ValueError("contract version must be semantic version MAJOR.MINOR.PATCH")
        if self.data_classification == DataClassification.SECRET:
            raise ValueError("SECRET data cannot be exposed by a generic operation contract")
        if self.lifecycle == ContractLifecycle.DEPRECATED:
            if not self.replacement_operation or self.replacement_operation == self.operation:
                raise ValueError("deprecated contract requires a distinct replacement_operation")
        elif self.replacement_operation is not None:
            raise ValueError("only deprecated contracts may declare replacement_operation")
        if self.access == "read" and self.risk in {"R2", "R3"}:
            raise ValueError("read operations may only use R0 or R1 risk")
        if self.requires_quiescence and not (
            self.access == "write" and self.risk == "R2"
        ):
            raise ValueError("quiescence may only be required by R2 write operations")
        if self.requires_quiescence and self.max_duration_s > 115:
            raise ValueError(
                "quiescence-required operation duration must leave provider lease margin"
            )
        if self.access == "read" and self.risk == "R1":
            if self.observation_overhead != ObservationOverhead.ELEVATED:
                raise ValueError("R1 read operations require ELEVATED observation overhead")
            if not self.side_effects or self.rate_limit == "on_demand":
                raise ValueError("R1 read operations require side effects and a bounded rate limit")
        if self.access == "read" and self.risk == "R0" and (
            self.observation_overhead == ObservationOverhead.ELEVATED
        ):
            raise ValueError("ELEVATED observation overhead requires R1 risk")
        expected_result = (
            ResultSemantics.SESSION_HANDLE
            if self.execution_mode == ExecutionMode.SESSION_START
            else ResultSemantics.OBSERVATION
            if self.access == "read"
            else ResultSemantics.ACKNOWLEDGEMENT_ONLY
        )
        if self.result_semantics != expected_result:
            raise ValueError(
                f"{self.access} operations require {expected_result.value} result semantics"
            )
        if self.cancelable and self.access != "write" and (
            self.execution_mode != ExecutionMode.BOUNDED_STREAM
        ):
            raise ValueError("only writes and bounded streams may be cancelable")
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
        if self.access == "write" and "status" not in self.output_schema.get("required", []):
            raise ValueError("write operation output must require status acknowledgement")
        if self.risk == "R3":
            missing = [
                label
                for label, values in (
                    ("preconditions", self.preconditions),
                    ("postconditions", self.postconditions),
                    ("side_effects", self.side_effects),
                    ("resource_locks", self.resource_locks),
                )
                if not values
            ]
            if missing:
                raise ValueError(f"R3 operation lacks safety contract fields: {missing}")
        self._validate_execution_mode()
        return self

    def _validate_execution_mode(self) -> None:
        input_properties = self.input_schema.get("properties", {})
        input_required = set(self.input_schema.get("required", []))
        output_properties = self.output_schema.get("properties", {})
        output_required = set(self.output_schema.get("required", []))
        if self.execution_mode == ExecutionMode.REQUEST_RESPONSE:
            if self.paired_operation is not None:
                raise ValueError("request-response operation cannot declare paired_operation")
            return
        if self.execution_mode == ExecutionMode.BOUNDED_STREAM:
            if self.access != "read" or not self.cancelable:
                raise ValueError("bounded streams must be cancelable read operations")
            if self.risk != "R1" or self.observation_overhead != ObservationOverhead.ELEVATED:
                raise ValueError("bounded streams require R1 risk and ELEVATED overhead")
            required_bounds = {"duration_s", "max_items", "max_bytes"}
            if not required_bounds <= input_required:
                raise ValueError(
                    "bounded stream input must require duration_s, max_items, max_bytes"
                )
            for name in required_bounds:
                schema = input_properties.get(name, {})
                if schema.get("minimum", 0) <= 0 or schema.get("maximum") is None:
                    raise ValueError(f"bounded stream {name} requires positive minimum and maximum")
            if self.max_duration_s < input_properties["duration_s"]["maximum"]:
                raise ValueError("max_duration_s must cover the bounded stream duration maximum")
            required_output = {"status", "observed_at", "truncated"}
            if not required_output <= output_required or not (
                {"items", "artifact_ref"} & set(output_properties)
            ):
                raise ValueError(
                    "bounded stream output must expose bounds and items or artifact_ref"
                )
            if self.paired_operation is not None:
                raise ValueError("bounded stream cannot declare paired_operation")
            return
        if self.access != "write" or not self.paired_operation:
            raise ValueError("session control requires write access and paired_operation")
        if not self.side_effects or not self.resource_locks:
            raise ValueError("session control requires side effects and resource locks")
        if self.execution_mode == ExecutionMode.SESSION_START:
            required_bounds = {"ttl_s", "max_bytes"}
            if not required_bounds <= input_required:
                raise ValueError("session start input must require ttl_s and max_bytes")
            for name in required_bounds:
                schema = input_properties.get(name, {})
                if schema.get("minimum", 0) <= 0 or schema.get("maximum") is None:
                    raise ValueError(f"session start {name} requires positive minimum and maximum")
            if not {"status", "session_id", "expires_at"} <= output_required:
                raise ValueError("session start output must require status, session_id, expires_at")
        elif self.execution_mode == ExecutionMode.SESSION_STOP:
            if "session_id" not in input_required:
                raise ValueError("session stop input must require session_id")
            if not {"status", "session_id"} <= output_required:
                raise ValueError("session stop output must require status and session_id")

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
        by_operation = {contract.operation: contract for contract in self.contracts}
        for contract in self.contracts:
            if contract.replacement_operation is not None:
                replacement = by_operation.get(contract.replacement_operation)
                if replacement is None or replacement.lifecycle == ContractLifecycle.DEPRECATED:
                    raise ValueError(
                        f"active replacement contract is missing: {contract.operation}"
                    )
            if contract.compensation_operation is not None:
                compensation = by_operation.get(contract.compensation_operation)
                if (
                    compensation is None
                    or compensation.lifecycle == ContractLifecycle.DEPRECATED
                    or compensation.access != "write"
                ):
                    raise ValueError(
                        f"active write compensation contract is missing: {contract.operation}"
                    )
            if (
                contract.access == "write"
                and contract.cancelable
                and contract.compensation_operation is None
            ):
                raise ValueError(
                    f"cancelable write contract lacks compensation: {contract.operation}"
                )
            if contract.paired_operation is None:
                continue
            paired = by_operation.get(contract.paired_operation)
            if paired is None:
                raise ValueError(f"paired operation contract is missing: {contract.operation}")
            expected_mode = (
                ExecutionMode.SESSION_STOP
                if contract.execution_mode == ExecutionMode.SESSION_START
                else ExecutionMode.SESSION_START
            )
            if (
                paired.execution_mode != expected_mode
                or paired.paired_operation != contract.operation
            ):
                raise ValueError(f"session operation pair is not reciprocal: {contract.operation}")
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
    if previous.result_semantics != current.result_semantics:
        issues.append("result semantics changed")
    if previous.observation_overhead != current.observation_overhead:
        issues.append("observation overhead changed")
    if (
        previous.execution_mode != current.execution_mode
        or previous.paired_operation != current.paired_operation
    ):
        issues.append("execution mode or session pairing changed")
    classification_rank = {
        DataClassification.PUBLIC: 0,
        DataClassification.INTERNAL: 1,
        DataClassification.SENSITIVE: 2,
        DataClassification.SECRET: 3,
    }
    if classification_rank[current.data_classification] < classification_rank[
        previous.data_classification
    ]:
        issues.append("data classification was weakened")
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
        "| Operation | Lifecycle | Version | Data | Contract SHA-256 |",
        "|---|---|---|---|---|",
    ]
    lines.extend(
        f"| `{contract.operation}` | {contract.lifecycle.value} | `{contract.version}` | "
        f"`{contract.data_classification.value}` | "
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
                f"- Data classification: `{contract.data_classification.value}`",
                f"- Result semantics: `{contract.result_semantics.value}`",
                f"- Observation overhead: `{contract.observation_overhead.value}`",
                f"- Execution mode: `{contract.execution_mode.value}`",
                f"- Paired operation: `{contract.paired_operation or 'none'}`",
                f"- Replacement operation: `{contract.replacement_operation or 'none'}`",
                f"- Idempotent/cancelable: `{str(contract.idempotent).lower()}` / "
                f"`{str(contract.cancelable).lower()}`",
                f"- Requires execution quiescence: "
                f"`{str(contract.requires_quiescence).lower()}`",
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
