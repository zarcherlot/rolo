from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_STAGES = {"adapt", "diagnose", "verify"}


def _segment(value: str, label: str) -> str:
    if not _SAFE_SEGMENT.fullmatch(value):
        raise ValueError(f"invalid {label}: {value!r}")
    return value


def canonical_stage(value: str) -> str:
    if value not in _STAGES:
        raise ValueError(f"unknown lifecycle stage: {value}")
    return value


@dataclass(frozen=True)
class ArtifactLayout:
    """Single source of truth for all lifecycle artifact locations."""

    root: Path

    def discovery_run(self, robot_id: str, discovery_id: str) -> Path:
        return (
            self.root
            / "discovery"
            / _segment(robot_id, "robot_id")
            / "runs"
            / _segment(discovery_id, "discovery_id")
        )

    def discovery_latest(self, robot_id: str) -> Path:
        return self.root / "discovery" / _segment(robot_id, "robot_id") / "latest.json"

    def stage_run(self, stage: str, robot_id: str, run_id: str) -> Path:
        return (
            self.root
            / canonical_stage(stage)
            / _segment(robot_id, "robot_id")
            / "runs"
            / _segment(run_id, "run_id")
        )

    def stage_latest(self, stage: str, robot_id: str) -> Path:
        return self.root / canonical_stage(stage) / _segment(robot_id, "robot_id") / "latest"

    def stage_latest_index(self, stage: str, robot_id: str) -> Path:
        return self.root / canonical_stage(stage) / _segment(robot_id, "robot_id") / "latest.json"

    def episode_publications(self, robot_id: str) -> Path:
        return self.root / "episodes" / _segment(robot_id, "robot_id") / "published"

    def episode_publication(self, robot_id: str, episode_id: str) -> Path:
        return self.episode_publications(robot_id) / f"{_segment(episode_id, 'episode_id')}.json"

    def episode_records(self, robot_id: str, episode_id: str) -> Path:
        return (
            self.root
            / "episodes"
            / _segment(robot_id, "robot_id")
            / "records"
            / _segment(episode_id, "episode_id")
        )

    def episode_record(self, robot_id: str, episode_id: str, revision: int) -> Path:
        if revision < 1:
            raise ValueError("episode revision must be positive")
        return self.episode_records(robot_id, episode_id) / f"revision-{revision}.json"

    def episode_observation_records(self, robot_id: str, episode_id: str) -> Path:
        return (
            self.root
            / "episodes"
            / _segment(robot_id, "robot_id")
            / "observation-records"
            / _segment(episode_id, "episode_id")
        )

    def episode_observation_record(
        self,
        robot_id: str,
        episode_id: str,
        revision: int,
    ) -> Path:
        if revision < 1:
            raise ValueError("episode revision must be positive")
        return self.episode_observation_records(robot_id, episode_id) / f"revision-{revision}.json"

    def episode_observation_publications(self, robot_id: str, episode_id: str) -> Path:
        return (
            self.root
            / "episodes"
            / _segment(robot_id, "robot_id")
            / "published-observations"
            / _segment(episode_id, "episode_id")
        )

    def episode_observation_publication(
        self,
        robot_id: str,
        episode_id: str,
        revision: int,
    ) -> Path:
        if revision < 1:
            raise ValueError("episode revision must be positive")
        return (
            self.episode_observation_publications(robot_id, episode_id)
            / f"revision-{revision}.json"
        )

    def relative(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.root.resolve()).as_posix()
        except ValueError as exc:
            raise ValueError(f"artifact path escapes artifact root: {path}") from exc

    def ref(self, path: Path) -> str:
        return f"artifact://{self.relative(path)}"

    def stage_file(self, stage: str, robot_id: str, relative: str) -> Path:
        return self.stage_latest(stage, robot_id) / relative


def resolve_artifact_ref(root: Path, reference: str) -> Path:
    prefix = "artifact://"
    if not reference.startswith(prefix):
        raise ValueError(f"not an artifact reference: {reference}")
    relative = Path(reference[len(prefix) :])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe artifact reference: {reference}")
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"artifact reference escapes root: {reference}") from exc
    return resolved
