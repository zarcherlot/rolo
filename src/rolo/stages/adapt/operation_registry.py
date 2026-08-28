from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from rolo.contract_catalog import (
    ContractLifecycle,
    DataClassification,
    ExecutionMode,
    ObservationOverhead,
    ResultSemantics,
    load_operation_contracts,
)
from rolo.core.models import DiscoveryReport, OperationCandidate, ToolDescriptor
from rolo.schema_subset import validate_schema_definition
from rolo.stages.adapt.models import AdapterBundleManifest, ToolCatalog
from rolo.stages.adapt.routes import (
    candidate_routes_fully_observed,
    candidate_runtime_evidence_complete,
)


class CanonicalOperationDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: str
    layer: Literal["control", "hw", "linux", "middleware", "ros", "app"]
    description: str
    risk: str
    access: str
    idempotent: bool
    cancelable: bool
    max_duration_s: float
    canonical_cli: list[str]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    error_codes: list[str]
    contract_lifecycle: ContractLifecycle
    contract_version: str
    contract_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    data_classification: DataClassification
    result_semantics: ResultSemantics
    observation_overhead: ObservationOverhead
    execution_mode: ExecutionMode
    paired_operation: str | None
    replacement_operation: str | None
    capability_requirements: list[str]
    preconditions: list[str]
    postconditions: list[str]
    semantic_units: dict[str, str]
    coordinate_frames: list[str]
    time_semantics: str
    side_effects: list[str]
    resource_locks: list[str]
    rate_limit: str
    retry_policy: str
    compensation_operation: str | None
    requires_quiescence: bool


class CanonicalOperationRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-canonical-operation-registry/v1"] = (
        "robot-canonical-operation-registry/v1"
    )
    contract_catalog_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    operations: list[CanonicalOperationDefinition]


_GROUPS: dict[str, tuple[str, ...]] = {
    "control": (
        "tool.catalog",
        "tool.schema",
        "runtime.health",
        "runtime.version",
        "state.graph.snapshot",
        "state.graph.query",
        "evidence.resolve",
        "episode.list",
        "episode.inspect",
        "episode.export",
        "checkpoint.list",
        "checkpoint.create",
        "checkpoint.restore",
    ),
    "hw": (
        "hw.inventory.scan",
        "hw.compute.list",
        "hw.compute.inspect",
        "hw.compute.status",
        "hw.clock.status",
        "hw.thermal.status",
        "hw.storage.status",
        "hw.sensor.list",
        "hw.sensor.inspect",
        "hw.sensor.status",
        "hw.sensor.read",
        "hw.sensor.calibrate",
        "hw.sensor.reset",
        "hw.actuator.list",
        "hw.actuator.inspect",
        "hw.actuator.status",
        "hw.actuator.command",
        "hw.actuator.stop",
        "hw.actuator.enable",
        "hw.actuator.disable",
        "hw.actuator.calibrate",
        "hw.actuator.reset",
        "hw.bus.list",
        "hw.bus.inspect",
        "hw.bus.status",
        "hw.bus.scan",
        "hw.bus.statistics",
        "hw.bus.reset",
        "hw.firmware.list",
        "hw.firmware.inspect",
        "hw.firmware.verify",
        "hw.firmware.update",
        "hw.firmware.rollback",
        "hw.power.status",
        "hw.power.battery.status",
        "hw.power.rail.list",
        "hw.power.rail.inspect",
        "hw.power.rail.enable",
        "hw.power.rail.disable",
        "hw.power.cycle",
    ),
    "linux": (
        "linux.host.inventory",
        "linux.host.status",
        "linux.host.uptime",
        "linux.host.reboot",
        "linux.host.shutdown",
        "linux.process.list",
        "linux.process.inspect",
        "linux.process.start",
        "linux.process.stop",
        "linux.process.restart",
        "linux.process.signal",
        "linux.process.logs",
        "linux.process.resources",
        "linux.service.list",
        "linux.service.inspect",
        "linux.service.start",
        "linux.service.stop",
        "linux.service.restart",
        "linux.service.enable",
        "linux.service.disable",
        "linux.service.logs",
        "linux.container.list",
        "linux.container.inspect",
        "linux.container.start",
        "linux.container.stop",
        "linux.container.restart",
        "linux.container.logs",
        "linux.container.stats",
        "linux.schedule.list",
        "linux.schedule.inspect",
        "linux.schedule.enable",
        "linux.schedule.disable",
        "linux.schedule.run",
        "linux.binary.describe",
        "linux.binary.verify",
        "linux.cli.probe",
        "linux.package.inspect",
        "linux.package.verify",
        "linux.config.locate",
        "linux.config.inspect",
        "linux.config.validate",
        "linux.config.diff",
        "linux.config.apply",
        "linux.config.rollback",
        "linux.file.inspect",
        "linux.file.read",
        "linux.file.hash",
        "linux.file.list",
        "linux.network.interfaces",
        "linux.network.listeners",
        "linux.network.routes",
        "linux.network.connections",
        "linux.network.statistics",
        "linux.network.dns",
        "linux.resource.snapshot",
        "linux.resource.cpu",
        "linux.resource.memory",
        "linux.resource.disk",
        "linux.resource.gpu",
        "linux.log.query",
        "linux.log.follow",
        "linux.time.status",
        "linux.time.synchronize",
    ),
    "middleware": (
        "middleware.inspect",
        "middleware.status",
        "middleware.graph.snapshot",
    ),
    "ros": (
        "ros.graph.snapshot",
        "ros.node.list",
        "ros.node.status",
        "ros.node.inspect",
        "ros.node.lifecycle",
        "ros.node.activate",
        "ros.node.deactivate",
        "ros.topic.list",
        "ros.topic.describe",
        "ros.topic.sample",
        "ros.topic.rate",
        "ros.topic.bandwidth",
        "ros.topic.publish",
        "ros.service.list",
        "ros.service.describe",
        "ros.service.call",
        "ros.action.list",
        "ros.action.describe",
        "ros.action.send",
        "ros.action.status",
        "ros.action.cancel",
        "ros.tf.tree",
        "ros.tf.snapshot",
        "ros.tf.lookup",
        "ros.tf.monitor",
        "ros.parameter.list",
        "ros.parameter.get",
        "ros.parameter.describe",
        "ros.parameter.set",
        "ros.parameter.dump",
        "ros.parameter.load",
        "ros.parameter.rollback",
        "ros.diagnostics.snapshot",
        "ros.diagnostics.watch",
        "ros.clock.status",
        "ros.bag.inspect",
        "ros.bag.record",
        "ros.bag.play",
    ),
    "app": (
        "app.robot.discover",
        "app.robot.status",
        "app.robot.start",
        "app.robot.stop",
        "app.robot.restart",
        "app.robot.health",
        "app.camera.list",
        "app.camera.status",
        "app.camera.inspect",
        "app.camera.snapshot",
        "app.camera.stream.start",
        "app.camera.stream.stop",
        "app.camera.calibration.status",
        "app.lidar.list",
        "app.lidar.status",
        "app.lidar.inspect",
        "app.lidar.snapshot",
        "app.lidar.calibration.status",
        "app.imu.list",
        "app.imu.status",
        "app.imu.inspect",
        "app.imu.sample",
        "app.imu.calibration.status",
        "app.gnss.list",
        "app.gnss.status",
        "app.gnss.inspect",
        "app.gnss.sample",
        "app.odometry.status",
        "app.odometry.sample",
        "app.odometry.reset",
        "app.teleop.velocity",
        "app.teleop.pose",
        "app.teleop.joint",
        "app.teleop.stop",
        "app.base.status",
        "app.base.velocity",
        "app.base.move_distance",
        "app.base.rotate",
        "app.base.stop",
        "app.base.recover",
        "app.manipulation.status",
        "app.manipulation.plan",
        "app.manipulation.execute",
        "app.manipulation.cancel",
        "app.manipulation.stop",
        "app.manipulation.home",
        "app.gripper.status",
        "app.gripper.open",
        "app.gripper.close",
        "app.gripper.set",
        "app.gripper.stop",
        "app.localization.status",
        "app.localization.pose",
        "app.localization.initialize",
        "app.localization.reset",
        "app.localization.relocalize",
        "app.localization.quality",
        "app.map.list",
        "app.map.inspect",
        "app.map.create",
        "app.map.save",
        "app.map.load",
        "app.map.clear",
        "app.map.export",
        "app.map.import",
        "app.navigation.status",
        "app.navigation.plan",
        "app.navigation.start",
        "app.navigation.pause",
        "app.navigation.resume",
        "app.navigation.cancel",
        "app.navigation.stop",
        "app.navigation.recover",
        "app.navigation.costmap.inspect",
        "app.navigation.path.inspect",
        "app.calibration.list",
        "app.calibration.inspect",
        "app.calibration.status",
        "app.calibration.run",
        "app.calibration.validate",
        "app.calibration.apply",
        "app.calibration.rollback",
        "app.safety.status",
        "app.safety.limits.inspect",
        "app.safety.zones.inspect",
        "app.safety.interlocks.inspect",
        "app.safety.approval.status",
        "app.safety.emergency_stop",
        "app.safety.protective_stop",
        "app.safety.stop.clear",
        "app.task.list",
        "app.task.describe",
        "app.task.start",
        "app.task.status",
        "app.task.pause",
        "app.task.resume",
        "app.task.cancel",
        "app.task.stop",
        "app.task.result",
        "app.test.list",
        "app.test.describe",
        "app.test.plan",
        "app.test.run",
        "app.test.status",
        "app.test.cancel",
        "app.test.result",
        "app.test.evidence",
        "app.regression.plan",
        "app.regression.run",
        "app.regression.cancel",
        "app.regression.status",
        "app.regression.result",
        "app.diagnosis.snapshot",
        "app.diagnosis.run",
        "app.diagnosis.status",
        "app.diagnosis.cancel",
        "app.diagnosis.result",
        "app.diagnosis.evidence",
        "app.parameter.list",
        "app.parameter.inspect",
        "app.parameter.get",
        "app.parameter.set",
        "app.parameter.validate",
        "app.parameter.rollback",
        "app.tuning.baseline.create",
        "app.tuning.candidate.create",
        "app.tuning.candidate.evaluate",
        "app.tuning.status",
        "app.tuning.commit",
        "app.tuning.rollback",
        "app.state.snapshot",
        "app.state.watch",
        "app.event.list",
        "app.event.inspect",
        "app.telemetry.snapshot",
        "app.telemetry.watch",
        "app.telemetry.export",
    ),
}

_BUILTIN_CLI: dict[str, str] = {
    "tool.schema": "robotctl tool schema OPERATION --robot ROBOT_ID",
    "runtime.health": "robotctl runtime health",
    "runtime.version": "robotctl runtime version",
    "state.graph.snapshot": "robotctl state graph snapshot --robot ROBOT_ID",
    "state.graph.query": "robotctl state graph query QUERY --robot ROBOT_ID",
    "evidence.resolve": "robotctl adapt evidence resolve REFERENCE --robot ROBOT_ID",
    "hw.inventory.scan": "robotctl hw inventory scan",
    "linux.host.inventory": "robotctl linux host inventory",
    "linux.host.status": "robotctl linux host status",
    "linux.host.uptime": "robotctl linux host uptime",
    "linux.service.list": "robotctl linux service list",
    "linux.service.inspect": "robotctl linux service inspect NAME",
    "linux.container.list": "robotctl linux container list",
    "linux.container.inspect": "robotctl linux container inspect NAME",
    "linux.container.stats": "robotctl linux container stats",
    "linux.schedule.list": "robotctl linux schedule list",
    "linux.schedule.inspect": "robotctl linux schedule inspect NAME",
    "linux.process.list": "robotctl linux process list",
    "linux.process.inspect": "robotctl linux process inspect PID",
    "linux.process.resources": "robotctl linux process resources PID",
    "linux.binary.describe": "robotctl linux binary describe PATH",
    "linux.binary.verify": "robotctl linux binary verify PATH --expected-sha256 SHA256",
    "linux.package.inspect": "robotctl linux package inspect NAME",
    "linux.package.verify": "robotctl linux package verify NAME",
    "linux.cli.probe": "robotctl linux cli probe PATH --arg=--help",
    "linux.config.locate": "robotctl linux config locate --process PID",
    "linux.file.inspect": "robotctl linux file inspect PATH",
    "linux.file.hash": "robotctl linux file hash PATH",
    "linux.file.list": "robotctl linux file list PATH",
    "linux.network.interfaces": "robotctl linux network interfaces",
    "linux.network.listeners": "robotctl linux network listeners",
    "linux.network.routes": "robotctl linux network routes",
    "linux.network.connections": "robotctl linux network connections",
    "linux.network.statistics": "robotctl linux network statistics",
    "linux.network.dns": "robotctl linux network dns",
    "linux.resource.snapshot": "robotctl linux resource snapshot",
    "linux.resource.cpu": "robotctl linux resource cpu",
    "linux.resource.memory": "robotctl linux resource memory",
    "linux.resource.disk": "robotctl linux resource disk",
    "linux.resource.gpu": "robotctl linux resource gpu",
    "linux.time.status": "robotctl linux time status",
    "middleware.inspect": "robotctl middleware inspect",
    "middleware.status": "robotctl middleware status",
    "middleware.graph.snapshot": "robotctl middleware graph snapshot",
    "ros.node.status": "robotctl ros node status NAME",
    "ros.node.list": "robotctl ros node list",
    "ros.node.inspect": "robotctl ros node inspect NAME",
    "ros.node.lifecycle": "robotctl ros node lifecycle NAME",
    "ros.topic.list": "robotctl ros topic list",
    "ros.topic.describe": "robotctl ros topic describe NAME",
    "ros.service.list": "robotctl ros service list",
    "ros.service.describe": "robotctl ros service describe NAME",
    "ros.action.list": "robotctl ros action list",
    "ros.action.describe": "robotctl ros action describe NAME",
    "ros.parameter.list": "robotctl ros parameter list",
    "ros.parameter.get": "robotctl ros parameter get NAME --node NODE",
    "ros.parameter.describe": "robotctl ros parameter describe NAME --node NODE",
    "ros.clock.status": "robotctl ros clock status",
    "ros.bag.inspect": "robotctl ros bag inspect PATH",
    "ros.graph.snapshot": "robotctl ros graph snapshot",
    "app.robot.discover": "robotctl app robot discover",
    "tool.catalog": "robotctl tool catalog --robot ROBOT_ID",
}


def canonical_operation_registry() -> CanonicalOperationRegistry:
    catalog = load_operation_contracts()
    contracts = {contract.operation: contract for contract in catalog.contracts}
    vocabulary = {operation for operations in _GROUPS.values() for operation in operations}
    unknown_contracts = sorted(set(contracts) - vocabulary)
    if unknown_contracts:
        raise RuntimeError(f"contracts are outside the product vocabulary: {unknown_contracts}")
    missing_contracts = sorted(vocabulary - set(contracts))
    if missing_contracts:
        raise RuntimeError(f"product operations lack explicit contracts: {missing_contracts}")
    definitions: list[CanonicalOperationDefinition] = []
    for layer, operations in _GROUPS.items():
        for operation in operations:
            contract = contracts[operation]
            if contract.layer != layer:
                raise RuntimeError(f"contract layer mismatch: {operation}")
            definitions.append(
                CanonicalOperationDefinition(
                    operation=operation,
                    layer=layer,  # type: ignore[arg-type]
                    description=contract.description,
                    risk=contract.risk,
                    access=contract.access,
                    idempotent=contract.idempotent,
                    cancelable=contract.cancelable,
                    max_duration_s=contract.max_duration_s,
                    canonical_cli=contract.canonical_cli,
                    input_schema=contract.input_schema,
                    output_schema=contract.output_schema,
                    error_codes=contract.error_codes,
                    contract_lifecycle=contract.lifecycle,
                    contract_version=contract.version,
                    contract_sha256=contract.sha256,
                    data_classification=contract.data_classification,
                    result_semantics=contract.result_semantics,
                    observation_overhead=contract.observation_overhead,
                    execution_mode=contract.execution_mode,
                    paired_operation=contract.paired_operation,
                    replacement_operation=contract.replacement_operation,
                    capability_requirements=contract.capability_requirements,
                    preconditions=contract.preconditions,
                    postconditions=contract.postconditions,
                    semantic_units=contract.semantic_units,
                    coordinate_frames=contract.coordinate_frames,
                    time_semantics=contract.time_semantics,
                    side_effects=contract.side_effects,
                    resource_locks=contract.resource_locks,
                    rate_limit=contract.rate_limit,
                    retry_policy=contract.retry_policy,
                    compensation_operation=contract.compensation_operation,
                    requires_quiescence=contract.requires_quiescence,
                )
            )
    if len({item.operation for item in definitions}) != len(definitions):
        raise RuntimeError("canonical operation registry contains duplicates")
    return CanonicalOperationRegistry(
        contract_catalog_sha256=catalog.sha256,
        operations=definitions,
    )


def builtin_operations() -> set[str]:
    return set(_BUILTIN_CLI)


def required_adapter_agent_conformance_operations(report: DiscoveryReport) -> set[str]:
    """Operations owned by the generated bundle and therefore reported by its Agent."""
    eligible, _ = adapter_operation_eligibility(report)
    return eligible


def adapter_operation_eligibility(
    report: DiscoveryReport,
) -> tuple[set[str], dict[str, str]]:
    """Split candidates into independently gateable and evidence-only operations."""
    definitions = {item.operation: item for item in canonical_operation_registry().operations}
    eligible: set[str] = set()
    deferred: dict[str, str] = {}
    for candidate in report.operation_candidates:
        definition = definitions[candidate.operation]
        if candidate.origin == "HEURISTIC_AGENT":
            deferred[candidate.operation] = "HEURISTIC_MAPPING_REQUIRES_VERIFICATION"
        elif definition.contract_lifecycle not in {
            ContractLifecycle.GATEABLE,
            ContractLifecycle.RELEASED,
        }:
            deferred[candidate.operation] = "PRODUCT_CONTRACT_NOT_GATEABLE"
        elif not candidate.route_evidence:
            deferred[candidate.operation] = "TARGET_ROUTE_NOT_DECLARED"
        elif any(
            "Heuristic mapping is ambiguous" in limitation for limitation in candidate.limitations
        ):
            deferred[candidate.operation] = "HEURISTIC_MAPPING_AMBIGUOUS"
        elif not candidate_routes_fully_observed(candidate, report.probes):
            deferred[candidate.operation] = "TARGET_ROUTE_NOT_OBSERVED"
        elif not candidate_runtime_evidence_complete(candidate, report.probes):
            deferred[candidate.operation] = "TARGET_ROUTE_IDENTITY_INCOMPLETE"
        else:
            eligible.add(candidate.operation)
    return eligible, deferred


def required_builtin_conformance_operations() -> set[str]:
    """Operations whose implementation and conformance are owned by Rolo itself."""
    return builtin_operations()


def required_conformance_operations(report: DiscoveryReport) -> set[str]:
    """Complete gate surface; callers must preserve the two ownership domains."""
    return (
        required_builtin_conformance_operations()
        | required_adapter_agent_conformance_operations(report)
    )


def validate_definition_contract(definition: CanonicalOperationDefinition) -> None:
    """Validate the product-owned declaration without executing a target operation."""
    if definition.contract_lifecycle not in {
        ContractLifecycle.GATEABLE,
        ContractLifecycle.RELEASED,
    }:
        raise ValueError(f"canonical operation contract is incomplete: {definition.operation}")
    for label, schema in (
        ("input", definition.input_schema),
        ("output", definition.output_schema),
    ):
        validate_schema_definition(schema, f"{definition.operation} {label}")
        if schema["type"] != "object":
            raise ValueError(f"{definition.operation} {label} schema must describe an object")
    if not definition.output_schema["properties"]:
        raise ValueError(f"{definition.operation} output schema is not explicit")
    if not definition.error_codes:
        raise ValueError(f"canonical operation has no error contract: {definition.operation}")
    if definition.access == "read" and definition.risk in {"R2", "R3"}:
        raise ValueError(f"read operation exceeds R1 risk: {definition.operation}")
    if definition.access == "read" and definition.risk == "R1" and (
        definition.observation_overhead != ObservationOverhead.ELEVATED
        or not definition.side_effects
        or definition.rate_limit == "on_demand"
    ):
        raise ValueError(f"R1 read operation lacks overhead controls: {definition.operation}")
    if (
        definition.access == "read"
        and definition.risk == "R0"
        and definition.observation_overhead == ObservationOverhead.ELEVATED
    ):
        raise ValueError(f"R0 read operation has elevated overhead: {definition.operation}")
    if (
        definition.cancelable
        and definition.access != "write"
        and definition.execution_mode != ExecutionMode.BOUNDED_STREAM
    ):
        raise ValueError(
            f"cancelable operation must be a write or bounded stream: {definition.operation}"
        )
    expected_result = (
        ResultSemantics.SESSION_HANDLE
        if definition.execution_mode == ExecutionMode.SESSION_START
        else ResultSemantics.OBSERVATION
        if definition.access == "read"
        else ResultSemantics.ACKNOWLEDGEMENT_ONLY
    )
    if definition.result_semantics != expected_result:
        raise ValueError(
            f"canonical operation has invalid result semantics: {definition.operation}"
        )
    if definition.access == "write" and "status" not in definition.output_schema.get(
        "required", []
    ):
        raise ValueError(
            f"write operation does not require acknowledgement: {definition.operation}"
        )
    if definition.risk == "R3" and any(
        not values
        for values in (
            definition.preconditions,
            definition.postconditions,
            definition.side_effects,
            definition.resource_locks,
        )
    ):
        raise ValueError(f"R3 operation lacks safety contract fields: {definition.operation}")
    input_required = set(definition.input_schema.get("required", []))
    output_required = set(definition.output_schema.get("required", []))
    if definition.execution_mode == ExecutionMode.BOUNDED_STREAM:
        if (
            definition.access != "read"
            or not definition.cancelable
            or definition.risk != "R1"
            or definition.observation_overhead != ObservationOverhead.ELEVATED
            or not {"duration_s", "max_items", "max_bytes"} <= input_required
            or not {"status", "observed_at", "truncated"} <= output_required
        ):
            raise ValueError(f"bounded stream contract is incomplete: {definition.operation}")
    elif definition.execution_mode in {ExecutionMode.SESSION_START, ExecutionMode.SESSION_STOP}:
        if definition.access != "write" or not definition.paired_operation:
            raise ValueError(f"session control contract is incomplete: {definition.operation}")
        if definition.execution_mode == ExecutionMode.SESSION_START and (
            not {"ttl_s", "max_bytes"} <= input_required
            or not {"status", "session_id", "expires_at"} <= output_required
        ):
            raise ValueError(f"session start contract is incomplete: {definition.operation}")
        if definition.execution_mode == ExecutionMode.SESSION_STOP and (
            "session_id" not in input_required
            or not {"status", "session_id"} <= output_required
        ):
            raise ValueError(f"session stop contract is incomplete: {definition.operation}")
    elif definition.paired_operation is not None:
        raise ValueError(f"request contract has an invalid session pair: {definition.operation}")


def materialize_active_catalog(
    report: DiscoveryReport,
    *,
    bundle: AdapterBundleManifest | None = None,
) -> ToolCatalog:
    """Trusted composition of product definitions, host evidence, and a gated bundle."""
    registry = canonical_operation_registry()
    candidates = {item.operation: item for item in report.operation_candidates}
    bundle_entries = (
        {item.operation: item for item in bundle.operations} if bundle else {}
    )
    _, deferred = adapter_operation_eligibility(report)
    tools: list[ToolDescriptor] = []
    for definition in registry.operations:
        candidate = candidates.get(definition.operation)
        if definition.contract_lifecycle not in {
            ContractLifecycle.GATEABLE,
            ContractLifecycle.RELEASED,
        }:
            availability = "UNAVAILABLE"
            adapter = "unbound"
        elif definition.operation in _BUILTIN_CLI:
            availability = "AVAILABLE"
            adapter = (
                "builtin.host_introspection"
                if definition.operation.startswith(("linux.", "middleware.", "ros.node."))
                else "builtin.discovery"
            )
            if definition.operation == "ros.graph.snapshot" and report.probes["ros"].status not in {
                "SUCCEEDED",
                "PARTIAL",
            }:
                availability = "UNAVAILABLE"
        elif candidate is not None:
            if definition.operation in bundle_entries:
                if candidate_runtime_evidence_complete(candidate, report.probes):
                    availability = "VERIFIED"
                elif candidate_routes_fully_observed(candidate, report.probes):
                    availability = "ROUTE_VERIFIED"
                else:
                    availability = "UNAVAILABLE"
            elif bundle is not None:
                availability = "UNAVAILABLE"
            else:
                availability = candidate.status
            adapter = (
                f"bundle:{bundle.bundle_id}#{bundle_entries[definition.operation].entrypoint}"
                if definition.operation in bundle_entries and bundle is not None
                else "unbound"
                if bundle is not None
                else "generated.binding_candidate"
            )
        else:
            availability = "UNAVAILABLE"
            adapter = "unbound"
        tools.append(
            ToolDescriptor(
                operation=definition.operation,
                canonical_cli=definition.canonical_cli,
                layer=definition.layer,
                description=definition.description,
                risk=definition.risk,
                access=definition.access,
                idempotent=definition.idempotent,
                cancelable=definition.cancelable,
                max_duration_s=definition.max_duration_s,
                availability=availability,
                adapter=adapter,
                contract_lifecycle=definition.contract_lifecycle.value,
                contract_version=definition.contract_version,
                contract_sha256=definition.contract_sha256,
                data_classification=definition.data_classification.value,
                result_semantics=definition.result_semantics.value,
                observation_overhead=definition.observation_overhead.value,
                execution_mode=definition.execution_mode.value,
                paired_operation=definition.paired_operation,
                replacement_operation=definition.replacement_operation,
                capability_requirements=definition.capability_requirements,
                preconditions=definition.preconditions,
                postconditions=definition.postconditions,
                semantic_bindings=candidate.semantic_bindings if candidate else [],
                semantic_units=definition.semantic_units,
                coordinate_frames=definition.coordinate_frames,
                time_semantics=definition.time_semantics,
                side_effects=definition.side_effects,
                resource_locks=definition.resource_locks,
                rate_limit=definition.rate_limit,
                retry_policy=definition.retry_policy,
                compensation_operation=definition.compensation_operation,
                requires_quiescence=definition.requires_quiescence,
                evidence=candidate.evidence if candidate else [],
                limitations=[
                    *(candidate.limitations if candidate else []),
                    *(
                        [
                            "Product contract is not gateable "
                            f"({definition.contract_lifecycle.value}); promotion is prohibited"
                        ]
                        if definition.contract_lifecycle
                        not in {ContractLifecycle.GATEABLE, ContractLifecycle.RELEASED}
                        else []
                    ),
                    *(
                        [f"Deferred from this release: {deferred[definition.operation]}"]
                        if bundle is not None and definition.operation in deferred
                        else []
                    ),
                    *(
                        [
                            "Target route was observed, but provider identity, interface schema, "
                            "or runtime revision evidence is incomplete; operation is route-only "
                            "and cannot be invoked as VERIFIED."
                        ]
                        if availability == "ROUTE_VERIFIED"
                        else []
                    ),
                ],
                error_codes=definition.error_codes,
                input_schema=definition.input_schema,
                output_schema=definition.output_schema,
            )
        )
    return ToolCatalog(
        robot_id=report.robot_id,
        discovery_id=report.discovery_id,
        contract_catalog_sha256=registry.contract_catalog_sha256,
        tools=tools,
    )


def validate_candidate_operations(candidates: Iterable[OperationCandidate]) -> None:
    known = {item.operation for item in canonical_operation_registry().operations}
    values = list(candidates)
    operations = [item.operation for item in values]
    if len(operations) != len(set(operations)):
        raise ValueError("operation candidates contain duplicates")
    unknown = sorted(set(operations) - known)
    if unknown:
        raise ValueError(f"operation candidates are not defined by the product registry: {unknown}")
