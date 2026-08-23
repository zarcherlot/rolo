from copy import deepcopy
from pathlib import Path

import pytest

from rolo.contract_catalog import (
    ContractLifecycle,
    ExecutionMode,
    OperationContract,
    OperationContractCatalog,
    compatibility_issues,
    load_operation_contracts,
    render_canonical_cli,
    render_contract_catalog,
)
from rolo.stages.adapt.operation_registry import canonical_operation_registry


def test_authored_contracts_compile_into_the_complete_product_vocabulary() -> None:
    catalog = load_operation_contracts()
    registry = canonical_operation_registry()

    assert len(catalog.contracts) == 294
    assert len(registry.operations) == 294
    assert sum(item.lifecycle == ContractLifecycle.RELEASED for item in catalog.contracts) == 62
    assert sum(item.lifecycle == ContractLifecycle.GATEABLE for item in catalog.contracts) == 232
    assert sum(item.lifecycle == ContractLifecycle.DEPRECATED for item in catalog.contracts) == 0
    draft_count = sum(
        item.contract_lifecycle == ContractLifecycle.DRAFT for item in registry.operations
    )
    assert draft_count == 0
    assert registry.contract_catalog_sha256 == catalog.sha256
    assert len(catalog.sha256) == 64
    assert {item.version for item in catalog.contracts} == {"1.1.0", "2.0.0"}
    assert catalog.by_operation()["ros.node.status"].version == "2.0.0"
    assert all(item.data_classification.value in {
        "PUBLIC", "INTERNAL", "SENSITIVE", "SECRET"
    } for item in catalog.contracts)
    assert catalog.by_operation()["runtime.version"].data_classification.value == "PUBLIC"
    assert catalog.by_operation()["app.camera.snapshot"].data_classification.value == "SENSITIVE"
    assert catalog.by_operation()["ros.parameter.get"].data_classification.value == "SENSITIVE"
    assert catalog.by_operation()["hw.sensor.read"].data_classification.value == "SENSITIVE"
    assert catalog.by_operation()["app.localization.pose"].data_classification.value == "SENSITIVE"
    assert catalog.by_operation()["hw.bus.scan"].risk == "R1"
    writes = [item for item in catalog.contracts if item.access == "write"]
    assert writes
    assert all(
        item.result_semantics.value
        in {"ACKNOWLEDGEMENT_ONLY", "SESSION_HANDLE"}
        for item in writes
    )
    assert all(
        item.preconditions and item.postconditions and item.side_effects and item.resource_locks
        for item in writes
        if item.risk == "R3"
    )


def test_contract_hash_and_cli_rendering_are_deterministic() -> None:
    contract = load_operation_contracts().by_operation()["app.camera.snapshot"]

    assert contract.sha256 == OperationContract.model_validate(
        contract.model_dump(mode="json")
    ).sha256
    assert render_canonical_cli(
        contract, robot_id="robot-1", payload={"camera": "front"}
    )[-1] == '{"camera":"front"}'


def test_breaking_contract_change_requires_a_new_major_version() -> None:
    previous = load_operation_contracts().by_operation()["app.camera.snapshot"]
    changed = deepcopy(previous.model_dump(mode="json"))
    changed["input_schema"]["properties"]["quality"] = {"type": "integer"}
    changed["input_schema"].setdefault("required", []).append("quality")
    current = OperationContract.model_validate(changed)

    assert "new required input properties: ['quality']" in compatibility_issues(
        previous, current
    )
    assert "breaking changes require a new major version" in compatibility_issues(
        previous, current
    )


def test_contract_schema_rejects_unknown_keywords() -> None:
    payload = deepcopy(
        load_operation_contracts().by_operation()["app.camera.snapshot"].model_dump(
            mode="json"
        )
    )
    payload["input_schema"]["unevaluatedProperties"] = False

    with pytest.raises(ValueError, match="unsupported schema keywords"):
        OperationContract.model_validate(payload)


def test_contract_compatibility_rejects_weaker_data_classification() -> None:
    previous = load_operation_contracts().by_operation()["app.camera.snapshot"]
    changed = deepcopy(previous.model_dump(mode="json"))
    changed["data_classification"] = "INTERNAL"
    current = OperationContract.model_validate(changed)

    assert "data classification was weakened" in compatibility_issues(previous, current)
    assert "breaking changes require a new major version" in compatibility_issues(
        previous, current
    )


def test_generic_contract_rejects_secret_data() -> None:
    contract = load_operation_contracts().by_operation()["app.camera.snapshot"]
    changed = deepcopy(contract.model_dump(mode="json"))
    changed["data_classification"] = "SECRET"

    with pytest.raises(ValueError, match="SECRET data cannot be exposed"):
        OperationContract.model_validate(changed)


def test_high_risk_write_contract_requires_acknowledgement_and_safety_fields() -> None:
    contract = load_operation_contracts().by_operation()["app.teleop.velocity"]
    changed = deepcopy(contract.model_dump(mode="json"))
    changed["result_semantics"] = "OBSERVATION"

    with pytest.raises(ValueError, match="write operations require ACKNOWLEDGEMENT_ONLY"):
        OperationContract.model_validate(changed)

    changed = deepcopy(contract.model_dump(mode="json"))
    changed["resource_locks"] = []
    with pytest.raises(ValueError, match="R3 operation lacks safety contract fields"):
        OperationContract.model_validate(changed)


def test_r1_read_contract_requires_explicit_observation_controls() -> None:
    contract = load_operation_contracts().by_operation()["hw.bus.scan"]
    assert contract.observation_overhead.value == "ELEVATED"

    changed = deepcopy(contract.model_dump(mode="json"))
    changed["observation_overhead"] = "BOUNDED"
    with pytest.raises(ValueError, match="R1 read operations require ELEVATED"):
        OperationContract.model_validate(changed)

    changed = deepcopy(contract.model_dump(mode="json"))
    changed["rate_limit"] = "on_demand"
    with pytest.raises(ValueError, match="R1 read operations require side effects"):
        OperationContract.model_validate(changed)


def test_bounded_streams_and_session_pairs_have_machine_enforced_limits() -> None:
    catalog = load_operation_contracts()
    sample = catalog.by_operation()["ros.topic.sample"]
    assert sample.execution_mode == ExecutionMode.BOUNDED_STREAM
    assert sample.cancelable is True
    assert set(sample.input_schema["required"]) >= {
        "duration_s", "max_items", "max_bytes"
    }

    start = catalog.by_operation()["app.camera.stream.start"]
    stop = catalog.by_operation()["app.camera.stream.stop"]
    assert start.execution_mode == ExecutionMode.SESSION_START
    assert stop.execution_mode == ExecutionMode.SESSION_STOP
    assert start.paired_operation == stop.operation
    assert stop.paired_operation == start.operation

    changed = deepcopy(sample.model_dump(mode="json"))
    changed["input_schema"]["properties"]["max_bytes"].pop("maximum")
    with pytest.raises(ValueError, match="max_bytes requires positive minimum and maximum"):
        OperationContract.model_validate(changed)


def test_retired_host_inspect_alias_is_not_a_product_operation() -> None:
    catalog = load_operation_contracts()
    registry = {item.operation for item in canonical_operation_registry().operations}

    assert "linux.host.inspect" not in catalog.by_operation()
    assert "linux.host.inspect" not in registry
    assert "linux.host.inventory" in registry


def test_linux_lifecycle_writes_have_gateable_acknowledgement_contracts() -> None:
    catalog = load_operation_contracts().by_operation()
    operations = {
        "linux.host.reboot",
        "linux.host.shutdown",
        "linux.process.start",
        "linux.process.stop",
        "linux.process.restart",
        "linux.process.signal",
        "linux.service.start",
        "linux.service.stop",
        "linux.service.restart",
        "linux.service.enable",
        "linux.service.disable",
        "linux.container.start",
        "linux.container.stop",
        "linux.container.restart",
        "linux.schedule.enable",
        "linux.schedule.disable",
        "linux.schedule.run",
        "linux.time.synchronize",
    }

    assert all(catalog[name].lifecycle == ContractLifecycle.GATEABLE for name in operations)
    assert all(catalog[name].access == "write" for name in operations)
    assert all(
        catalog[name].result_semantics.value == "ACKNOWLEDGEMENT_ONLY"
        for name in operations
    )
    assert all(
        "resulting state must be observed separately" in catalog[name].postconditions[0]
        for name in operations
    )


def test_config_mutations_use_artifacts_and_non_authorizing_rollback_tokens() -> None:
    catalog = load_operation_contracts().by_operation()
    apply = catalog["linux.config.apply"]
    rollback = catalog["linux.config.rollback"]

    assert apply.lifecycle == rollback.lifecycle == ContractLifecycle.GATEABLE
    assert apply.data_classification.value == rollback.data_classification.value == "SENSITIVE"
    assert "path" not in apply.input_schema["properties"]
    assert {
        "target_resource_id",
        "artifact_ref",
        "artifact_sha256",
        "format",
        "max_bytes",
    } <= set(apply.input_schema["required"])
    assert "rollback_token" in apply.output_schema["required"]
    assert set(rollback.input_schema["required"]) == {
        "target_resource_id",
        "rollback_token",
    }
    assert apply.result_semantics.value == rollback.result_semantics.value == (
        "ACKNOWLEDGEMENT_ONLY"
    )


def test_non_motion_state_mutations_are_gateable_acknowledgements() -> None:
    catalog = load_operation_contracts().by_operation()
    operations = {
        "app.odometry.reset",
        "app.localization.initialize",
        "app.localization.reset",
        "app.localization.relocalize",
        "app.map.create",
        "app.map.save",
        "app.map.load",
        "app.map.clear",
        "app.map.import",
    }

    assert all(catalog[name].lifecycle == ContractLifecycle.GATEABLE for name in operations)
    assert all(catalog[name].risk == "R2" for name in operations)
    assert all(catalog[name].access == "write" for name in operations)
    assert all(
        catalog[name].result_semantics.value == "ACKNOWLEDGEMENT_ONLY"
        for name in operations
    )
    assert "motion is not started" in catalog["app.map.create"].postconditions[0]
    assert "navigation or robot motion is not started" in (
        catalog["app.map.import"].postconditions[0]
    )
    assert "artifact_ref" in catalog["app.map.import"].input_schema["required"]
    assert "artifact_sha256" in catalog["app.map.import"].input_schema["required"]


def test_episode_and_checkpoint_contracts_bound_control_plane_state_only() -> None:
    catalog = load_operation_contracts().by_operation()
    operations = {
        "episode.list",
        "episode.inspect",
        "episode.export",
        "checkpoint.list",
        "checkpoint.create",
        "checkpoint.restore",
    }

    assert all(catalog[name].lifecycle == ContractLifecycle.GATEABLE for name in operations)
    assert all(
        catalog[name].data_classification.value == "SENSITIVE" for name in operations
    )
    assert catalog["episode.export"].risk == "R1"
    assert catalog["episode.export"].observation_overhead.value == "ELEVATED"
    assert "max_bytes" in catalog["episode.export"].input_schema["required"]
    assert "artifact_ref" in catalog["episode.export"].output_schema["required"]
    assert catalog["checkpoint.create"].risk == "R2"
    assert catalog["checkpoint.restore"].risk == "R2"
    assert catalog["checkpoint.restore"].result_semantics.value == (
        "ACKNOWLEDGEMENT_ONLY"
    )
    assert "expected_current_revision" in (
        catalog["checkpoint.restore"].input_schema["required"]
    )
    assert len(catalog["checkpoint.restore"].preconditions) == 1
    assert len(catalog["checkpoint.restore"].postconditions) == 1
    assert "physical robot state are not restored or resumed" in (
        catalog["checkpoint.restore"].postconditions[0]
    )


def test_tuning_evaluation_is_bounded_observation_without_execution() -> None:
    contract = load_operation_contracts().by_operation()["app.tuning.candidate.evaluate"]

    assert contract.lifecycle == ContractLifecycle.GATEABLE
    assert contract.risk == "R1"
    assert contract.access == "read"
    assert contract.observation_overhead.value == "ELEVATED"
    assert contract.rate_limit != "on_demand"
    assert "not applied" in contract.postconditions[0]
    assert "robot motion" in contract.postconditions[0]


def test_parameter_and_tuning_mutations_require_quiescence_only_when_applying() -> None:
    catalog = load_operation_contracts().by_operation()
    operations = {
        "app.parameter.set",
        "app.parameter.rollback",
        "app.tuning.baseline.create",
        "app.tuning.candidate.create",
        "app.tuning.commit",
        "app.tuning.rollback",
    }
    applying = {
        "app.parameter.set",
        "app.parameter.rollback",
        "app.tuning.commit",
        "app.tuning.rollback",
    }

    assert all(catalog[name].lifecycle == ContractLifecycle.GATEABLE for name in operations)
    assert all(catalog[name].risk == "R2" for name in operations)
    assert all(catalog[name].access == "write" for name in operations)
    assert all(
        catalog[name].data_classification.value == "SENSITIVE" for name in operations
    )
    assert all(catalog[name].requires_quiescence for name in applying)
    assert all(
        not catalog[name].requires_quiescence for name in operations - applying
    )
    assert "artifact_ref" in (
        catalog["app.tuning.candidate.create"].input_schema["required"]
    )
    assert "artifact_sha256" in (
        catalog["app.tuning.candidate.create"].input_schema["required"]
    )
    assert "rollback_token" in catalog["app.parameter.set"].output_schema["required"]
    assert "rollback_token" in catalog["app.tuning.commit"].output_schema["required"]
    assert "robot motion is started" in (
        catalog["app.tuning.baseline.create"].postconditions[0]
    )


def test_quiescence_flag_is_rejected_outside_r2_writes() -> None:
    contract = load_operation_contracts().by_operation()["app.parameter.set"]
    changed = deepcopy(contract.model_dump(mode="json"))
    changed["access"] = "read"
    changed["risk"] = "R0"
    changed["result_semantics"] = "OBSERVATION"

    with pytest.raises(ValueError, match="quiescence may only be required by R2 write"):
        OperationContract.model_validate(changed)

    changed = deepcopy(contract.model_dump(mode="json"))
    changed["max_duration_s"] = 116
    with pytest.raises(ValueError, match="leave provider lease margin"):
        OperationContract.model_validate(changed)


def test_generic_execution_runs_are_r3_and_have_targeted_cancellation() -> None:
    catalog = load_operation_contracts().by_operation()
    pairs = {
        "app.task.start": "app.task.cancel",
        "app.test.run": "app.test.cancel",
        "app.regression.run": "app.regression.cancel",
        "app.diagnosis.run": "app.diagnosis.cancel",
    }

    for operation, cancellation in pairs.items():
        run = catalog[operation]
        cancel = catalog[cancellation]
        assert run.lifecycle == cancel.lifecycle == ContractLifecycle.GATEABLE
        assert run.risk == "R3"
        assert run.access == "write"
        assert run.cancelable is True
        assert run.compensation_operation == cancellation
        assert run.result_semantics.value == "ACKNOWLEDGEMENT_ONLY"
        assert len(run.preconditions) == 1
        assert len(run.postconditions) == 1
        assert len(run.side_effects) == 1
        assert "run_id" in run.output_schema["required"]
        assert cancel.risk == "R2"
        assert cancel.access == "write"
        assert cancel.input_schema["required"] == ["run_id"]
        assert "stopped state must be observed separately" in cancel.postconditions[0]


def test_physical_application_controls_separate_r3_actions_from_r2_cancel() -> None:
    catalog = load_operation_contracts().by_operation()
    direct_physical_controls = {
        "app.teleop.pose",
        "app.teleop.joint",
        "app.teleop.stop",
        "app.base.velocity",
        "app.base.move_distance",
        "app.base.rotate",
        "app.base.stop",
        "app.base.recover",
        "app.manipulation.execute",
        "app.manipulation.stop",
        "app.manipulation.home",
        "app.gripper.open",
        "app.gripper.close",
        "app.gripper.set",
        "app.gripper.stop",
        "app.navigation.start",
        "app.navigation.pause",
        "app.navigation.resume",
        "app.navigation.stop",
        "app.navigation.recover",
        "app.task.pause",
        "app.task.resume",
        "app.task.stop",
    }

    assert all(
        catalog[name].lifecycle == ContractLifecycle.GATEABLE
        for name in direct_physical_controls
    )
    assert all(catalog[name].access == "write" for name in direct_physical_controls)
    assert all(catalog[name].risk == "R3" for name in direct_physical_controls)
    assert all(
        catalog[name].result_semantics.value == "ACKNOWLEDGEMENT_ONLY"
        for name in direct_physical_controls
    )

    ordinary_cancellations = {
        "app.manipulation.cancel",
        "app.navigation.cancel",
    }
    assert all(catalog[name].risk == "R2" for name in ordinary_cancellations)
    assert all(catalog[name].access == "write" for name in ordinary_cancellations)
    assert all(
        "stopped state must be observed separately" in catalog[name].postconditions[0]
        for name in ordinary_cancellations
    )

    assert catalog["app.base.move_distance"].compensation_operation == "app.base.stop"
    assert catalog["app.manipulation.execute"].compensation_operation == (
        "app.manipulation.cancel"
    )
    assert catalog["app.navigation.start"].compensation_operation == (
        "app.navigation.cancel"
    )
    for name in {"app.teleop.stop", "app.base.stop", "app.navigation.stop"}:
        assert "protective-stop" in catalog[name].postconditions[0]
        assert "emergency-stop" in catalog[name].postconditions[0]


def test_complete_product_vocabulary_has_conservative_mutation_boundaries() -> None:
    catalog = load_operation_contracts().by_operation()
    newly_authored = {
        "hw.sensor.calibrate",
        "hw.sensor.reset",
        "hw.actuator.command",
        "hw.actuator.stop",
        "hw.actuator.enable",
        "hw.actuator.disable",
        "hw.actuator.calibrate",
        "hw.actuator.reset",
        "hw.bus.reset",
        "hw.firmware.update",
        "hw.firmware.rollback",
        "hw.power.rail.enable",
        "hw.power.rail.disable",
        "hw.power.cycle",
        "ros.topic.publish",
        "ros.service.call",
        "ros.action.send",
        "ros.action.cancel",
        "ros.bag.record",
        "ros.bag.play",
        "app.robot.start",
        "app.robot.stop",
        "app.robot.restart",
        "app.calibration.run",
        "app.calibration.apply",
        "app.calibration.rollback",
    }
    r3_operations = {
        "hw.actuator.command",
        "hw.actuator.stop",
        "hw.actuator.enable",
        "hw.actuator.disable",
        "hw.actuator.calibrate",
        "hw.actuator.reset",
        "hw.power.rail.enable",
        "hw.power.rail.disable",
        "hw.power.cycle",
        "ros.topic.publish",
        "ros.service.call",
        "ros.action.send",
        "ros.bag.play",
        "app.robot.start",
        "app.robot.stop",
        "app.robot.restart",
        "app.calibration.run",
    }
    quiescent_r2_operations = {
        "hw.sensor.calibrate",
        "hw.sensor.reset",
        "hw.bus.reset",
        "hw.firmware.update",
        "hw.firmware.rollback",
        "app.calibration.apply",
        "app.calibration.rollback",
    }

    assert all(
        catalog[name].lifecycle == ContractLifecycle.GATEABLE for name in newly_authored
    )
    assert all(catalog[name].access == "write" for name in newly_authored)
    assert all(catalog[name].data_classification.value == "SENSITIVE" for name in newly_authored)
    assert all(catalog[name].risk == "R3" for name in r3_operations)
    assert all(
        catalog[name].risk == "R2" for name in newly_authored - r3_operations
    )
    assert all(catalog[name].requires_quiescence for name in quiescent_r2_operations)
    assert all(
        not catalog[name].requires_quiescence
        for name in newly_authored - quiescent_r2_operations
    )

    assert catalog["ros.action.send"].compensation_operation == "ros.action.cancel"
    assert catalog["hw.actuator.calibrate"].compensation_operation == "hw.actuator.stop"
    for name in {"ros.topic.publish", "ros.service.call", "ros.action.send"}:
        required = catalog[name].input_schema["required"]
        assert "interface_id" in required
        assert "interface_schema_sha256" in required
    assert "artifact_sha256" in catalog["ros.bag.play"].input_schema["required"]
    assert "duration_s" in catalog["ros.bag.record"].input_schema["required"]
    assert "max_bytes" in catalog["ros.bag.record"].input_schema["required"]
    assert "rollback_token" in catalog["hw.firmware.update"].output_schema["required"]
    assert "rollback_token" in catalog["app.calibration.apply"].output_schema["required"]
    for name in {"hw.actuator.stop", "app.robot.stop"}:
        assert "protective-stop" in catalog[name].postconditions[0]
        assert "emergency-stop" in catalog[name].postconditions[0]


def test_cancelable_write_contract_requires_active_write_compensation() -> None:
    payload = load_operation_contracts().model_dump(mode="json")
    task_start = next(
        item for item in payload["contracts"] if item["operation"] == "app.task.start"
    )
    task_start["compensation_operation"] = None

    with pytest.raises(ValueError, match="cancelable write contract lacks compensation"):
        OperationContractCatalog.model_validate(payload)


def test_ros_node_lifecycle_transitions_are_gateable_writes() -> None:
    catalog = load_operation_contracts().by_operation()

    for name in {"ros.node.activate", "ros.node.deactivate"}:
        contract = catalog[name]
        assert contract.lifecycle == ContractLifecycle.GATEABLE
        assert contract.access == "write"
        assert contract.risk == "R2"
        assert contract.result_semantics.value == "ACKNOWLEDGEMENT_ONLY"


def test_ros_parameter_mutations_are_digest_bound_quiescent_r2_writes() -> None:
    catalog = load_operation_contracts().by_operation()
    operations = {
        "ros.parameter.set",
        "ros.parameter.load",
        "ros.parameter.rollback",
    }

    assert all(catalog[name].lifecycle == ContractLifecycle.GATEABLE for name in operations)
    assert all(catalog[name].risk == "R2" for name in operations)
    assert all(catalog[name].access == "write" for name in operations)
    assert all(catalog[name].requires_quiescence for name in operations)
    assert all(
        catalog[name].result_semantics.value == "ACKNOWLEDGEMENT_ONLY"
        for name in operations
    )
    assert "expected_current_sha256" in (
        catalog["ros.parameter.set"].input_schema["required"]
    )
    assert "artifact_sha256" in (
        catalog["ros.parameter.load"].input_schema["required"]
    )
    assert "expected_parameter_state_sha256" in (
        catalog["ros.parameter.load"].input_schema["required"]
    )
    assert "rollback_token" in (
        catalog["ros.parameter.load"].output_schema["required"]
    )
    assert "process restart" in catalog["ros.parameter.set"].postconditions[0]


def test_sensitive_results_and_evidence_are_gateable_but_not_preverified() -> None:
    catalog = load_operation_contracts().by_operation()
    registry = {item.operation: item for item in canonical_operation_registry().operations}
    operations = {
        "app.task.result",
        "app.test.result",
        "app.test.evidence",
        "app.regression.result",
        "app.diagnosis.snapshot",
        "app.diagnosis.result",
        "app.diagnosis.evidence",
        "app.parameter.get",
        "app.state.snapshot",
        "app.event.list",
        "app.event.inspect",
        "app.telemetry.snapshot",
        "app.telemetry.export",
    }

    assert all(catalog[name].lifecycle == ContractLifecycle.GATEABLE for name in operations)
    assert all(catalog[name].data_classification.value == "SENSITIVE" for name in operations)
    assert all(
        registry[name].contract_lifecycle == ContractLifecycle.GATEABLE
        for name in operations
    )
    assert catalog["app.telemetry.export"].risk == "R1"


def test_spatial_observation_contracts_are_bounded_sensitive_and_gateable() -> None:
    catalog = load_operation_contracts().by_operation()
    operations = {
        "ros.action.status",
        "ros.tf.tree",
        "ros.tf.snapshot",
        "ros.tf.lookup",
        "ros.tf.monitor",
        "ros.parameter.dump",
        "app.lidar.snapshot",
        "app.navigation.costmap.inspect",
        "app.navigation.path.inspect",
    }

    assert all(catalog[name].lifecycle == ContractLifecycle.GATEABLE for name in operations)
    assert all(catalog[name].data_classification.value == "SENSITIVE" for name in operations)
    assert catalog["ros.tf.monitor"].execution_mode == ExecutionMode.BOUNDED_STREAM
    assert catalog["ros.parameter.dump"].risk == "R1"
    assert "max_bytes" in catalog["app.navigation.path.inspect"].input_schema["required"]


def test_planning_validation_and_export_contracts_do_not_authorize_execution() -> None:
    catalog = load_operation_contracts().by_operation()
    operations = {
        "app.navigation.plan",
        "app.manipulation.plan",
        "app.test.plan",
        "app.regression.plan",
        "app.calibration.validate",
        "app.parameter.validate",
        "app.map.export",
    }

    assert all(catalog[name].lifecycle == ContractLifecycle.GATEABLE for name in operations)
    assert all(catalog[name].access == "read" for name in operations)
    assert all(catalog[name].data_classification.value == "SENSITIVE" for name in operations)
    assert "execution is not started" in catalog["app.navigation.plan"].postconditions[0]
    assert "not changed" in catalog["app.parameter.validate"].postconditions[0]


def test_protected_content_contracts_never_return_inline_content() -> None:
    catalog = load_operation_contracts().by_operation()
    operations = {
        "linux.file.read",
        "linux.config.inspect",
        "linux.config.validate",
        "linux.config.diff",
        "linux.process.logs",
        "linux.service.logs",
        "linux.container.logs",
        "linux.log.query",
        "linux.log.follow",
    }

    assert all(catalog[name].lifecycle == ContractLifecycle.GATEABLE for name in operations)
    assert all(catalog[name].data_classification.value == "SENSITIVE" for name in operations)
    for name in operations - {"linux.config.validate"}:
        properties = catalog[name].output_schema["properties"]
        assert "artifact_ref" in properties
        assert "content" not in properties
    assert catalog["linux.log.follow"].execution_mode == ExecutionMode.BOUNDED_STREAM


def test_diagnostics_categories_share_one_versioned_product_operation() -> None:
    catalog = load_operation_contracts().by_operation()
    registry = {item.operation for item in canonical_operation_registry().operations}
    snapshot = catalog["ros.diagnostics.snapshot"]

    assert snapshot.version == "2.0.0"
    assert snapshot.input_schema["properties"]["category"]["enum"] == [
        "all", "hardware", "software"
    ]
    assert "category" in snapshot.input_schema["required"]
    assert "ros.diagnostics.hardware" not in registry
    assert "ros.diagnostics.software" not in registry


def test_rendered_contract_catalog_contains_every_authored_contract() -> None:
    catalog = load_operation_contracts()
    rendered = render_contract_catalog(catalog)

    assert rendered.count("\n| `") == len(catalog.contracts)
    assert "app.teleop.velocity" in rendered
    tracked = (Path(__file__).parents[1] / "docs" / "OPERATION_CONTRACTS.md").read_text(
        encoding="utf-8"
    )
    assert tracked == rendered
