from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from rolo.core.hashing import sha256_file
from rolo.core.models import utc_now
from rolo.stages.artifact_paths import ArtifactLayout


class ManifestEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)


class DiscoveryRunManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-discovery-run-manifest/v1"] = (
        "robot-discovery-run-manifest/v1"
    )
    robot_id: str
    discovery_id: str
    files: list[ManifestEntry] = Field(min_length=1)
    created_at: datetime = Field(default_factory=utc_now)


def create_discovery_manifest(
    run_root: Path, robot_id: str, discovery_id: str
) -> DiscoveryRunManifest:
    entries = []
    for path in sorted(run_root.rglob("*")):
        if path.is_file() and path.name not in {"manifest.json", "robot_wiki.md"}:
            entries.append(
                ManifestEntry(
                    path=path.relative_to(run_root).as_posix(),
                    sha256=sha256_file(path),
                    size_bytes=path.stat().st_size,
                )
            )
    return DiscoveryRunManifest(robot_id=robot_id, discovery_id=discovery_id, files=entries)


def load_and_verify_discovery_manifest(
    artifact_root: Path, robot_id: str, discovery_id: str
) -> tuple[DiscoveryRunManifest, Path]:
    run_root = ArtifactLayout(artifact_root).discovery_run(robot_id, discovery_id)
    return verify_discovery_manifest_path(run_root, robot_id, discovery_id)


def verify_discovery_manifest_path(
    run_root: Path, robot_id: str, discovery_id: str
) -> tuple[DiscoveryRunManifest, Path]:
    manifest_path = run_root / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"discovery manifest is missing: {manifest_path}")
    manifest = DiscoveryRunManifest.model_validate_json(
        manifest_path.read_text(encoding="utf-8")
    )
    if manifest.robot_id != robot_id or manifest.discovery_id != discovery_id:
        raise ValueError("discovery manifest identity mismatch")
    seen: set[str] = set()
    for entry in manifest.files:
        relative = Path(entry.path)
        if relative.is_absolute() or ".." in relative.parts or entry.path in seen:
            raise ValueError(f"invalid discovery manifest entry: {entry.path}")
        seen.add(entry.path)
        path = (run_root / relative).resolve()
        try:
            path.relative_to(run_root.resolve())
        except ValueError as exc:
            raise ValueError(f"discovery manifest entry escapes run: {entry.path}") from exc
        if not path.is_file():
            raise ValueError(f"discovery manifest file is missing: {entry.path}")
        if path.stat().st_size != entry.size_bytes or sha256_file(path) != entry.sha256:
            raise ValueError(f"discovery manifest hash mismatch: {entry.path}")
    required = {
        "report.json",
        "active_discovery_report.json",
        "capability_manifest.json",
        "semantic_context.json",
        "tool_catalog.json",
    }
    missing = required - seen
    if missing:
        raise ValueError(f"discovery manifest lacks required files: {sorted(missing)}")
    actual = {
        path.relative_to(run_root).as_posix()
        for path in run_root.rglob("*")
        if path.is_file() and path.name not in {"manifest.json", "robot_wiki.md"}
    }
    unexpected = actual - seen
    if unexpected:
        raise ValueError(f"discovery run contains unmanifested files: {sorted(unexpected)}")
    return manifest, manifest_path
