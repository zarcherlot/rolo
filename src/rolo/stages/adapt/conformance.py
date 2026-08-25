from __future__ import annotations

import base64
import binascii
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
from rolo.core.hashing import sha256_bytes, sha256_file
from rolo.core.models import DiscoveryStatus
from rolo.core.persistence import atomic_write_text, interprocess_lock
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
    AdapterReleaseIndex,
    AdaptGateReport,
    AdaptGateStatus,
    AdaptLatestIndex,
    ConformanceScope,
    StateGraphBaseline,
)
from rolo.stages.adapt.operation_registry import (
    canonical_operation_registry,
    materialize_active_catalog,
    required_adapter_agent_conformance_operations,
    required_builtin_conformance_operations,
    validate_definition_contract,
)
from rolo.stages.adapt.routes import ROUTE_PROBE_LAYER, candidate_route_observed
from rolo.stages.adapt.state_graph import (
    build_state_graph_baseline,
    validate_state_graph_baseline,
)
from rolo.stages.adapt.target_fingerprint import (
    runtime_environment_from_report,
    target_fingerprint_sha256,
)
from rolo.stages.artifact_paths import ArtifactLayout, resolve_artifact_ref
from rolo.stages.discovery_manifest import load_and_verify_discovery_manifest


def _restore_index(path: Path, previous: bytes | None) -> None:
    """Compensate a failed cross-root publication without exposing a partial index."""
    if previous is None:
        path.unlink(missing_ok=True)
        return
    atomic_write_text(path, previous.decode("utf-8"))


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


def _workspace_bundle_files(
    workspace: Path, bundle: AdapterBundleManifest
) -> list[tuple[object, Path]]:
    root = workspace.expanduser().resolve()
    resolved: list[tuple[object, Path]] = []
    total_bytes = 0
    declared = bundle.declared_files()
    if len(declared) > 256:
        raise ValueError("adapter bundle exceeds the 256-file limit")
    for item in declared:
        raw = root / item.path
        if raw.is_symlink() or any(
            parent.is_symlink() for parent in raw.parents if parent != root.parent
        ):
            raise ValueError(f"adapter bundle file cannot be a symlink: {item.path}")
        path = _workspace_output(workspace, item.path)
        if sha256_file(path) != item.sha256:
            raise ValueError(f"adapter bundle file digest mismatch: {item.path}")
        total_bytes += path.stat().st_size
        if total_bytes > 512 * 1024 * 1024:
            raise ValueError("adapter bundle exceeds the 512 MiB total size limit")
        resolved.append((item, path))
    return resolved


def _read_model(path: Path, model: type[BaseModel]) -> BaseModel:
    try:
        return model.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"invalid {model.__name__} at {path}: {exc}") from exc


def _structured_output_files(result: AdapterAgentResult) -> dict[str, bytes]:
    if len(result.files) > 256:
        raise ValueError("Adapter Agent structured handoff exceeds the 256-file limit")
    decoded: dict[str, bytes] = {}
    total_bytes = 0
    for item in result.files:
        candidate = Path(item.path)
        if candidate.is_absolute() or ".." in candidate.parts or not candidate.parts:
            raise ValueError(f"Adapter Agent file path is unsafe: {item.path}")
        normalized = candidate.as_posix()
        if normalized in decoded:
            raise ValueError(f"Adapter Agent file path is duplicated: {item.path}")
        try:
            payload = base64.b64decode(item.content, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError(f"Adapter Agent file is not valid base64: {item.path}") from exc
        if len(payload) > 16 * 1024 * 1024:
            raise ValueError(f"Adapter Agent file exceeds the 16 MiB handoff limit: {item.path}")
        total_bytes += len(payload)
        if total_bytes > 64 * 1024 * 1024:
            raise ValueError("Adapter Agent structured handoff exceeds the 64 MiB total limit")
        if sha256_bytes(payload) != item.sha256:
            raise ValueError(f"Adapter Agent structured file digest mismatch: {item.path}")
        decoded[normalized] = payload
    return decoded


def _payload(decoded: dict[str, bytes], relative: str) -> bytes:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"adapter output must be workspace-relative: {relative}")
    try:
        return decoded[candidate.as_posix()]
    except KeyError as exc:
        raise ValueError(f"adapter output is missing from structured handoff: {relative}") from exc


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
        decoded = _structured_output_files(result) if result.files else {}
        bundle_manifest_payload: bytes | None = None
        bundle_payloads: list[tuple[object, bytes]] | None = None
        if decoded:
            bundle_manifest_payload = _payload(decoded, result.outputs.adapter_manifest)
            adapter_package_payload = _payload(decoded, result.outputs.adapter_package)
            graph_payload = _payload(decoded, result.outputs.state_graph)
            conformance_payload = _payload(decoded, result.outputs.conformance_report)
            bundle = AdapterBundleManifest.model_validate_json(bundle_manifest_payload)
            graph = StateGraphBaseline.model_validate_json(graph_payload)
            conformance = AdapterConformanceReport.model_validate_json(conformance_payload)
            bundle_payloads = []
            total_bytes = 0
            for item in bundle.declared_files():
                payload = _payload(decoded, item.path)
                if sha256_bytes(payload) != item.sha256:
                    raise ValueError(f"adapter bundle file digest mismatch: {item.path}")
                total_bytes += len(payload)
                if total_bytes > 512 * 1024 * 1024:
                    raise ValueError("adapter bundle exceeds the 512 MiB total size limit")
                bundle_payloads.append((item, payload))
            entry_payload = next(
                payload for item, payload in bundle_payloads if item.role == "ENTRYPOINT"
            )
            if entry_payload != adapter_package_payload:
                raise ValueError("adapter result entrypoint does not match the bundle file payload")
        else:
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
        if Path(bundle.package_file).as_posix() != Path(result.outputs.adapter_package).as_posix():
            raise ValueError("adapter bundle package_file does not match the proposed package")
        if decoded:
            if sha256_bytes(adapter_package_payload) != bundle.package_sha256:
                raise ValueError("adapter package hash does not match its bundle manifest")
        else:
            if sha256_file(adapter_package_path) != bundle.package_sha256:
                raise ValueError("adapter package hash does not match its bundle manifest")
            bundle_files = _workspace_bundle_files(workspace, bundle)
            entry_path = next(path for item, path in bundle_files if item.role == "ENTRYPOINT")
            if entry_path != adapter_package_path:
                raise ValueError(
                    "adapter result entrypoint does not match the bundle file manifest"
                )
        bundle_operations = [item.operation for item in bundle.operations]
        if len(bundle_operations) != len(set(bundle_operations)):
            raise ValueError("adapter bundle contains duplicate operations")
        discovery = load_report(self.artifacts.root, run.robot_id, run.source_discovery_id)
        expected_bundle_operations = required_adapter_agent_conformance_operations(discovery)
        if not expected_bundle_operations:
            raise ValueError("no target-observed adapter operations are eligible for promotion")
        if set(bundle_operations) != expected_bundle_operations:
            raise ValueError(
                "adapter bundle operation coverage must exactly match eligible operations"
            )
        graph = build_state_graph_baseline(discovery, bundle)
        identified_outputs = ((graph, "State Graph"), (conformance, "conformance report"))
        for value, label in identified_outputs:
            if value.robot_id != run.robot_id or value.discovery_id != run.source_discovery_id:
                raise ValueError(f"{label} identity does not match the Adapter Agent run")

        snapshot_root = self.layout.stage_run("adapt", run.robot_id, run.run_id) / "output-snapshot"
        bundle_manifest_out = snapshot_root / "adapter-manifest.json"
        snapshot_root.mkdir(parents=True, exist_ok=True)
        if bundle_manifest_payload is not None:
            bundle_manifest_out.write_bytes(bundle_manifest_payload)
        else:
            shutil.copy2(bundle_manifest_path, bundle_manifest_out)
        snapshot_files = []
        adapter_package_out: Path | None = None
        sources = bundle_payloads if bundle_payloads is not None else bundle_files
        for item, source in sources:
            destination = snapshot_root / "adapter-files" / item.path
            destination.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(source, bytes):
                destination.write_bytes(source)
            else:
                shutil.copy2(source, destination)
            snapshot_files.append(
                {
                    "path": self.layout.ref(destination),
                    "sha256": item.sha256,
                    "role": item.role,
                }
            )
            if item.role == "ENTRYPOINT":
                adapter_package_out = destination
        assert adapter_package_out is not None
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
            adapter_files=snapshot_files,
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
            *[(item.path, item.sha256) for item in snapshot.adapter_files],
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
        declared = bundle.declared_files()
        if len(snapshot.adapter_files) != len(declared) or any(
            published.sha256 != expected.sha256 or published.role != expected.role
            for expected, published in zip(declared, snapshot.adapter_files, strict=True)
        ):
            raise ValueError("adapter output snapshot file manifest differs from bundle")
        return bundle, package_path, graph, conformance

    def promote_run(
        self,
        run: AdapterAgentRun,
        snapshot: AdapterOutputSnapshot,
    ) -> tuple[AdapterHandoff, Path, AdaptGateReport, Path]:
        promotion_lock = self.layout.stage_latest_index("adapt", run.robot_id).with_name(
            "promotion"
        )
        with interprocess_lock(promotion_lock, timeout_s=30.0):
            return self._promote_run_locked(run, snapshot)

    def _promote_run_locked(
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
        expected_current_release_id = (
            AdapterReleaseIndex.model_validate_json(previous_runtime_index).release_id
            if previous_runtime_index is not None
            else None
        )
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
            validate_state_graph_baseline(graph, discovery, bundle)
            checks.append("Rolo-owned State Graph identity, binding, and route coverage")

            expected_agent_operations = required_adapter_agent_conformance_operations(discovery)
            expected_builtin_operations = required_builtin_conformance_operations()
            definitions_by_operation = {
                definition.operation: definition
                for definition in canonical_operation_registry().operations
            }
            expected_bundle_operations = required_adapter_agent_conformance_operations(discovery)
            if not expected_bundle_operations:
                raise ValueError("no target-observed adapter operations are eligible for promotion")
            runtime_environment = runtime_environment_from_report(
                discovery,
                operations=expected_bundle_operations,
            )
            bundle_entries = {item.operation: item for item in bundle.operations}
            if set(bundle_entries) != expected_bundle_operations:
                raise ValueError(
                    "adapter bundle operation coverage must exactly match eligible operations"
                )
            probe_adapter_package(
                package_path,
                bundle,
                runtime_environment=runtime_environment,
            )
            checks.append("adapter package describe and entrypoint binding")
            actual = {item.operation: item for item in conformance.operations}
            if (
                len(actual) != len(conformance.operations)
                or set(actual) != expected_agent_operations
            ):
                raise ValueError(
                    "Adapter Agent conformance coverage must exactly match bundle candidates"
                )
            checks.append("Adapter Agent bundle-candidate coverage")
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
            for operation in expected_builtin_operations:
                definition = definitions_by_operation[operation]
                validate_definition_contract(definition)
            checks.append("Rolo-owned builtin operation contracts")

            for operation in expected_agent_operations:
                definition = definitions_by_operation[operation]
                validate_definition_contract(definition)
                if operation in bundle_entries:
                    entry = bundle_entries[operation]
                    if (
                        entry.contract_version != definition.contract_version
                        or entry.contract_sha256 != definition.contract_sha256
                    ):
                        raise ValueError(f"adapter bundle contract binding mismatch: {operation}")
                check = actual[operation]
                if not check.agent_reported_passed:
                    raise ValueError(
                        f"Adapter Agent reported failed local static checks: {operation}"
                    )
                scopes = set(check.validation_scopes)
                if ConformanceScope.LOCAL_STATIC not in scopes:
                    raise ValueError(f"local static validation scope is missing: {operation}")
                candidate = candidates[operation]
                required_layers = {
                    ROUTE_PROBE_LAYER[route.kind] for route in candidate.route_evidence
                }
                available_layers = {
                    layer
                    for layer in required_layers
                    if (probe := discovery.probes.get(layer)) is not None
                    and probe.status
                    in {DiscoveryStatus.SUCCEEDED, DiscoveryStatus.PARTIAL}
                    and (layer != "ros" or runtime_probe_requested)
                }
                if not available_layers:
                    raise ValueError(
                        f"target runtime evidence is unavailable for operation: {operation}"
                    )
                if not candidate_route_observed(candidate, discovery.probes):
                    raise ValueError(f"target operation route was not observed: {operation}")
            checks.append("product-owned operation contracts")
            checks.append("Adapter Agent bundle local-static declarations (advisory)")
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
                    or descriptor.requires_quiescence
                    != definition.requires_quiescence
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
                target_fingerprint_sha256=target_fingerprint_sha256(
                    discovery,
                    self.artifacts.root,
                    operations=[entry.operation for entry in bundle.operations],
                ),
                runtime_environment=runtime_environment,
                bundle_manifest_path=resolve_artifact_ref(
                    self.artifacts.root, snapshot.adapter_manifest_ref
                ),
                adapter_package_path=package_path,
                adapter_files=[
                    (
                        declared.path,
                        resolve_artifact_ref(self.artifacts.root, published.path),
                        declared.role,
                    )
                    for declared, published in zip(
                        bundle.declared_files(), snapshot.adapter_files, strict=True
                    )
                ],
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
            activate_release(
                self.output_root,
                run.robot_id,
                run.run_id,
                artifact_root=self.artifacts.root,
                expected_current_release_id=expected_current_release_id,
            )
            runtime_index_written = True
            validate_adapter_handoff(
                self.artifacts.root,
                run.robot_id,
                output_root=self.output_root,
            )
            _, active_release, _, _ = load_current_release(
                self.output_root,
                run.robot_id,
                artifact_root=self.artifacts.root,
            )
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
