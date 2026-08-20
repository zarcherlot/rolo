from __future__ import annotations

from datetime import datetime
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from rolo.adapter_runtime import load_current_release
from rolo.core.models import DiscoveryReport, RobotCapability, ToolDescriptor, utc_now
from rolo.stages.adapt.discovery import load_latest_report
from rolo.stages.adapt.operation_registry import (
    CanonicalOperationDefinition,
    builtin_operations,
    canonical_operation_registry,
)
from rolo.workbench_read_models import build_robot_topology


class CapabilityLayer(str, Enum):
    HARDWARE = "Hardware"
    LINUX = "Linux"
    MIDDLEWARE = "Middleware"
    APPLICATION = "Application"


class CapabilityApplicability(str, Enum):
    APPLICABLE = "APPLICABLE"
    NOT_OBSERVED = "NOT_OBSERVED"
    UNKNOWN = "UNKNOWN"


class CapabilityAvailability(str, Enum):
    VERIFIED = "VERIFIED"
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


class CapabilityRegistration(str, Enum):
    BUILTIN = "BUILTIN"
    REGISTERED = "REGISTERED"
    NOT_REGISTERED = "NOT_REGISTERED"
    STALE = "STALE"


class CapabilityBinding(BaseModel):
    schema_version: Literal["rolo-capability-binding/v1"] = "rolo-capability-binding/v1"
    binding_id: str
    source: Literal["gated_release", "discovery_candidate"]
    authority: Literal["GATED", "OBSERVED", "DECLARED"]
    kind: str
    endpoint: str
    interface_type: str | None = None
    adapter: str | None = None
    observed_at: datetime | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    reference_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    limitations: list[str] = Field(default_factory=list)


class CapabilitySummary(BaseModel):
    schema_version: Literal["rolo-capability-summary/v1"] = "rolo-capability-summary/v1"
    operation: str
    layer: CapabilityLayer
    description: str
    lifecycle: Literal["DRAFT", "GATEABLE", "RELEASED", "DEPRECATED"]
    applicability: CapabilityApplicability
    availability: CapabilityAvailability
    registration: CapabilityRegistration
    access: Literal["read", "write"]
    risk: Literal["R0", "R1", "R2", "R3"]
    data_classification: Literal["PUBLIC", "INTERNAL", "SENSITIVE", "SECRET"]
    contract_version: str
    contract_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    paired_operation: str | None = None
    replacement_operation: str | None = None
    compensation_operation: str | None = None
    binding_count: int = Field(ge=0)
    last_verified_at: datetime | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    integrity_status: Literal["validated", "verified"]
    limitations: list[str] = Field(default_factory=list)


class CapabilityCollection(BaseModel):
    schema_version: Literal["rolo-capability-collection/v1"] = (
        "rolo-capability-collection/v1"
    )
    robot_id: str
    items: list[CapabilitySummary]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    next_offset: int | None = Field(default=None, ge=0)
    observed_at: datetime
    freshness: Literal["fresh", "unknown"]
    source_kind: Literal["product_registry", "discovery", "gated_release"]
    limitations: list[str] = Field(default_factory=list)


class CapabilityContract(BaseModel):
    schema_version: Literal["rolo-capability-contract/v1"] = "rolo-capability-contract/v1"
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    capability_requirements: list[str]
    preconditions: list[str]
    postconditions: list[str]
    semantic_units: dict[str, str]
    coordinate_frames: list[str]
    time_semantics: str
    result_semantics: str
    execution_mode: str
    idempotent: bool
    cancelable: bool
    max_duration_s: float
    side_effects: list[str]
    resource_locks: list[str]
    requires_quiescence: bool


class CapabilityDetail(BaseModel):
    schema_version: Literal["rolo-capability-detail/v1"] = "rolo-capability-detail/v1"
    robot_id: str
    capability: CapabilitySummary
    contract: CapabilityContract
    bindings: list[CapabilityBinding]
    observed_at: datetime
    freshness: Literal["fresh", "unknown"]


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _stable_id(prefix: str, value: str) -> str:
    return f"{prefix}_{_digest(value)[:18]}"


def _layer(value: str) -> CapabilityLayer:
    if value == "hw":
        return CapabilityLayer.HARDWARE
    if value == "linux":
        return CapabilityLayer.LINUX
    if value in {"middleware", "ros"}:
        return CapabilityLayer.MIDDLEWARE
    return CapabilityLayer.APPLICATION


def _optional_discovery(artifact_root: Path, robot_id: str) -> DiscoveryReport | None:
    try:
        return load_latest_report(artifact_root, robot_id)
    except FileNotFoundError:
        return None


def _release_context(
    output_root: Path, robot_id: str
) -> tuple[datetime | None, str | None, dict[str, ToolDescriptor]]:
    try:
        _, release, _, catalog = load_current_release(output_root, robot_id)
    except FileNotFoundError:
        return None, None, {}
    return release.published_at, release.discovery_id, {
        item.operation: item for item in catalog.tools
    }


def _operation_evidence(robot: RobotCapability, output_root: Path) -> dict[str, list[str]]:
    topology, _ = build_robot_topology(robot, output_root)
    evidence: dict[str, set[str]] = {}
    for node in topology.nodes:
        operation = node.attributes.get("operation")
        if isinstance(operation, str):
            evidence.setdefault(operation, set()).update(node.evidence_ids)
    return {operation: sorted(ids) for operation, ids in evidence.items()}


def _availability(value: str | None) -> CapabilityAvailability:
    if value == "VERIFIED":
        return CapabilityAvailability.VERIFIED
    if value == "AVAILABLE":
        return CapabilityAvailability.AVAILABLE
    if value in {"UNAVAILABLE", "BLOCKED"}:
        return CapabilityAvailability.UNAVAILABLE
    return CapabilityAvailability.UNKNOWN


def _summary(
    definition: CanonicalOperationDefinition,
    *,
    builtins: set[str],
    discovery: DiscoveryReport | None,
    release_discovery_id: str | None,
    active: ToolDescriptor | None,
    published_at: datetime | None,
    evidence_ids: list[str],
) -> CapabilitySummary:
    candidate = next(
        (
            item
            for item in (discovery.operation_candidates if discovery else [])
            if item.operation == definition.operation
        ),
        None,
    )
    release_matches = bool(
        discovery and release_discovery_id and discovery.discovery_id == release_discovery_id
    )
    if definition.operation in builtins:
        registration = CapabilityRegistration.BUILTIN
        availability = CapabilityAvailability.AVAILABLE
    elif active is not None and (discovery is None or release_matches):
        registration = CapabilityRegistration.REGISTERED
        availability = _availability(active.availability)
    elif active is not None:
        registration = CapabilityRegistration.STALE
        availability = CapabilityAvailability.UNAVAILABLE
    else:
        registration = CapabilityRegistration.NOT_REGISTERED
        availability = CapabilityAvailability.UNAVAILABLE

    if definition.operation in builtins or candidate is not None or active is not None:
        applicability = CapabilityApplicability.APPLICABLE
    elif discovery is None:
        applicability = CapabilityApplicability.UNKNOWN
    else:
        applicability = CapabilityApplicability.NOT_OBSERVED

    verified = active is not None and registration is CapabilityRegistration.REGISTERED
    binding_count = len(candidate.route_evidence) if candidate else 0
    if active is not None:
        binding_count = max(binding_count, len(active.semantic_bindings), 1)
    limitations: list[str] = []
    if discovery is None and active is None:
        limitations.append("No discovery snapshot is available; applicability is unknown.")
    elif candidate is None and definition.operation not in builtins:
        limitations.append("The latest discovery did not observe an applicable binding.")
    if registration is CapabilityRegistration.STALE:
        limitations.append("The active release belongs to a different discovery snapshot.")
    if registration is CapabilityRegistration.NOT_REGISTERED:
        limitations.append("No gated adapter binding is registered for this operation.")
    if registration is CapabilityRegistration.BUILTIN:
        limitations.append("Built-in availability does not prove a successful physical outcome.")
    return CapabilitySummary(
        operation=definition.operation,
        layer=_layer(definition.layer),
        description=definition.description,
        lifecycle=definition.contract_lifecycle.value,
        applicability=applicability,
        availability=availability,
        registration=registration,
        access=definition.access,
        risk=definition.risk,
        data_classification=(
            definition.data_classification.value
            if definition.data_classification
            else "INTERNAL"
        ),
        contract_version=definition.contract_version or "0.0.0",
        contract_digest=definition.contract_sha256 or _digest(definition.operation),
        paired_operation=definition.paired_operation,
        replacement_operation=definition.replacement_operation,
        compensation_operation=definition.compensation_operation,
        binding_count=binding_count,
        last_verified_at=published_at if verified else None,
        evidence_ids=evidence_ids,
        confidence=1.0 if verified else (0.9 if definition.operation in builtins else 0.5),
        integrity_status="verified" if verified else "validated",
        limitations=limitations,
    )


def _context(
    robot: RobotCapability,
    artifact_root: Path,
    output_root: Path,
) -> tuple[
    list[CanonicalOperationDefinition],
    set[str],
    DiscoveryReport | None,
    datetime | None,
    str | None,
    dict[str, ToolDescriptor],
    dict[str, list[str]],
]:
    registry = canonical_operation_registry()
    return (
        registry.operations,
        builtin_operations(),
        _optional_discovery(artifact_root, robot.robot_id),
        *_release_context(output_root, robot.robot_id),
        _operation_evidence(robot, output_root),
    )


def build_capability_collection(
    robot: RobotCapability,
    artifact_root: Path,
    output_root: Path,
    *,
    limit: int = 50,
    offset: int = 0,
    query: str | None = None,
    layer: CapabilityLayer | None = None,
    lifecycle: str | None = None,
    risk: str | None = None,
    availability: CapabilityAvailability | None = None,
    observed_at: datetime | None = None,
) -> CapabilityCollection:
    context = _context(robot, artifact_root, output_root)
    definitions, builtins, discovery, published_at, release_discovery_id, active, evidence = (
        context
    )
    items = [
        _summary(
            definition,
            builtins=builtins,
            discovery=discovery,
            release_discovery_id=release_discovery_id,
            active=active.get(definition.operation),
            published_at=published_at,
            evidence_ids=evidence.get(definition.operation, []),
        )
        for definition in definitions
    ]
    if query:
        needle = query.casefold().strip()
        items = [
            item
            for item in items
            if needle in item.operation.casefold() or needle in item.description.casefold()
        ]
    if layer is not None:
        items = [item for item in items if item.layer is layer]
    if lifecycle:
        items = [item for item in items if item.lifecycle == lifecycle]
    if risk:
        items = [item for item in items if item.risk == risk]
    if availability is not None:
        items = [item for item in items if item.availability is availability]
    items.sort(key=lambda item: (item.layer.value, item.operation))
    total = len(items)
    source_kind: Literal["product_registry", "discovery", "gated_release"]
    if active:
        source_kind = "gated_release"
    elif discovery:
        source_kind = "discovery"
    else:
        source_kind = "product_registry"
    limitations = []
    if discovery is None and not active:
        limitations.append("Applicability is unknown until an Adapt discovery snapshot exists.")
    if not active:
        limitations.append(
            "Availability is limited to built-in operations until a gated release exists."
        )
    return CapabilityCollection(
        robot_id=robot.robot_id,
        items=items[offset : offset + limit],
        total=total,
        limit=limit,
        offset=offset,
        next_offset=(offset + limit if offset + limit < total else None),
        observed_at=observed_at or utc_now(),
        freshness="unknown" if published_at else "fresh",
        source_kind=source_kind,
        limitations=limitations,
    )


def get_capability_detail(
    robot: RobotCapability,
    artifact_root: Path,
    output_root: Path,
    operation: str,
    *,
    observed_at: datetime | None = None,
) -> CapabilityDetail | None:
    context = _context(robot, artifact_root, output_root)
    definitions, builtins, discovery, published_at, release_discovery_id, active, evidence = (
        context
    )
    definition = next((item for item in definitions if item.operation == operation), None)
    if definition is None:
        return None
    descriptor = active.get(operation)
    summary = _summary(
        definition,
        builtins=builtins,
        discovery=discovery,
        release_discovery_id=release_discovery_id,
        active=descriptor,
        published_at=published_at,
        evidence_ids=evidence.get(operation, []),
    )
    candidate = next(
        (
            item
            for item in (discovery.operation_candidates if discovery else [])
            if item.operation == operation
        ),
        None,
    )
    bindings: list[CapabilityBinding] = []
    if descriptor is not None:
        semantic_bindings = descriptor.semantic_bindings or [descriptor.adapter]
        for value in semantic_bindings:
            bindings.append(
                CapabilityBinding(
                    binding_id=_stable_id(
                        "binding", f"{robot.robot_id}\0{operation}\0gated\0{value}"
                    ),
                    source="gated_release",
                    authority="GATED",
                    kind="adapter_binding",
                    endpoint=value,
                    adapter=descriptor.adapter,
                    observed_at=published_at,
                    evidence_ids=summary.evidence_ids,
                    reference_digest=_digest(value),
                    limitations=[
                        "A gated binding does not prove physical task outcome correctness."
                    ],
                )
            )
    if candidate is not None:
        for route in candidate.route_evidence:
            bindings.append(
                CapabilityBinding(
                    binding_id=_stable_id(
                        "binding", f"{robot.robot_id}\0{operation}\0{route.resource_id}"
                    ),
                    source="discovery_candidate",
                    authority="OBSERVED" if route.observed else "DECLARED",
                    kind=route.kind,
                    endpoint=route.endpoint,
                    interface_type=route.interface_type,
                    observed_at=route.observed_at,
                    evidence_ids=[],
                    reference_digest=_digest(route.source),
                    limitations=[
                        *route.limitations,
                        "Discovery evidence is not a gated adapter binding.",
                    ],
                )
            )
    return CapabilityDetail(
        robot_id=robot.robot_id,
        capability=summary,
        contract=CapabilityContract(
            input_schema=definition.input_schema,
            output_schema=definition.output_schema,
            capability_requirements=definition.capability_requirements,
            preconditions=definition.preconditions,
            postconditions=definition.postconditions,
            semantic_units=definition.semantic_units,
            coordinate_frames=definition.coordinate_frames,
            time_semantics=definition.time_semantics,
            result_semantics=(
                definition.result_semantics.value
                if definition.result_semantics
                else "OBSERVATION"
            ),
            execution_mode=definition.execution_mode.value,
            idempotent=definition.idempotent,
            cancelable=definition.cancelable,
            max_duration_s=definition.max_duration_s,
            side_effects=definition.side_effects,
            resource_locks=definition.resource_locks,
            requires_quiescence=definition.requires_quiescence,
        ),
        bindings=bindings,
        observed_at=observed_at or utc_now(),
        freshness="unknown" if published_at else "fresh",
    )
