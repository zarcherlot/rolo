from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from rolo.contract_catalog import ContractLifecycle, load_operation_contracts
from rolo.core.models import DiscoveryReport, OperationCandidate, ToolDescriptor
from rolo.schema_subset import validate_schema_definition
from rolo.stages.adapt.models import AdapterBundleManifest, ToolCatalog


class CanonicalOperationDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: str
    layer: Literal["control", "hw", "linux", "middleware", "ros", "app"]
    description: str
    risk: str = "R0"
    access: str = "read"
    idempotent: bool = True
    cancelable: bool = False
    max_duration_s: float = 30.0
    canonical_cli: list[str]
    input_schema: dict[str, Any] = Field(
        default_factory=lambda: {"type": "object", "additionalProperties": False}
    )
    output_schema: dict[str, Any] = Field(default_factory=lambda: {"type": "object"})
    error_codes: list[str] = Field(
        default_factory=lambda: ["UNAVAILABLE", "TIMEOUT", "OPERATION_FAILED"]
    )
    contract_lifecycle: ContractLifecycle = ContractLifecycle.DRAFT
    contract_version: str | None = None
    contract_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    capability_requirements: list[str] = Field(default_factory=list)
    preconditions: list[str] = Field(default_factory=list)
    postconditions: list[str] = Field(default_factory=list)
    semantic_units: dict[str, str] = Field(default_factory=dict)
    coordinate_frames: list[str] = Field(default_factory=list)
    time_semantics: str = ""
    side_effects: list[str] = Field(default_factory=list)
    resource_locks: list[str] = Field(default_factory=list)
    rate_limit: str = "on_demand"
    retry_policy: str = "none"
    compensation_operation: str | None = None


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
        "linux.host.inspect",
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
        "ros.topic.echo",
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
        "ros.diagnostics.hardware",
        "ros.diagnostics.software",
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
    "hw.inventory.scan": "robotctl hw inventory scan",
    "linux.host.inventory": "robotctl linux host inventory",
    "linux.host.inspect": "robotctl linux host inspect",
    "linux.service.list": "robotctl linux service list",
    "linux.service.inspect": "robotctl linux service inspect NAME",
    "linux.container.list": "robotctl linux container list",
    "linux.container.inspect": "robotctl linux container inspect NAME",
    "linux.schedule.list": "robotctl linux schedule list",
    "linux.schedule.inspect": "robotctl linux schedule inspect NAME",
    "linux.process.list": "robotctl linux process list",
    "linux.process.inspect": "robotctl linux process inspect PID",
    "linux.binary.describe": "robotctl linux binary describe PATH",
    "linux.cli.probe": "robotctl linux cli probe PATH --arg=--help",
    "linux.config.locate": "robotctl linux config locate --process PID",
    "linux.network.listeners": "robotctl linux network listeners",
    "middleware.inspect": "robotctl middleware inspect",
    "ros.node.status": "robotctl ros node status NAME",
    "ros.graph.snapshot": "robotctl ros graph snapshot",
    "app.robot.discover": "robotctl app robot discover",
    "tool.catalog": "robotctl tool catalog --robot ROBOT_ID",
}


_DRAFT_INPUT_SCHEMA = {"type": "object", "properties": {}, "additionalProperties": False}
_DRAFT_OUTPUT_SCHEMA = {"type": "object"}


def _is_write(operation: str) -> bool:
    verb = operation.rsplit(".", 1)[-1]
    return operation.endswith((".emergency_stop", ".protective_stop")) or verb in {
        "apply",
        "calibrate",
        "call",
        "cancel",
        "clear",
        "close",
        "command",
        "commit",
        "create",
        "cycle",
        "deactivate",
        "disable",
        "enable",
        "execute",
        "export",
        "home",
        "import",
        "initialize",
        "load",
        "open",
        "pause",
        "play",
        "publish",
        "reboot",
        "record",
        "recover",
        "relocalize",
        "reset",
        "restart",
        "restore",
        "resume",
        "rollback",
        "run",
        "save",
        "send",
        "set",
        "shutdown",
        "signal",
        "start",
        "stop",
        "synchronize",
        "update",
    }


def _is_physical(operation: str) -> bool:
    physical_suffixes = {
        "calibrate",
        "cancel",
        "close",
        "command",
        "disable",
        "enable",
        "execute",
        "home",
        "joint",
        "move_distance",
        "open",
        "pause",
        "pose",
        "recover",
        "reset",
        "resume",
        "rotate",
        "set",
        "start",
        "stop",
        "velocity",
    }
    family = operation.startswith(
        (
            "hw.actuator.",
            "app.teleop.",
            "app.base.",
            "app.manipulation.",
            "app.gripper.",
            "app.navigation.",
            "app.safety.",
        )
    )
    return family and operation.rsplit(".", 1)[-1] in physical_suffixes


def canonical_operation_registry() -> CanonicalOperationRegistry:
    catalog = load_operation_contracts()
    contracts = {contract.operation: contract for contract in catalog.contracts}
    vocabulary = {operation for operations in _GROUPS.values() for operation in operations}
    unknown_contracts = sorted(set(contracts) - vocabulary)
    if unknown_contracts:
        raise RuntimeError(f"contracts are outside the product vocabulary: {unknown_contracts}")
    definitions: list[CanonicalOperationDefinition] = []
    for layer, operations in _GROUPS.items():
        for operation in operations:
            write = _is_write(operation) or _is_physical(operation)
            contract = contracts.get(operation)
            if contract is not None and contract.layer != layer:
                raise RuntimeError(f"contract layer mismatch: {operation}")
            definitions.append(
                CanonicalOperationDefinition(
                    operation=operation,
                    layer=layer,  # type: ignore[arg-type]
                    description=(
                        contract.description if contract else operation.replace(".", " ")
                    ),
                    risk=(
                        contract.risk
                        if contract
                        else "R3"
                        if _is_physical(operation) or operation.startswith("app.safety.") and write
                        else "R2"
                        if write
                        else "R0"
                    ),
                    access=contract.access if contract else "write" if write else "read",
                    idempotent=contract.idempotent if contract else not write,
                    cancelable=contract.cancelable if contract else False,
                    max_duration_s=contract.max_duration_s if contract else 30.0,
                    canonical_cli=(
                        contract.canonical_cli
                        if contract
                        else [
                            "robotctl",
                            "tool",
                            "invoke",
                            "{operation}",
                            "--robot",
                            "{robot_id}",
                            "--input",
                            "{input_json}",
                        ]
                    ),
                    input_schema=contract.input_schema if contract else _DRAFT_INPUT_SCHEMA,
                    output_schema=contract.output_schema if contract else _DRAFT_OUTPUT_SCHEMA,
                    error_codes=(
                        contract.error_codes
                        if contract
                        else ["UNAVAILABLE", "CONTRACT_INCOMPLETE"]
                    ),
                    contract_lifecycle=(
                        contract.lifecycle if contract else ContractLifecycle.DRAFT
                    ),
                    contract_version=contract.version if contract else None,
                    contract_sha256=contract.sha256 if contract else None,
                    capability_requirements=(
                        contract.capability_requirements if contract else []
                    ),
                    preconditions=contract.preconditions if contract else [],
                    postconditions=contract.postconditions if contract else [],
                    semantic_units=contract.semantic_units if contract else {},
                    coordinate_frames=contract.coordinate_frames if contract else [],
                    time_semantics=contract.time_semantics if contract else "",
                    side_effects=contract.side_effects if contract else [],
                    resource_locks=contract.resource_locks if contract else [],
                    rate_limit=contract.rate_limit if contract else "on_demand",
                    retry_policy=contract.retry_policy if contract else "none",
                    compensation_operation=(
                        contract.compensation_operation if contract else None
                    ),
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


def required_conformance_operations(report: DiscoveryReport) -> set[str]:
    definitions = {item.operation: item for item in canonical_operation_registry().operations}
    incomplete = sorted(
        candidate.operation
        for candidate in report.operation_candidates
        if definitions[candidate.operation].contract_lifecycle
        not in {ContractLifecycle.GATEABLE, ContractLifecycle.RELEASED}
    )
    if incomplete:
        raise ValueError(
            "discovered operations lack complete product contracts: " + ", ".join(incomplete)
        )
    return builtin_operations() | {item.operation for item in report.operation_candidates}


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
    if definition.access == "read" and definition.risk != "R0":
        raise ValueError(f"read operation has a non-R0 risk: {definition.operation}")
    if definition.cancelable and definition.access != "write":
        raise ValueError(f"cancelable operation must be a write: {definition.operation}")
    if definition.contract_version is None or definition.contract_sha256 is None:
        raise ValueError(f"canonical operation lacks version/hash binding: {definition.operation}")


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
            availability = (
                "VERIFIED" if definition.operation in bundle_entries else candidate.status
            )
            adapter = (
                f"bundle:{bundle.bundle_id}#{bundle_entries[definition.operation].entrypoint}"
                if definition.operation in bundle_entries and bundle is not None
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
