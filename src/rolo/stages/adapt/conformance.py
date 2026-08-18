from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from rolo.core.artifacts import ArtifactStore
from rolo.core.hashing import sha256_file
from rolo.stages.adapt.discovery import load_report
from rolo.stages.adapt.models import (
    AdapterAgentResult,
    AdapterAgentRun,
    AdapterAgentRunStatus,
    AdapterConformanceReport,
    AdapterHandoff,
    AdapterOutputSnapshot,
    AdaptGateReport,
    AdaptGateStatus,
    AdaptLatestIndex,
    StateGraphBaseline,
    ToolCatalog,
)
from rolo.stages.artifact_paths import ArtifactLayout, resolve_artifact_ref
from rolo.stages.discovery_manifest import load_and_verify_discovery_manifest


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
    artifact_root: Path, robot_id: str, handoff_path: Path | None = None
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
        resolve_artifact_ref(artifact_root, handoff.gate_report_ref).read_text(
            encoding="utf-8"
        )
    )
    if gate.status != AdaptGateStatus.PASSED or gate.run_id != handoff.source_agent_run_id:
        raise ValueError("adapter handoff is not backed by a passed independent gate")
    return handoff


class AdapterPromotionService:
    """Freeze Agent outputs, independently validate them, and publish a handoff."""

    def __init__(self, artifacts: ArtifactStore) -> None:
        self.artifacts = artifacts
        self.layout = ArtifactLayout(artifacts.root)

    def snapshot(self, run: AdapterAgentRun) -> tuple[AdapterOutputSnapshot, Path]:
        if run.status != AdapterAgentRunStatus.SUCCEEDED:
            raise ValueError("Adapter Agent run is not successful")
        if not run.result_ref:
            raise ValueError("successful Adapter Agent run has no structured result")
        result_path = resolve_artifact_ref(self.artifacts.root, run.result_ref)
        result = AdapterAgentResult.model_validate_json(
            result_path.read_text(encoding="utf-8")
        )
        if not result.handoff_ready or result.blockers or result.outputs is None:
            raise ValueError("Adapter Agent result is not ready for independent conformance")

        workspace = Path(run.workspace)
        catalog_path = _workspace_output(workspace, result.outputs.tool_catalog)
        graph_path = _workspace_output(workspace, result.outputs.state_graph)
        conformance_path = _workspace_output(workspace, result.outputs.conformance_report)
        catalog = _read_model(catalog_path, ToolCatalog)
        graph = _read_model(graph_path, StateGraphBaseline)
        conformance = _read_model(conformance_path, AdapterConformanceReport)
        assert isinstance(catalog, ToolCatalog)
        assert isinstance(graph, StateGraphBaseline)
        assert isinstance(conformance, AdapterConformanceReport)

        identified_outputs = (
            (catalog, "tool catalog"),
            (graph, "State Graph"),
            (conformance, "conformance report"),
        )
        for value, label in identified_outputs:
            if value.robot_id != run.robot_id or value.discovery_id != run.source_discovery_id:
                raise ValueError(f"{label} identity does not match the Adapter Agent run")

        snapshot_root = self.layout.stage_run("adapt", run.robot_id, run.run_id) / "output-snapshot"
        catalog_out = self.artifacts.write_json(
            self.layout.relative(snapshot_root / "tool-catalog.json"),
            catalog.model_dump(mode="json"),
        )
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
            tool_catalog_ref=self.layout.ref(catalog_out),
            tool_catalog_sha256=sha256_file(catalog_out),
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
    ) -> tuple[ToolCatalog, StateGraphBaseline, AdapterConformanceReport]:
        pairs = (
            (snapshot.tool_catalog_ref, snapshot.tool_catalog_sha256),
            (snapshot.state_graph_ref, snapshot.state_graph_sha256),
            (snapshot.conformance_report_ref, snapshot.conformance_report_sha256),
        )
        for reference, expected in pairs:
            path = resolve_artifact_ref(self.artifacts.root, reference)
            if not path.is_file() or sha256_file(path) != expected:
                raise ValueError(f"adapter output snapshot hash mismatch: {reference}")
        catalog = _read_model(
            resolve_artifact_ref(self.artifacts.root, snapshot.tool_catalog_ref), ToolCatalog
        )
        graph = _read_model(
            resolve_artifact_ref(self.artifacts.root, snapshot.state_graph_ref), StateGraphBaseline
        )
        conformance = _read_model(
            resolve_artifact_ref(self.artifacts.root, snapshot.conformance_report_ref),
            AdapterConformanceReport,
        )
        assert isinstance(catalog, ToolCatalog)
        assert isinstance(graph, StateGraphBaseline)
        assert isinstance(conformance, AdapterConformanceReport)
        return catalog, graph, conformance

    def promote_run(
        self,
        run: AdapterAgentRun,
        snapshot: AdapterOutputSnapshot,
    ) -> tuple[AdapterHandoff, Path, AdaptGateReport, Path]:
        checks: list[str] = []
        gate_path = self.layout.stage_run("adapt", run.robot_id, run.run_id) / "gate.json"
        try:
            if run.status != AdapterAgentRunStatus.SUCCEEDED:
                raise ValueError("Adapter Agent run did not succeed")
            if (
                snapshot.run_id != run.run_id
                or snapshot.robot_id != run.robot_id
                or snapshot.discovery_id != run.source_discovery_id
            ):
                raise ValueError("adapter output snapshot identity mismatch")
            catalog, graph, conformance = self._snapshot_models(snapshot)
            checks.append("frozen output hashes and schemas")

            discovery = load_report(
                self.artifacts.root, run.robot_id, run.source_discovery_id
            )
            identified_outputs = (
                (catalog, "tool catalog"),
                (graph, "State Graph"),
                (conformance, "conformance report"),
            )
            for value, label in identified_outputs:
                if (
                    value.robot_id != run.robot_id
                    or value.discovery_id != run.source_discovery_id
                ):
                    raise ValueError(f"{label} identity does not match the Adapter Agent run")
            checks.append("robot and discovery identity")

            expected = {tool.operation: tool for tool in discovery.tool_catalog}
            actual = {item.operation: item for item in conformance.operations}
            if len(actual) != len(conformance.operations) or set(actual) != set(expected):
                raise ValueError("conformance coverage must exactly match discovered operations")
            catalog_ops = {tool.operation for tool in catalog.tools}
            if catalog_ops != set(expected):
                raise ValueError("verified tool catalog must exactly match discovered operations")
            checks.append("exact discovered-operation coverage")
            unverified = [
                tool.operation
                for tool in catalog.tools
                if tool.availability in {"DISCOVERED_UNVERIFIED", "UNAVAILABLE"}
            ]
            if unverified:
                raise ValueError(
                    f"tool catalog still contains unverified operations: {unverified}"
                )
            checks.append("no unverified operations remain")
            for operation, source in expected.items():
                check = actual[operation]
                if not check.passed:
                    raise ValueError(f"conformance failed for operation: {operation}")
                if (source.risk == "R3" or source.access == "write") and (
                    check.physical_result_valid is not True or not check.evidence
                ):
                    raise ValueError(
                        f"physical write operation lacks verified result evidence: {operation}"
                    )
            checks.append("operation conformance and physical write evidence")

            _, manifest_path = load_and_verify_discovery_manifest(
                self.artifacts.root, run.robot_id, run.source_discovery_id
            )
            checks.append("immutable discovery manifest")
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
            handoff = AdapterHandoff(
                robot_id=run.robot_id,
                source_discovery_id=run.source_discovery_id,
                source_agent_run_id=run.run_id,
                discovery_manifest_ref=self.layout.ref(manifest_path),
                discovery_manifest_sha256=sha256_file(manifest_path),
                tool_catalog_ref=snapshot.tool_catalog_ref,
                tool_catalog_sha256=snapshot.tool_catalog_sha256,
                state_graph_ref=snapshot.state_graph_ref,
                state_graph_sha256=snapshot.state_graph_sha256,
                conformance_report_ref=snapshot.conformance_report_ref,
                conformance_report_sha256=snapshot.conformance_report_sha256,
                gate_report_ref=self.layout.ref(persisted_gate),
                gate_report_sha256=sha256_file(persisted_gate),
            )
            run_root = self.layout.stage_run("adapt", run.robot_id, run.run_id)
            immutable_path = self.artifacts.write_json(
                self.layout.relative(run_root / "handoff.json"),
                handoff.model_dump(mode="json"),
            )
            validate_adapter_handoff(self.artifacts.root, run.robot_id, immutable_path)
            latest = AdaptLatestIndex(
                robot_id=run.robot_id,
                run_id=run.run_id,
                handoff_ref=self.layout.ref(immutable_path),
                handoff_sha256=sha256_file(immutable_path),
            )
            self.artifacts.write_json(
                self.layout.relative(
                    self.layout.stage_latest_index("adapt", run.robot_id)
                ),
                latest.model_dump(mode="json"),
            )
            validate_adapter_handoff(self.artifacts.root, run.robot_id)
            return handoff, immutable_path, gate, persisted_gate
        except (FileNotFoundError, OSError, ValueError) as exc:
            gate = AdaptGateReport(
                run_id=run.run_id,
                robot_id=run.robot_id,
                discovery_id=run.source_discovery_id,
                status=AdaptGateStatus.FAILED,
                checks=checks,
                error=str(exc),
            )
            self.artifacts.write_json(
                self.layout.relative(gate_path), gate.model_dump(mode="json")
            )
            raise
