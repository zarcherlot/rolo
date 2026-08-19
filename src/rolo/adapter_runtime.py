from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rolo.core.hashing import sha256_file
from rolo.schema_subset import validate_object
from rolo.stages.adapt.models import (
    AdapterBundleManifest,
    AdapterReleaseIndex,
    AdapterReleaseManifest,
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


@dataclass(frozen=True)
class AdapterOutputLayout:
    root: Path

    def robot_root(self, robot_id: str) -> Path:
        return self.root / "robots" / _safe_segment(robot_id, "robot_id")

    def release(self, robot_id: str, release_id: str) -> Path:
        return self.robot_root(robot_id) / "releases" / _safe_segment(release_id, "release_id")

    def current(self, robot_id: str) -> Path:
        return self.robot_root(robot_id) / "current.json"


def load_current_release(
    output_root: Path, robot_id: str
) -> tuple[Path, AdapterReleaseManifest, AdapterBundleManifest, ToolCatalog]:
    layout = AdapterOutputLayout(output_root)
    index_path = layout.current(robot_id)
    index = AdapterReleaseIndex.model_validate_json(index_path.read_text(encoding="utf-8"))
    if index.robot_id != robot_id:
        raise ValueError("adapter release index robot identity mismatch")
    release_root = layout.release(robot_id, index.release_id)
    manifest_path = _relative_file(release_root, index.manifest)
    if sha256_file(manifest_path) != index.manifest_sha256:
        raise ValueError("adapter release manifest hash mismatch")
    release = AdapterReleaseManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    if release.robot_id != robot_id or release.release_id != index.release_id:
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
    bundle = AdapterBundleManifest.model_validate_json(
        _relative_file(release_root, release.bundle_manifest).read_text(encoding="utf-8")
    )
    catalog = ToolCatalog.model_validate_json(
        _relative_file(release_root, release.tool_catalog).read_text(encoding="utf-8")
    )
    if bundle.robot_id != robot_id or bundle.discovery_id != release.discovery_id:
        raise ValueError("adapter bundle identity mismatch")
    if catalog.robot_id != robot_id or catalog.discovery_id != release.discovery_id:
        raise ValueError("active Tool Catalog identity mismatch")
    if bundle.package_sha256 != release.adapter_package_sha256:
        raise ValueError("adapter bundle and release package hashes differ")
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
    return release_root, release, bundle, catalog


def invoke_adapter(
    output_root: Path,
    robot_id: str,
    operation: str,
    payload: dict[str, Any],
    *,
    timeout_s: float = 30.0,
) -> dict[str, Any]:
    """Invoke one catalogued operation through the immutable adapter RPC bundle."""
    release_root, release, bundle, catalog = load_current_release(output_root, robot_id)
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
    package_path = _relative_file(release_root, release.adapter_package)
    try:
        completed = subprocess.run(
            adapter_command(package_path)
            + ["invoke", "--operation", operation, "--entrypoint", entry.entrypoint],
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=min(timeout_s, descriptor.max_duration_s),
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("adapter invocation timed out") from exc
    if completed.returncode != 0:
        raise RuntimeError(
            f"adapter invocation failed with code {completed.returncode}: "
            f"{completed.stderr.strip()[:1000]}"
        )
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("adapter returned invalid JSON") from exc
    if not isinstance(result, dict):
        raise RuntimeError("adapter result must be a JSON object")
    _validate_object_schema(result, descriptor.output_schema, "adapter output")
    return result


def _validate_object_schema(value: dict[str, Any], schema: dict[str, Any], label: str) -> None:
    validate_object(value, schema, label)


def adapter_command(package_path: Path) -> list[str]:
    """Return an argv-only launcher for a standalone executable or Python adapter package."""
    if package_path.suffix.lower() == ".py":
        return [sys.executable, str(package_path)]
    return [str(package_path)]


def probe_adapter_package(
    package_path: Path, manifest: AdapterBundleManifest, *, timeout_s: float = 10.0
) -> None:
    """Require the generated package to self-describe exactly the declared entrypoints."""
    try:
        completed = subprocess.run(
            adapter_command(package_path) + ["describe"],
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError("adapter package describe timed out") from exc
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


def publish_release(
    *,
    output_root: Path,
    robot_id: str,
    release_id: str,
    discovery_id: str,
    bundle_manifest_path: Path,
    adapter_package_path: Path,
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
        files = {
            "adapter/adapter-manifest.json": bundle_manifest_path,
            f"adapter/{adapter_package_path.name}": adapter_package_path,
            "tool-catalog.json": tool_catalog_path,
            "state-graph.json": state_graph_path,
            "conformance-report.json": conformance_path,
            "gate-report.json": gate_report_path,
        }
        for relative, source in files.items():
            destination = staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        release = AdapterReleaseManifest(
            release_id=release_id,
            robot_id=robot_id,
            discovery_id=discovery_id,
            bundle_manifest="adapter/adapter-manifest.json",
            bundle_manifest_sha256=sha256_file(staging / "adapter/adapter-manifest.json"),
            adapter_package=f"adapter/{adapter_package_path.name}",
            adapter_package_sha256=sha256_file(staging / f"adapter/{adapter_package_path.name}"),
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
        manifest_path.write_text(release.model_dump_json(indent=2) + "\n", encoding="utf-8")
        release_root.parent.mkdir(parents=True, exist_ok=True)
        staging.replace(release_root)
        manifest_path = release_root / "manifest.json"
        return release, manifest_path
    except Exception:
        if staging.is_dir():
            shutil.rmtree(staging)
        raise


def activate_release(output_root: Path, robot_id: str, release_id: str) -> Path:
    """Atomically make an already-published, fully validated release current."""
    layout = AdapterOutputLayout(output_root)
    release_root = layout.release(robot_id, release_id)
    manifest_path = _relative_file(release_root, "manifest.json")
    release = AdapterReleaseManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    if release.robot_id != robot_id or release.release_id != release_id:
        raise ValueError("adapter release identity mismatch before activation")
    index = AdapterReleaseIndex(
        robot_id=robot_id,
        release_id=release_id,
        manifest="manifest.json",
        manifest_sha256=sha256_file(manifest_path),
    )
    current = layout.current(robot_id)
    current.parent.mkdir(parents=True, exist_ok=True)
    temporary = current.with_suffix(".json.tmp")
    temporary.write_text(index.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(current)
    return current
