from __future__ import annotations

import shutil
from pathlib import Path

from pydantic import BaseModel

from rolo.adapter_runtime import (
    AdapterOutputLayout,
    activate_release,
    load_current_release,
    probe_adapter_package,
    publish_release,
)
from rolo.core.artifacts import ArtifactStore
from rolo.core.config import get_settings
from rolo.core.hashing import sha256_file
from rolo.core.models import OperationCandidate
from rolo.stages.adapt.active_discovery import ActiveDiscoveryReport, ActiveProbeMode
from rolo.stages.adapt.discovery import load_report
from rolo.stages.adapt.models import (
    AdapterAgentResult,
    AdapterAgentRun,
    AdapterAgentRunStatus,
    AdapterBundleManifest,
    AdapterConformanceReport,
    AdapterHandoff,
    AdapterOutputSnapshot,
    AdaptGateReport,
    AdaptGateStatus,
    AdaptLatestIndex,
    ConformanceScope,
    StateGraphBaseline,
)
from rolo.stages.adapt.operation_registry import (
    canonical_operation_registry,
    materialize_active_catalog,
    required_conformance_operations,
    validate_definition_contract,
)
from rolo.stages.artifact_paths import ArtifactLayout, resolve_artifact_ref
from rolo.stages.discovery_manifest import load_and_verify_discovery_manifest


def _ros_name(value: object) -> str:
    name = str(value).split(" ", 1)[0].strip()
    return f"/{name.lstrip('/')}".casefold() if name else ""


def _candidate_route_observed(candidate: OperationCandidate, probe_data: dict[str, object]) -> bool:
    """Require an exact normalized endpoint match in structured runtime probe fields."""
    probe_fields = {
        "ros_topic": "topics",
        "ros_service": "services",
        "ros_action": "actions",
    }
    for route in candidate.route_evidence:
        field = probe_fields.get(route.kind)
        if not route.observed or field is None:
            continue
        observed = {
            _ros_name(value)
            for value in probe_data.get(field, [])
            if isinstance(value, str) and _ros_name(value)
        }
        if _ros_name(route.name) in observed:
            return True
    return False


def _restore_index(path: Path, previous: bytes | None) -> None:
    """Compensate a failed cross-root publication without exposing a partial index."""
    if previous is None:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".rollback")
    temporary.write_bytes(previous)
    temporary.replace(path)


def _workspace_output(workspace: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"adapter output must be workspace-relative: {relative}")
    root = workspace.expanduser().resolve()
    path = (root / candidate).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"adapter output escapes workspace: {relative}") from exc
    if not path.is_file():
        raise FileNotFoundError(f"adapter output is missing: {path}")
    return path


def _read_model(path: Path, model: type[BaseModel]) -> BaseModel:
    try:
        return model.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"invalid {model.__name__} at {path}: {exc}") from exc


def latest_adapter_handoff_path(artifact_root: Path, robot_id: str) -> Path:
    layout = ArtifactLayout(artifact_root)
    index_path = layout.stage_latest_index("adapt", robot_id)
    index = AdaptLatestIndex.model_validate_json(index_path.read_text(encoding="utf-8"))
    if index.robot_id != robot_id:
        raise ValueError("adapt latest index robot identity mismatch")
    path = resolve_artifact_ref(artifact_root, index.handoff_ref)
    if not path.is_file() or sha256_file(path) != index.handoff_sha256:
        raise ValueError("adapt latest handoff hash mismatch")
    return path


def validate_adapter_handoff(
    artifact_root: Path,
    robot_id: str,
    handoff_path: Path | None = None,
    output_root: Path | None = None,
) -> AdapterHandoff:
    if handoff_path is None:
        path = latest_adapter_handoff_path(artifact_root, robot_id)
    else:
        path = handoff_path
    handoff = AdapterHandoff.model_validate_json(path.read_text(encoding="utf-8"))
    if handoff.robot_id != robot_id:
        raise ValueError("adapter handoff robot identity mismatch")
    _, manifest_path = load_and_verify_discovery_manifest(
        artifact_root, robot_id, handoff.source_discovery_id
    )
    checks = (
        (manifest_path, handoff.discovery_manifest_sha256),
        (
            resolve_artifact_ref(artifact_root, handoff.tool_catalog_ref),
            handoff.tool_catalog_sha256,
        ),
        (resolve_artifact_ref(artifact_root, handoff.state_graph_ref), handoff.state_graph_sha256),
        (
            resolve_artifact_ref(artifact_root, handoff.conformance_report_ref),
            handoff.conformance_report_sha256,
        ),
        (
            resolve_artifact_ref(artifact_root, handoff.gate_report_ref),
            handoff.gate_report_sha256,
        ),
    )
    for target, expected in checks:
        if not target.is_file() or sha256_file(target) != expected:
            raise ValueError(f"adapter handoff artifact hash mismatch: {target}")
    gate = AdaptGateReport.model_validate_json(
        resolve_artifact_ref(artifact_root, handoff.gate_report_ref).read_text(encoding="utf-8")
    )
    if gate.status != AdaptGateStatus.PASSED or gate.run_id != handoff.source_agent_run_id:
        raise ValueError("adapter handoff is not backed by a passed independent gate")
    release_prefix = "output://"
    if not handoff.release_ref.startswith(release_prefix):
        raise ValueError("adapter handoff has an invalid release reference")
    relative = Path(handoff.release_ref[len(release_prefix) :])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("adapter handoff release reference is unsafe")
    release_path = ((output_root or get_settings().rolo_output_dir) / relative).resolve()
    if not release_path.is_file() or sha256_file(release_path) != handoff.release_manifest_sha256:
        raise ValueError("adapter handoff release manifest hash mismatch")
    return handoff


class AdapterPromotionService:
    """Freeze Agent outputs, independently validate them, and publish a handoff."""

    def __init__(self, artifacts: ArtifactStore, output_root: Path) -> None:
        self.artifacts = artifacts
        self.layout = ArtifactLayout(artifacts.root)
        self.output_root = output_root

    def snapshot(self, run: AdapterAgentRun) -> tuple[AdapterOutputSnapshot, Path]:
        if run.status != AdapterAgentRunStatus.SUCCEEDED:
            raise ValueError("Adapter Agent run is not successful")
        if not run.result_ref:
            raise ValueError("successful Adapter Agent run has no structured result")
        result_path = resolve_artifact_ref(self.artifacts.root, run.result_ref)
        result = AdapterAgentResult.model_validate_json(result_path.read_text(encoding="utf-8"))
        if not result.handoff_ready or result.blockers or result.outputs is None:
            raise ValueError("Adapter Agent result is not ready for independent conformance")

        workspace = Path(run.workspace)
        bundle_manifest_path = _workspace_output(workspace, result.outputs.adapter_manifest)
        adapter_package_path = _workspace_output(workspace, result.outputs.adapter_package)
        graph_path = _workspace_output(workspace, result.outputs.state_graph)
        conformance_path = _workspace_output(workspace, result.outputs.conformance_report)
        bundle = _read_model(bundle_manifest_path, AdapterBundleManifest)
        graph = _read_model(graph_path, StateGraphBaseline)
        conformance = _read_model(conformance_path, AdapterConformanceReport)
        assert isinstance(bundle, AdapterBundleManifest)
        assert isinstance(graph, StateGraphBaseline)
        assert isinstance(conformance, AdapterConformanceReport)
        if bundle.robot_id != run.robot_id or bundle.discovery_id != run.source_discovery_id:
            raise ValueError("adapter bundle identity does not match the Adapter Agent run")
        if Path(bundle.package_file).name != adapter_package_path.name:
            raise ValueError("adapter bundle package_file does not match the proposed package")
        if sha256_file(adapter_package_path) != bundle.package_sha256:
            raise ValueError("adapter package hash does not match its bundle manifest")
        bundle_operations = [item.operation for item in bundle.operations]
        if len(bundle_operations) != len(set(bundle_operations)):
            raise ValueError("adapter bundle contains duplicate operations")
        discovery = load_report(self.artifacts.root, run.robot_id, run.source_discovery_id)
        expected_bundle_operations = {
            candidate.operation for candidate in discovery.operation_candidates
        }
        if set(bundle_operations) != expected_bundle_operations:
            raise ValueError(
                "adapter bundle operation coverage must exactly match discovered candidates"
            )
        identified_outputs = (
            (graph, "State Graph"),
            (conformance, "conformance report"),
        )
        for value, label in identified_outputs:
            if value.robot_id != run.robot_id or value.discovery_id != run.source_discovery_id:
                raise ValueError(f"{label} identity does not match the Adapter Agent run")

        snapshot_root = self.layout.stage_run("adapt", run.robot_id, run.run_id) / "output-snapshot"
        bundle_manifest_out = snapshot_root / "adapter-manifest.json"
        adapter_package_out = snapshot_root / adapter_package_path.name
        snapshot_root.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bundle_manifest_path, bundle_manifest_out)
        shutil.copy2(adapter_package_path, adapter_package_out)
        graph_out = self.artifacts.write_json(
            self.layout.relative(snapshot_root / "state-graph.json"),
            graph.model_dump(mode="json"),
        )
        conformance_out = self.artifacts.write_json(
            self.layout.relative(snapshot_root / "conformance-report.json"),
            conformance.model_dump(mode="json"),
        )
        snapshot = AdapterOutputSnapshot(
            run_id=run.run_id,
            robot_id=run.robot_id,
            discovery_id=run.source_discovery_id,
            adapter_manifest_ref=self.layout.ref(bundle_manifest_out),
            adapter_manifest_sha256=sha256_file(bundle_manifest_out),
            adapter_package_ref=self.layout.ref(adapter_package_out),
            adapter_package_sha256=sha256_file(adapter_package_out),
            state_graph_ref=self.layout.ref(graph_out),
            state_graph_sha256=sha256_file(graph_out),
            conformance_report_ref=self.layout.ref(conformance_out),
            conformance_report_sha256=sha256_file(conformance_out),
        )
        snapshot_path = self.artifacts.write_json(
            self.layout.relative(snapshot_root / "snapshot.json"),
            snapshot.model_dump(mode="json"),
        )
        return snapshot, snapshot_path

    def _snapshot_models(
        self, snapshot: AdapterOutputSnapshot
    ) -> tuple[
        AdapterBundleManifest,
        Path,
        StateGraphBaseline,
        AdapterConformanceReport,
    ]:
        pairs = (
            (snapshot.adapter_manifest_ref, snapshot.adapter_manifest_sha256),
            (snapshot.adapter_package_ref, snapshot.adapter_package_sha256),
            (snapshot.state_graph_ref, snapshot.state_graph_sha256),
            (snapshot.conformance_report_ref, snapshot.conformance_report_sha256),
        )
        for reference, expected in pairs:
            path = resolve_artifact_ref(self.artifacts.root, reference)
            if not path.is_file() or sha256_file(path) != expected:
                raise ValueError(f"adapter output snapshot hash mismatch: {reference}")
        bundle = _read_model(
            resolve_artifact_ref(self.artifacts.root, snapshot.adapter_manifest_ref),
            AdapterBundleManifest,
        )
        package_path = resolve_artifact_ref(self.artifacts.root, snapshot.adapter_package_ref)
        graph = _read_model(
            resolve_artifact_ref(self.artifacts.root, snapshot.state_graph_ref), StateGraphBaseline
        )
        conformance = _read_model(
            resolve_artifact_ref(self.artifacts.root, snapshot.conformance_report_ref),
            AdapterConformanceReport,
        )
        assert isinstance(bundle, AdapterBundleManifest)
        assert isinstance(graph, StateGraphBaseline)
        assert isinstance(conformance, AdapterConformanceReport)
        return bundle, package_path, graph, conformance

    def promote_run(
        self,
        run: AdapterAgentRun,
        snapshot: AdapterOutputSnapshot,
    ) -> tuple[AdapterHandoff, Path, AdaptGateReport, Path]:
        checks: list[str] = []
        published_release_root: Path | None = None
        gate_path = self.layout.stage_run("adapt", run.robot_id, run.run_id) / "gate.json"
        runtime_index = AdapterOutputLayout(self.output_root).current(run.robot_id)
        adapt_index = self.layout.stage_latest_index("adapt", run.robot_id)
        previous_runtime_index = runtime_index.read_bytes() if runtime_index.is_file() else None
        previous_adapt_index = adapt_index.read_bytes() if adapt_index.is_file() else None
        runtime_index_written = False
        adapt_index_written = False
        try:
            if run.status != AdapterAgentRunStatus.SUCCEEDED:
                raise ValueError("Adapter Agent run did not succeed")
            if (
                snapshot.run_id != run.run_id
                or snapshot.robot_id != run.robot_id
                or snapshot.discovery_id != run.source_discovery_id
            ):
                raise ValueError("adapter output snapshot identity mismatch")
            bundle, package_path, graph, conformance = self._snapshot_models(snapshot)
            checks.append("frozen output hashes and schemas")

            discovery = load_report(self.artifacts.root, run.robot_id, run.source_discovery_id)
            identified_outputs = (
                (graph, "State Graph"),
                (conformance, "conformance report"),
            )
            for value, label in identified_outputs:
                if value.robot_id != run.robot_id or value.discovery_id != run.source_discovery_id:
                    raise ValueError(f"{label} identity does not match the Adapter Agent run")
            checks.append("robot and discovery identity")

            expected_operations = required_conformance_operations(discovery)
            definitions_by_operation = {
                definition.operation: definition
                for definition in canonical_operation_registry().operations
            }
            source_by_operation = {
                tool.operation: tool for tool in materialize_active_catalog(discovery).tools
            }
            expected_bundle_operations = {
                candidate.operation for candidate in discovery.operation_candidates
            }
            bundle_entries = {item.operation: item for item in bundle.operations}
            if set(bundle_entries) != expected_bundle_operations:
                raise ValueError(
                    "adapter bundle operation coverage must exactly match generated candidates"
                )
            probe_adapter_package(package_path, bundle)
            checks.append("adapter package describe and entrypoint binding")
            actual = {item.operation: item for item in conformance.operations}
            if len(actual) != len(conformance.operations) or set(actual) != expected_operations:
                raise ValueError("conformance coverage must exactly match required operations")
            checks.append("product registry and required-operation coverage")
            active_report = ActiveDiscoveryReport.model_validate_json(
                resolve_artifact_ref(
                    self.artifacts.root, discovery.active_discovery_report_ref
                ).read_text(encoding="utf-8")
            )
            runtime_probe_requested = (
                active_report.inputs.get("active_probe") == ActiveProbeMode.RUNTIME_READONLY.value
            )
            candidates = {
                candidate.operation: candidate for candidate in discovery.operation_candidates
            }
            candidate_operations = set(candidates)
            for operation in expected_operations:
                definition = definitions_by_operation[operation]
                validate_definition_contract(definition)
                if operation in bundle_entries:
                    entry = bundle_entries[operation]
                    if (
                        entry.contract_version != definition.contract_version
                        or entry.contract_sha256 != definition.contract_sha256
                    ):
                        raise ValueError(f"adapter bundle contract binding mismatch: {operation}")
                source = source_by_operation[operation]
                check = actual[operation]
                if not check.agent_reported_passed:
                    raise ValueError(
                        f"Adapter Agent reported failed local static checks: {operation}"
                    )
                scopes = set(check.validation_scopes)
                if ConformanceScope.LOCAL_STATIC not in scopes:
                    raise ValueError(f"local static validation scope is missing: {operation}")
                target_required = operation in candidate_operations
                if target_required:
                    relevant_layer = "ros" if source.layer in {"ros", "app"} else source.layer
                    probe = discovery.probes.get(relevant_layer)
                    if not runtime_probe_requested or probe is None or probe.status != "SUCCEEDED":
                        raise ValueError(
                            f"target runtime evidence is unavailable for operation: {operation}"
                        )
                    if not _candidate_route_observed(candidates[operation], probe.data):
                        raise ValueError(f"target operation route was not observed: {operation}")
            checks.append("product-owned operation contracts")
            checks.append("Adapter Agent local-static declarations (advisory)")
            checks.append("target route existence without outcome execution")

            _, manifest_path = load_and_verify_discovery_manifest(
                self.artifacts.root, run.robot_id, run.source_discovery_id
            )
            checks.append("immutable discovery manifest")

            catalog = materialize_active_catalog(discovery, bundle=bundle)
            registry_operations = {
                item.operation for item in canonical_operation_registry().operations
            }
            catalog_by_operation = {tool.operation: tool for tool in catalog.tools}
            if (
                len(catalog_by_operation) != len(catalog.tools)
                or set(catalog_by_operation) != registry_operations
            ):
                raise ValueError("Active Tool Catalog must exactly match the product registry")
            for operation, entry in bundle_entries.items():
                descriptor = catalog_by_operation[operation]
                expected_adapter = f"bundle:{bundle.bundle_id}#{entry.entrypoint}"
                if descriptor.adapter != expected_adapter or descriptor.availability != "VERIFIED":
                    raise ValueError(f"adapter bundle binding mismatch: {operation}")
            for operation, descriptor in catalog_by_operation.items():
                definition = definitions_by_operation[operation]
                if (
                    descriptor.input_schema != definition.input_schema
                    or descriptor.output_schema != definition.output_schema
                    or descriptor.error_codes != definition.error_codes
                    or descriptor.risk != definition.risk
                    or descriptor.access != definition.access
                    or descriptor.idempotent != definition.idempotent
                    or descriptor.cancelable != definition.cancelable
                    or descriptor.contract_lifecycle
                    != definition.contract_lifecycle.value
                    or descriptor.contract_version != definition.contract_version
                    or descriptor.contract_sha256 != definition.contract_sha256
                    or descriptor.data_classification
                    != (
                        definition.data_classification.value
                        if definition.data_classification is not None
                        else None
                    )
                    or descriptor.result_semantics
                    != (
                        definition.result_semantics.value
                        if definition.result_semantics is not None
                        else None
                    )
                    or descriptor.observation_overhead
                    != definition.observation_overhead.value
                    or descriptor.execution_mode != definition.execution_mode.value
                    or descriptor.paired_operation != definition.paired_operation
                    or descriptor.replacement_operation != definition.replacement_operation
                    or descriptor.capability_requirements
                    != definition.capability_requirements
                    or descriptor.preconditions != definition.preconditions
                    or descriptor.postconditions != definition.postconditions
                    or descriptor.semantic_units != definition.semantic_units
                    or descriptor.coordinate_frames != definition.coordinate_frames
                    or descriptor.time_semantics != definition.time_semantics
                    or descriptor.side_effects != definition.side_effects
                    or descriptor.resource_locks != definition.resource_locks
                    or descriptor.rate_limit != definition.rate_limit
                    or descriptor.retry_policy != definition.retry_policy
                    or descriptor.compensation_operation
                    != definition.compensation_operation
                ):
                    raise ValueError(f"Tool Catalog contract differs from Registry: {operation}")
            if any(tool.availability == "DISCOVERED_UNVERIFIED" for tool in catalog.tools):
                raise ValueError("gated Tool Catalog still contains unverified operations")
            run_root = self.layout.stage_run("adapt", run.robot_id, run.run_id)
            catalog_out = self.artifacts.write_json(
                self.layout.relative(run_root / "gated-output" / "tool-catalog.json"),
                catalog.model_dump(mode="json"),
            )
            checks.append("gate-owned Active Tool Catalog composition")
            gate = AdaptGateReport(
                run_id=run.run_id,
                robot_id=run.robot_id,
                discovery_id=run.source_discovery_id,
                status=AdaptGateStatus.PASSED,
                checks=checks,
            )
            persisted_gate = self.artifacts.write_json(
                self.layout.relative(gate_path), gate.model_dump(mode="json")
            )
            _, release_manifest_path = publish_release(
                output_root=self.output_root,
                robot_id=run.robot_id,
                release_id=run.run_id,
                discovery_id=run.source_discovery_id,
                bundle_manifest_path=resolve_artifact_ref(
                    self.artifacts.root, snapshot.adapter_manifest_ref
                ),
                adapter_package_path=package_path,
                tool_catalog_path=catalog_out,
                state_graph_path=resolve_artifact_ref(
                    self.artifacts.root, snapshot.state_graph_ref
                ),
                conformance_path=resolve_artifact_ref(
                    self.artifacts.root, snapshot.conformance_report_ref
                ),
                gate_report_path=persisted_gate,
            )
            published_release_root = release_manifest_path.parent
            handoff = AdapterHandoff(
                robot_id=run.robot_id,
                source_discovery_id=run.source_discovery_id,
                source_agent_run_id=run.run_id,
                discovery_manifest_ref=self.layout.ref(manifest_path),
                discovery_manifest_sha256=sha256_file(manifest_path),
                tool_catalog_ref=self.layout.ref(catalog_out),
                tool_catalog_sha256=sha256_file(catalog_out),
                state_graph_ref=snapshot.state_graph_ref,
                state_graph_sha256=snapshot.state_graph_sha256,
                conformance_report_ref=snapshot.conformance_report_ref,
                conformance_report_sha256=snapshot.conformance_report_sha256,
                gate_report_ref=self.layout.ref(persisted_gate),
                gate_report_sha256=sha256_file(persisted_gate),
                release_ref=(f"output://robots/{run.robot_id}/releases/{run.run_id}/manifest.json"),
                release_manifest_sha256=sha256_file(release_manifest_path),
            )
            immutable_path = self.artifacts.write_json(
                self.layout.relative(run_root / "handoff.json"),
                handoff.model_dump(mode="json"),
            )
            validate_adapter_handoff(
                self.artifacts.root,
                run.robot_id,
                immutable_path,
                self.output_root,
            )
            latest = AdaptLatestIndex(
                robot_id=run.robot_id,
                run_id=run.run_id,
                handoff_ref=self.layout.ref(immutable_path),
                handoff_sha256=sha256_file(immutable_path),
            )
            self.artifacts.write_json(
                self.layout.relative(adapt_index),
                latest.model_dump(mode="json"),
            )
            adapt_index_written = True
            activate_release(self.output_root, run.robot_id, run.run_id)
            runtime_index_written = True
            validate_adapter_handoff(
                self.artifacts.root,
                run.robot_id,
                output_root=self.output_root,
            )
            _, active_release, _, _ = load_current_release(self.output_root, run.robot_id)
            if (
                active_release.release_id != run.run_id
                or active_release.discovery_id != run.source_discovery_id
            ):
                raise ValueError("activated adapter release identity mismatch")
            return handoff, immutable_path, gate, persisted_gate
        except (FileNotFoundError, OSError, ValueError) as exc:
            if runtime_index_written:
                _restore_index(runtime_index, previous_runtime_index)
            if adapt_index_written:
                _restore_index(adapt_index, previous_adapt_index)
            if published_release_root is not None:
                shutil.rmtree(published_release_root, ignore_errors=True)
            gate = AdaptGateReport(
                run_id=run.run_id,
                robot_id=run.robot_id,
                discovery_id=run.source_discovery_id,
                status=AdaptGateStatus.FAILED,
                checks=checks,
                error=str(exc),
            )
            self.artifacts.write_json(self.layout.relative(gate_path), gate.model_dump(mode="json"))
            raise
