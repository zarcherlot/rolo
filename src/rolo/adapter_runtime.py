from __future__ import annotations

import json
import re
import shutil
import sys
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from rolo.adapter_runner import AdapterRunner, BoundedAdapterRunner
from rolo.core.hashing import sha256_file
from rolo.core.persistence import atomic_write_text, interprocess_lock
from rolo.invocation_policy import (
    authorize_invocation,
    validate_config_mutation_input,
    validate_config_mutation_result,
    validate_content_result,
    validate_digest_pinned_mutation_input,
    write_adapter_execution_audit,
)
from rolo.runtime_context import AdapterRuntimeContext
from rolo.schema_subset import validate_object
from rolo.stages.adapt.models import (
    AdapterBundleManifest,
    AdapterConformanceReport,
    AdapterReleaseIndex,
    AdapterReleaseManifest,
    AdaptGateReport,
    AdaptGateStatus,
    PublishedAdapterFile,
    StateGraphBaseline,
    ToolCatalog,
)


def _safe_segment(value: str, label: str) -> str:
    if not value or any(
        character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
        for character in value
    ):
        raise ValueError(f"invalid {label}: {value!r}")
    return value


def _relative_file(root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"unsafe adapter release path: {relative}")
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"adapter release path escapes release root: {relative}") from exc
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    return resolved


def operation_route_binding_document(
    graph: StateGraphBaseline,
    operation: str,
    *,
    semantic_bindings: list[str] | None = None,
) -> dict[str, Any]:
    """Build the immutable runtime route-binding ABI from the gated graph."""

    operation_node = f"operation:{operation}"
    nodes = {str(node.get("id", "")): node for node in graph.nodes}
    if nodes.get(operation_node, {}).get("operation") != operation:
        raise ValueError(f"State Graph lacks operation route binding: {operation}")
    route_ids = {
        str(edge.get("target", ""))
        for edge in graph.edges
        if edge.get("source") == operation_node and edge.get("relation") == "routes_to"
    }
    bindings: list[dict[str, Any]] = []
    for route_id in sorted(route_ids):
        route = nodes.get(route_id, {})
        if route.get("kind") != "route":
            raise ValueError(f"State Graph operation has invalid route node: {operation}")
        bindings.append(
            {
                "operation": operation,
                "route_id": route_id,
                "resource_id": route.get("resource_id"),
                "kind": route.get("route_kind"),
                "endpoint": route.get("endpoint"),
                "interface_type": route.get("interface_type"),
                "interface_schema_sha256": route.get("interface_schema_sha256"),
                "provider_id": route.get("provider_id"),
                "runtime_revision": route.get("runtime_revision"),
                "evidence_origin": route.get("evidence_origin"),
                "semantic_bindings": list(route.get("semantic_bindings", [])),
            }
        )
    if not bindings:
        raise ValueError(f"State Graph operation has no route bindings: {operation}")
    graph_semantic_bindings = sorted(
        {
            str(value)
            for binding in bindings
            for value in binding["semantic_bindings"]
            if value
        }
    )
    supplied_semantic_bindings = sorted(set(semantic_bindings or graph_semantic_bindings))
    if supplied_semantic_bindings != graph_semantic_bindings:
        raise ValueError(f"State Graph semantic binding mismatch: {operation}")
    return {
        "schema_version": "rolo-target-route-bindings/v1",
        "robot_id": graph.robot_id,
        "operation": operation,
        "semantic_bindings": supplied_semantic_bindings,
        "bindings": bindings,
    }


_ROUTE_SELECTOR_KEYS = ("resource_id", "route_id", "endpoint", "topic", "id", "camera")
_ROUTE_IDENTITY_FIELDS = ("route_id", "resource_id", "endpoint")


def _selector_tokens(value: object) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", str(value).casefold()))


def resolve_route_binding(
    document: Mapping[str, Any], payload: Mapping[str, Any]
) -> dict[str, Any] | None:
    """Resolve a request to one gated route, failing closed on ambiguity."""

    bindings = document.get("bindings")
    if not isinstance(bindings, list) or len(bindings) <= 1:
        if isinstance(bindings, list) and len(bindings) == 1 and isinstance(bindings[0], Mapping):
            return dict(bindings[0])
        return None
    candidates = [dict(binding) for binding in bindings if isinstance(binding, Mapping)]
    selectors = [
        (key, str(payload[key]).strip())
        for key in _ROUTE_SELECTOR_KEYS
        if isinstance(payload.get(key), str) and str(payload[key]).strip()
    ]
    if not selectors:
        raise ValueError(
            "operation has multiple target routes; an explicit route selector is required"
        )
    for _key, value in selectors:
        exact = [
            binding
            for binding in candidates
            if any(value == str(binding.get(field, "")).strip() for field in _ROUTE_IDENTITY_FIELDS)
        ]
        if len(exact) == 1:
            return exact[0]
        if len(exact) > 1:
            raise ValueError("operation route selector is ambiguous")
    for _key, value in selectors:
        value_tokens = _selector_tokens(value)
        if not value_tokens:
            continue
        token_matches = [
            binding
            for binding in candidates
            if value_tokens
            <= set().union(
                *(_selector_tokens(binding.get(field, "")) for field in _ROUTE_IDENTITY_FIELDS)
            )
        ]
        if len(token_matches) == 1:
            return token_matches[0]
        if len(token_matches) > 1:
            raise ValueError("operation route selector is ambiguous")
    raise ValueError("operation route selector does not match a gated route")


def require_route_selector(
    document: Mapping[str, Any], payload: Mapping[str, Any]
) -> dict[str, Any] | None:
    """Require an explicit selector whenever an operation has multiple routes."""

    return resolve_route_binding(document, payload)


def _load_release_manifest(path: Path) -> AdapterReleaseManifest:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("adapter release manifest is not valid JSON") from exc
    if not isinstance(raw, dict) or raw.get("schema_version") != "robot-adapter-release/v2":
        raise ValueError("legacy adapter releases cannot be loaded for runtime use")
    return AdapterReleaseManifest.model_validate(raw)


@dataclass(frozen=True)
class AdapterOutputLayout:
    root: Path

    def robot_root(self, robot_id: str) -> Path:
        return self.root / "robots" / _safe_segment(robot_id, "robot_id")

    def release(self, robot_id: str, release_id: str) -> Path:
        return self.robot_root(robot_id) / "releases" / _safe_segment(release_id, "release_id")

    def current(self, robot_id: str) -> Path:
        return self.robot_root(robot_id) / "current.json"


class StaleAdapterReleaseError(ValueError):
    """A hash-valid current release that no longer matches target evidence."""

    def __init__(
        self,
        message: str,
        *,
        release_root: Path,
        release: AdapterReleaseManifest,
        bundle: AdapterBundleManifest,
        catalog: ToolCatalog,
    ) -> None:
        super().__init__(message)
        self.release_root = release_root
        self.release = release
        self.bundle = bundle
        self.catalog = catalog


def _load_verified_release(
    layout: AdapterOutputLayout,
    robot_id: str,
    release_id: str,
    *,
    manifest_relative: str = "manifest.json",
    expected_manifest_sha256: str | None = None,
) -> tuple[Path, AdapterReleaseManifest, AdapterBundleManifest, ToolCatalog]:
    """Load one published release through the complete immutable-artifact checks."""
    release_root = layout.release(robot_id, release_id)
    manifest_path = _relative_file(release_root, manifest_relative)
    if (
        expected_manifest_sha256 is not None
        and sha256_file(manifest_path) != expected_manifest_sha256
    ):
        raise ValueError("adapter release manifest hash mismatch")
    release = _load_release_manifest(manifest_path)
    if release.robot_id != robot_id or release.release_id != release_id:
        raise ValueError("adapter release identity mismatch")
    checks = (
        (release.bundle_manifest, release.bundle_manifest_sha256),
        (release.adapter_package, release.adapter_package_sha256),
        (release.tool_catalog, release.tool_catalog_sha256),
        (release.state_graph, release.state_graph_sha256),
        (release.conformance_report, release.conformance_report_sha256),
        (release.gate_report, release.gate_report_sha256),
    )
    for relative, expected in checks:
        if sha256_file(_relative_file(release_root, relative)) != expected:
            raise ValueError(f"adapter release file hash mismatch: {relative}")
    for item in release.adapter_files:
        if sha256_file(_relative_file(release_root, item.path)) != item.sha256:
            raise ValueError(f"adapter release file hash mismatch: {item.path}")
    bundle = AdapterBundleManifest.model_validate_json(
        _relative_file(release_root, release.bundle_manifest).read_text(encoding="utf-8")
    )
    catalog = ToolCatalog.model_validate_json(
        _relative_file(release_root, release.tool_catalog).read_text(encoding="utf-8")
    )
    state_graph = StateGraphBaseline.model_validate_json(
        _relative_file(release_root, release.state_graph).read_text(encoding="utf-8")
    )
    conformance = AdapterConformanceReport.model_validate_json(
        _relative_file(release_root, release.conformance_report).read_text(encoding="utf-8")
    )
    gate = AdaptGateReport.model_validate_json(
        _relative_file(release_root, release.gate_report).read_text(encoding="utf-8")
    )
    if bundle.robot_id != robot_id or bundle.discovery_id != release.discovery_id:
        raise ValueError("adapter bundle identity mismatch")
    if catalog.robot_id != robot_id or catalog.discovery_id != release.discovery_id:
        raise ValueError("active Tool Catalog identity mismatch")
    if state_graph.robot_id != robot_id or state_graph.discovery_id != release.discovery_id:
        raise ValueError("adapter State Graph identity mismatch")
    if conformance.robot_id != robot_id or conformance.discovery_id != release.discovery_id:
        raise ValueError("adapter conformance identity mismatch")
    if (
        gate.robot_id != robot_id
        or gate.discovery_id != release.discovery_id
        or gate.run_id != release_id
        or gate.status != AdaptGateStatus.PASSED
    ):
        raise ValueError("adapter release lacks a matching passed gate report")
    if bundle.package_sha256 != release.adapter_package_sha256:
        raise ValueError("adapter bundle and release package hashes differ")
    published_files = {
        Path(item.path).relative_to("adapter").as_posix(): item
        for item in release.adapter_files
    }
    if published_files:
        declared_files = {item.path: item for item in bundle.declared_files()}
        if set(published_files) != set(declared_files):
            raise ValueError("adapter bundle and release file manifests differ")
        for path, declared in declared_files.items():
            published = published_files[path]
            if published.sha256 != declared.sha256 or published.role != declared.role:
                raise ValueError(f"adapter bundle file binding mismatch: {path}")
    descriptors = {item.operation: item for item in catalog.tools}
    for entry in bundle.operations:
        descriptor = descriptors.get(entry.operation)
        if descriptor is None:
            raise ValueError(
                f"adapter bundle operation missing from Tool Catalog: {entry.operation}"
            )
        if (
            descriptor.contract_version != entry.contract_version
            or descriptor.contract_sha256 != entry.contract_sha256
        ):
            raise ValueError(f"adapter contract binding mismatch: {entry.operation}")
        if descriptor.availability != "VERIFIED" or descriptor.adapter != (
            f"bundle:{bundle.bundle_id}#{entry.entrypoint}"
        ):
            raise ValueError(f"adapter catalog binding mismatch: {entry.operation}")
    bundled_operations = {entry.operation for entry in bundle.operations}
    unexpected_verified = sorted(
        descriptor.operation
        for descriptor in catalog.tools
        if descriptor.availability == "VERIFIED"
        and descriptor.operation not in bundled_operations
    )
    if unexpected_verified:
        raise ValueError(
            f"Tool Catalog verifies operations absent from adapter bundle: {unexpected_verified}"
        )
    return release_root, release, bundle, catalog


def _verify_release_freshness(
    release_root: Path,
    release: AdapterReleaseManifest,
    bundle: AdapterBundleManifest,
    catalog: ToolCatalog,
    *,
    artifact_root: Path,
) -> None:
    from rolo.stages.adapt.discovery import load_latest_report
    from rolo.stages.adapt.target_fingerprint import target_fingerprint_sha256

    latest = load_latest_report(artifact_root, release.robot_id)
    try:
        current_fingerprint = target_fingerprint_sha256(
            latest,
            artifact_root,
            operations=[entry.operation for entry in bundle.operations],
        )
    except ValueError as exc:
        raise StaleAdapterReleaseError(
            f"adapter release cannot match latest target evidence: {exc}",
            release_root=release_root,
            release=release,
            bundle=bundle,
            catalog=catalog,
        ) from exc
    if current_fingerprint != release.target_fingerprint_sha256:
        raise StaleAdapterReleaseError(
            "adapter release is stale for the latest target evidence",
            release_root=release_root,
            release=release,
            bundle=bundle,
            catalog=catalog,
        )


def load_current_release(
    output_root: Path,
    robot_id: str,
    *,
    artifact_root: Path,
) -> tuple[Path, AdapterReleaseManifest, AdapterBundleManifest, ToolCatalog]:
    layout = AdapterOutputLayout(output_root)
    index_path = layout.current(robot_id)
    index = AdapterReleaseIndex.model_validate_json(index_path.read_text(encoding="utf-8"))
    if index.robot_id != robot_id:
        raise ValueError("adapter release index robot identity mismatch")
    release_root, release, bundle, catalog = _load_verified_release(
        layout,
        robot_id,
        index.release_id,
        manifest_relative=index.manifest,
        expected_manifest_sha256=index.manifest_sha256,
    )
    _verify_release_freshness(
        release_root,
        release,
        bundle,
        catalog,
        artifact_root=artifact_root,
    )
    return release_root, release, bundle, catalog


def invoke_adapter(
    output_root: Path,
    robot_id: str,
    operation: str,
    payload: dict[str, Any],
    *,
    artifact_root: Path,
    timeout_s: float = 30.0,
    policy_path: Path | None = None,
    audit_path: Path | None = None,
    r3_authorizer_path: Path | None = None,
    quiescence_provider_path: Path | None = None,
    runner: AdapterRunner | None = None,
    expected_release_id: str | None = None,
    expected_target_fingerprint_sha256: str | None = None,
    expected_tool_catalog_sha256: str | None = None,
    expected_state_graph_sha256: str | None = None,
) -> dict[str, Any]:
    """Invoke one catalogued operation through the immutable adapter RPC bundle."""
    release_root, release, bundle, catalog = load_current_release(
        output_root, robot_id, artifact_root=artifact_root
    )
    expected_release_identity = (
        expected_release_id,
        expected_target_fingerprint_sha256,
        expected_tool_catalog_sha256,
        expected_state_graph_sha256,
    )
    actual_release_identity = (
        release.release_id,
        release.target_fingerprint_sha256,
        release.tool_catalog_sha256,
        release.state_graph_sha256,
    )
    for expected, actual, label in zip(
        expected_release_identity,
        actual_release_identity,
        (
            "release ID",
            "target fingerprint",
            "Tool Catalog",
            "State Graph",
        ),
        strict=True,
    ):
        if expected is not None and expected != actual:
            raise ValueError(f"active adapter {label} does not match the pinned invocation")
    descriptor = next((tool for tool in catalog.tools if tool.operation == operation), None)
    if descriptor is None:
        raise ValueError(f"operation is not in the active Tool Catalog: {operation}")
    if descriptor.availability != "VERIFIED":
        raise ValueError(f"operation is not verified for adapter invocation: {operation}")
    entry = next((item for item in bundle.operations if item.operation == operation), None)
    if entry is None:
        raise ValueError(f"operation has no adapter bundle entrypoint: {operation}")
    expected_adapter = f"bundle:{bundle.bundle_id}#{entry.entrypoint}"
    if descriptor.adapter != expected_adapter:
        raise ValueError(f"Tool Catalog adapter binding mismatch: {operation}")
    if (
        descriptor.contract_version != entry.contract_version
        or descriptor.contract_sha256 != entry.contract_sha256
    ):
        raise ValueError(f"adapter contract binding mismatch: {operation}")
    _validate_object_schema(payload, descriptor.input_schema, "adapter input")
    validate_config_mutation_input(
        descriptor,
        payload=payload,
        artifact_root=artifact_root,
    )
    validate_digest_pinned_mutation_input(
        descriptor,
        payload=payload,
        artifact_root=artifact_root,
    )
    state_graph = StateGraphBaseline.model_validate_json(
        _relative_file(release_root, release.state_graph).read_text(encoding="utf-8")
    )
    # Releases produced before the Rolo-owned route graph was populated may
    # still carry a validated, empty v1 graph. Preserve their existing
    # single-route invocation ABI; new graphs get strict route selection.
    route_document: dict[str, Any] | None = None
    if any(
        node.get("id") == f"operation:{operation}"
        for node in state_graph.nodes
        if isinstance(node, Mapping)
    ):
        route_document = operation_route_binding_document(state_graph, operation)
        selected_route = require_route_selector(route_document, payload)
        if selected_route is not None:
            route_document["selected_route_id"] = selected_route.get("route_id")
    effective_audit_path = audit_path or artifact_root / "runtime/invocation-audit.jsonl"
    authorize_invocation(
        descriptor,
        robot_id=robot_id,
        policy_path=policy_path,
        audit_path=effective_audit_path,
        payload=payload,
        r3_authorizer_path=r3_authorizer_path,
        quiescence_provider_path=quiescence_provider_path,
        required_quiescence_s=min(timeout_s, descriptor.max_duration_s) + 5,
    )
    package_path = _relative_file(release_root, release.adapter_package)
    invocation_id = f"invoke-{uuid4().hex}"
    write_adapter_execution_audit(
        effective_audit_path,
        invocation_id=invocation_id,
        robot_id=robot_id,
        operation=operation,
        release_id=release.release_id,
        payload=payload,
        outcome="STARTED",
    )
    started = time.monotonic()
    try:
        runtime_environment = release.runtime_environment.as_environment()
        if route_document is not None:
            runtime_environment["ROLO_TARGET_ROUTE_BINDINGS_JSON"] = json.dumps(
                route_document,
                ensure_ascii=False,
                separators=(",", ":"),
            )
        completed = (runner or BoundedAdapterRunner()).run(
            adapter_command(package_path)
            + ["invoke", "--operation", operation, "--entrypoint", entry.entrypoint],
            stdin=json.dumps(payload, ensure_ascii=False),
            cwd=release_root,
            timeout_s=min(timeout_s, descriptor.max_duration_s),
            runtime_environment=runtime_environment,
        )
    except Exception:
        write_adapter_execution_audit(
            effective_audit_path,
            invocation_id=invocation_id,
            robot_id=robot_id,
            operation=operation,
            release_id=release.release_id,
            payload=payload,
            outcome="FAILED",
            duration_s=time.monotonic() - started,
            error_code="RUNNER_ERROR",
        )
        raise
    if completed.timed_out:
        write_adapter_execution_audit(
            effective_audit_path,
            invocation_id=invocation_id,
            robot_id=robot_id,
            operation=operation,
            release_id=release.release_id,
            payload=payload,
            outcome="TIMED_OUT",
            duration_s=time.monotonic() - started,
            error_code="ADAPTER_TIMEOUT",
        )
        raise RuntimeError("adapter invocation timed out")
    if completed.output_limited:
        write_adapter_execution_audit(
            effective_audit_path,
            invocation_id=invocation_id,
            robot_id=robot_id,
            operation=operation,
            release_id=release.release_id,
            payload=payload,
            outcome="OUTPUT_LIMITED",
            duration_s=time.monotonic() - started,
            error_code="OUTPUT_LIMIT",
        )
        raise RuntimeError("adapter invocation exceeded its output limit")
    if completed.returncode != 0:
        write_adapter_execution_audit(
            effective_audit_path,
            invocation_id=invocation_id,
            robot_id=robot_id,
            operation=operation,
            release_id=release.release_id,
            payload=payload,
            outcome="FAILED",
            duration_s=time.monotonic() - started,
            error_code="NONZERO_EXIT",
        )
        raise RuntimeError(
            f"adapter invocation failed with code {completed.returncode}: "
            f"{completed.stderr.strip()[:1000]}"
        )
    try:
        result = json.loads(completed.stdout)
        if not isinstance(result, dict):
            raise RuntimeError("adapter result must be a JSON object")
        _validate_object_schema(result, descriptor.output_schema, "adapter output")
        validate_content_result(descriptor, payload=payload, result=result)
        validate_config_mutation_result(descriptor, result=result)
    except (json.JSONDecodeError, RuntimeError, ValueError) as exc:
        write_adapter_execution_audit(
            effective_audit_path,
            invocation_id=invocation_id,
            robot_id=robot_id,
            operation=operation,
            release_id=release.release_id,
            payload=payload,
            outcome="INVALID_RESULT",
            duration_s=time.monotonic() - started,
            error_code="INVALID_RESULT",
        )
        if isinstance(exc, json.JSONDecodeError):
            raise RuntimeError("adapter returned invalid JSON") from exc
        raise
    write_adapter_execution_audit(
        effective_audit_path,
        invocation_id=invocation_id,
        robot_id=robot_id,
        operation=operation,
        release_id=release.release_id,
        payload=payload,
        outcome="SUCCEEDED",
        result=result,
        duration_s=time.monotonic() - started,
    )
    return result


def _validate_object_schema(value: dict[str, Any], schema: dict[str, Any], label: str) -> None:
    validate_object(value, schema, label)


def adapter_command(package_path: Path) -> list[str]:
    """Return an argv-only launcher for a standalone executable or Python adapter package."""
    if package_path.suffix.lower() in {".py", ".pyz"}:
        return [sys.executable, str(package_path)]
    return [str(package_path)]


def _structured_adapter_error(stdout: str, stderr: str) -> str:
    """Return a bounded diagnostic, preferring a structured adapter error."""
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        payload = None
    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict):
        parts = [
            str(value).strip()
            for value in (error.get("code"), error.get("message"))
            if value is not None and str(value).strip()
        ]
        if parts:
            return ": ".join(parts)[:1000]
    diagnostic = stderr.strip()
    return diagnostic[:1000] if diagnostic else "target CLI returned no diagnostic"


def _probe_cli_help(
    package_path: Path,
    endpoints: list[str],
    *,
    timeout_s: float,
    runner: AdapterRunner,
    runtime_environment: Mapping[str, str] | None,
) -> None:
    """Run each gated CLI endpoint's bounded, read-only help command."""
    for endpoint in endpoints:
        completed = runner.run(
            [endpoint, "--help"],
            cwd=package_path.parent,
            timeout_s=timeout_s,
            max_stdout_bytes=200_000,
            max_stderr_bytes=200_000,
            runtime_environment=runtime_environment,
        )
        if completed.timed_out:
            raise ValueError(f"target CLI help probe timed out: {endpoint}")
        if completed.output_limited:
            raise ValueError(f"target CLI help probe exceeded its output limit: {endpoint}")
        if completed.returncode != 0:
            raise ValueError(
                f"target CLI help probe failed with code {completed.returncode}: "
                f"{endpoint}: {_structured_adapter_error(completed.stdout, completed.stderr)}"
            )


def _probe_cli_route_visibility(
    package_path: Path,
    manifest: AdapterBundleManifest,
    state_graph: StateGraphBaseline,
    *,
    timeout_s: float,
    runner: AdapterRunner,
    runtime_environment: Mapping[str, str] | None,
) -> None:
    """Verify gated CLI endpoints and their shebang interpreters resolve in the sandbox."""
    endpoints = sorted(
        {
            str(binding.get("endpoint", "")).strip()
            for entry in manifest.operations
            for binding in operation_route_binding_document(state_graph, entry.operation).get(
                "bindings", []
            )
            if binding.get("kind") == "cli" and str(binding.get("endpoint", "")).strip()
        }
    )
    if not endpoints:
        return
    script = """
import json
import os
import shlex
import shutil
import sys


def inspect(item):
    path = shutil.which(item)
    result = {"path": path, "interpreter": None, "interpreter_visible": None}
    if path is None:
        return result
    try:
        with open(path, "rb") as stream:
            first_line = stream.readline(4096)
    except OSError:
        return result
    if not first_line.startswith(b"#!"):
        return result
    try:
        command = shlex.split(first_line[2:].decode("utf-8", errors="strict").strip())
    except (UnicodeDecodeError, ValueError):
        result["interpreter"] = "INVALID_SHEBANG"
        result["interpreter_visible"] = False
        return result
    if not command:
        result["interpreter"] = "INVALID_SHEBANG"
        result["interpreter_visible"] = False
        return result
    interpreter = command[0]
    visible = (
        os.path.isfile(interpreter) and os.access(interpreter, os.X_OK)
        if os.path.isabs(interpreter)
        else shutil.which(interpreter) is not None
    )
    if os.path.basename(interpreter) == "env":
        program = next((value for value in command[1:] if not value.startswith("-")), None)
        if program is not None:
            interpreter = f"{interpreter} -> {program}"
            visible = visible and shutil.which(program) is not None
    result["interpreter"] = interpreter
    result["interpreter_visible"] = visible
    return result


items = json.load(sys.stdin)
print(json.dumps({item: inspect(item) for item in items}, sort_keys=True))
"""
    completed = runner.run(
        [sys.executable, "-c", script],
        stdin=json.dumps(endpoints),
        cwd=package_path.parent,
        timeout_s=timeout_s,
        max_stdout_bytes=200_000,
        max_stderr_bytes=200_000,
        runtime_environment=runtime_environment,
    )
    if completed.timed_out:
        raise ValueError("target CLI sandbox visibility probe timed out")
    if completed.output_limited:
        raise ValueError("target CLI sandbox visibility probe exceeded its output limit")
    if completed.returncode != 0:
        raise ValueError(
            "target CLI sandbox visibility probe failed with code "
            f"{completed.returncode}: {completed.stderr.strip()[:1000]}"
        )
    try:
        resolved = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("target CLI sandbox visibility probe returned invalid JSON") from exc
    missing = [
        item
        for item in endpoints
        if not isinstance(resolved, dict)
        or not isinstance(resolved.get(item), dict)
        or not resolved[item].get("path")
    ]
    if missing:
        raise ValueError(
            "target CLI is not resolvable inside the adapter sandbox: " + ", ".join(missing)
        )
    unavailable_interpreters = [
        item
        for item in endpoints
        if resolved[item].get("interpreter") is not None
        and resolved[item].get("interpreter_visible") is not True
    ]
    if unavailable_interpreters:
        raise ValueError(
            "target CLI interpreter is not resolvable inside the adapter sandbox: "
            + ", ".join(unavailable_interpreters)
        )


def probe_adapter_package(
    package_path: Path,
    manifest: AdapterBundleManifest,
    *,
    timeout_s: float = 10.0,
    runner: AdapterRunner | None = None,
    runtime_environment: Mapping[str, str] | None = None,
    state_graph: StateGraphBaseline | None = None,
) -> None:
    """Require package metadata and gated CLI routes to pass bounded probes.

    Promotion intentionally never executes adapter ``invoke``.  CLI ``--help``
    is read-only evidence for target route availability and is bounded by the
    same runner limits used at runtime.
    """
    effective_runner = runner or BoundedAdapterRunner()
    completed = effective_runner.run(
        adapter_command(package_path) + ["describe"],
        cwd=package_path.parent,
        timeout_s=timeout_s,
        max_stdout_bytes=200_000,
        max_stderr_bytes=200_000,
        runtime_environment=runtime_environment,
    )
    if completed.timed_out:
        raise ValueError("adapter package describe timed out")
    if completed.output_limited:
        raise ValueError("adapter package describe exceeded its output limit")
    if completed.returncode != 0:
        raise ValueError(
            f"adapter package describe failed with code {completed.returncode}: "
            f"{completed.stderr.strip()[:1000]}"
        )
    try:
        described = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("adapter package describe returned invalid JSON") from exc
    expected = {item.operation: item.entrypoint for item in manifest.operations}
    if not isinstance(described, dict) or described.get("operations") != expected:
        raise ValueError("adapter package describe does not match its bundle manifest")
    if state_graph is None:
        return
    endpoints = sorted(
        {
            str(binding.get("endpoint", "")).strip()
            for entry in manifest.operations
            for binding in operation_route_binding_document(state_graph, entry.operation).get(
                "bindings", []
            )
            if binding.get("kind") == "cli" and str(binding.get("endpoint", "")).strip()
        }
    )
    _probe_cli_help(
        package_path,
        endpoints,
        timeout_s=timeout_s,
        runner=effective_runner,
        runtime_environment=runtime_environment,
    )
    _probe_cli_route_visibility(
        package_path,
        manifest,
        state_graph,
        timeout_s=timeout_s,
        runner=effective_runner,
        runtime_environment=runtime_environment,
    )


def publish_release(
    *,
    output_root: Path,
    robot_id: str,
    release_id: str,
    discovery_id: str,
    target_fingerprint_sha256: str,
    runtime_environment: Mapping[str, str],
    bundle_manifest_path: Path,
    adapter_package_path: Path,
    adapter_files: list[tuple[str, Path, str]] | None = None,
    tool_catalog_path: Path,
    state_graph_path: Path,
    conformance_path: Path,
    gate_report_path: Path,
) -> tuple[AdapterReleaseManifest, Path]:
    """Atomically publish only gate-approved files to the external output root."""
    layout = AdapterOutputLayout(output_root)
    release_root = layout.release(robot_id, release_id)
    if release_root.exists():
        raise ValueError(f"adapter release already exists: {release_root}")
    staging = release_root.with_name(release_root.name + ".staging")
    if staging.exists():
        raise ValueError(f"adapter release staging path already exists: {staging}")
    staging.mkdir(parents=True)
    try:
        declared_adapter_files = adapter_files or [
            (adapter_package_path.name, adapter_package_path, "ENTRYPOINT")
        ]
        entrypoints = [item for item in declared_adapter_files if item[2] == "ENTRYPOINT"]
        if len(entrypoints) != 1 or entrypoints[0][1].resolve() != adapter_package_path.resolve():
            raise ValueError("published adapter files require one matching entrypoint")
        files = {
            "adapter/adapter-manifest.json": bundle_manifest_path,
            "tool-catalog.json": tool_catalog_path,
            "state-graph.json": state_graph_path,
            "conformance-report.json": conformance_path,
            "gate-report.json": gate_report_path,
        }
        for relative, source, _ in declared_adapter_files:
            candidate = Path(relative)
            if candidate.is_absolute() or ".." in candidate.parts or not candidate.parts:
                raise ValueError(f"unsafe adapter bundle file path: {relative}")
            files[f"adapter/{candidate.as_posix()}"] = source
        for relative, source in files.items():
            destination = staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        published_adapter_files = [
            PublishedAdapterFile(
                path=f"adapter/{Path(relative).as_posix()}",
                sha256=sha256_file(staging / "adapter" / relative),
                role=role,
            )
            for relative, _, role in declared_adapter_files
        ]
        entry = next(item for item in published_adapter_files if item.role == "ENTRYPOINT")
        release = AdapterReleaseManifest(
            schema_version="robot-adapter-release/v2",
            release_id=release_id,
            robot_id=robot_id,
            discovery_id=discovery_id,
            target_fingerprint_sha256=target_fingerprint_sha256,
            runtime_environment=AdapterRuntimeContext.capture(
                runtime_environment,
                include_executable_path=True,
            ),
            bundle_manifest="adapter/adapter-manifest.json",
            bundle_manifest_sha256=sha256_file(staging / "adapter/adapter-manifest.json"),
            adapter_package=entry.path,
            adapter_package_sha256=entry.sha256,
            adapter_files=published_adapter_files,
            tool_catalog="tool-catalog.json",
            tool_catalog_sha256=sha256_file(staging / "tool-catalog.json"),
            state_graph="state-graph.json",
            state_graph_sha256=sha256_file(staging / "state-graph.json"),
            conformance_report="conformance-report.json",
            conformance_report_sha256=sha256_file(staging / "conformance-report.json"),
            gate_report="gate-report.json",
            gate_report_sha256=sha256_file(staging / "gate-report.json"),
        )
        manifest_path = staging / "manifest.json"
        manifest_path.write_text(
            release.model_dump_json(indent=2, by_alias=True) + "\n", encoding="utf-8"
        )
        release_root.parent.mkdir(parents=True, exist_ok=True)
        staging.replace(release_root)
        manifest_path = release_root / "manifest.json"
        return release, manifest_path
    except Exception:
        if staging.is_dir():
            shutil.rmtree(staging)
        raise


def activate_release(
    output_root: Path,
    robot_id: str,
    release_id: str,
    *,
    artifact_root: Path,
    expected_current_release_id: str | None = None,
) -> Path:
    """Atomically make an already-published, fully validated release current."""
    layout = AdapterOutputLayout(output_root)
    current = layout.current(robot_id)
    current.parent.mkdir(parents=True, exist_ok=True)
    with interprocess_lock(current):
        if expected_current_release_id is not None:
            if not current.is_file():
                raise ValueError("active adapter release changed before activation")
            observed = AdapterReleaseIndex.model_validate_json(
                current.read_text(encoding="utf-8")
            )
            if observed.release_id != expected_current_release_id:
                raise ValueError("active adapter release changed before activation")
        release_root, release, bundle, catalog = _load_verified_release(
            layout, robot_id, release_id
        )
        _verify_release_freshness(
            release_root,
            release,
            bundle,
            catalog,
            artifact_root=artifact_root,
        )
        manifest_path = _relative_file(release_root, "manifest.json")
        index = AdapterReleaseIndex(
            robot_id=robot_id,
            release_id=release_id,
            manifest="manifest.json",
            manifest_sha256=sha256_file(manifest_path),
        )
        atomic_write_text(
            current,
            index.model_dump_json(indent=2) + "\n",
            acquire_lock=False,
        )
    return current
