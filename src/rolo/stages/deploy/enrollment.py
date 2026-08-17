"""Stage 1 robot identity and structural profile enrollment."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from rolo.core.config import load_yaml
from rolo.core.models import RobotCapability

ROBOT_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")
PROFILE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")


@dataclass(frozen=True)
class EnrollmentResult:
    status: str
    robot_id: str
    profile_id: str
    capability_path: Path
    capability_sha256: str


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def list_profiles(profile_root: Path) -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    if not profile_root.is_dir():
        return profiles
    for path in sorted(profile_root.glob("*.yaml")):
        template = load_yaml(path)
        profile_id = template.get("profile_id")
        if not isinstance(profile_id, str) or not PROFILE_ID_PATTERN.fullmatch(profile_id):
            raise ValueError(f"invalid profile_id in {path}")
        profiles.append(
            {
                "profile_id": profile_id,
                "description": template.get("description", ""),
                "drive_model": template.get("platform", {}).get("drive_model"),
                "requires_safety_confirmation": template.get("enrollment", {}).get(
                    "requires_safety_confirmation", True
                ),
                "path": str(path),
            }
        )
    return profiles


def resolve_profile_root(config_root: Path, requested: Path | None = None) -> Path:
    if requested is not None:
        return requested.resolve()
    candidates = (
        config_root / "profiles",
        config_root.parent / "profiles",
        Path("configs/profiles"),
    )
    for candidate in candidates:
        if candidate.is_dir():
            return candidate.resolve()
    return candidates[0].resolve()


class EnrollmentService:
    def __init__(self, *, config_root: Path, profile_root: Path) -> None:
        self.config_root = config_root.resolve()
        self.profile_root = profile_root.resolve()

    def enroll(
        self,
        *,
        robot_id: str,
        profile_id: str,
        safety_profile_confirmed: bool,
    ) -> EnrollmentResult:
        if not ROBOT_ID_PATTERN.fullmatch(robot_id):
            raise ValueError(
                "robot_id must match ^[a-z][a-z0-9_-]{2,63}$ and is assigned at enrollment"
            )
        if not PROFILE_ID_PATTERN.fullmatch(profile_id):
            raise ValueError("invalid profile_id")
        template_path = self.profile_root / f"{profile_id}.yaml"
        if not template_path.is_file():
            available = ", ".join(item["profile_id"] for item in list_profiles(self.profile_root))
            raise ValueError(f"unknown profile_id {profile_id}; available: {available or 'none'}")

        template = load_yaml(template_path)
        if template.get("profile_id") != profile_id:
            raise ValueError("profile filename and profile_id do not match")
        requirements = template.get("enrollment", {})
        if requirements.get("requires_safety_confirmation", True) and not safety_profile_confirmed:
            raise ValueError(
                "profile contains physical safety bounds; --confirm-safety-profile is required"
            )

        robots_root = self.config_root / "robots"
        robots_root.mkdir(parents=True, exist_ok=True)
        active = sorted(robots_root.glob("*.yaml"))
        target = robots_root / f"{robot_id}.yaml"
        if active:
            if len(active) == 1 and active[0] == target:
                existing = RobotCapability.model_validate(load_yaml(target))
                existing_profile = existing.features.get("enrollment", {}).get("profile_id")
                if existing_profile != profile_id:
                    raise ValueError(
                        f"{robot_id} is already enrolled with profile {existing_profile}; "
                        "profile replacement requires a separate migration"
                    )
                return EnrollmentResult(
                    status="ALREADY_ENROLLED",
                    robot_id=robot_id,
                    profile_id=profile_id,
                    capability_path=target,
                    capability_sha256=_digest(target),
                )
            active_ids = ", ".join(path.stem for path in active)
            raise ValueError(
                f"config root already contains enrolled robot(s): {active_ids}; "
                "one installed instance may own only one robot_id"
            )

        features = dict(template.get("features", {}))
        features["enrollment"] = {
            "profile_id": profile_id,
            "safety_profile_confirmed": safety_profile_confirmed,
            "bindings_verified": False,
            "calibration_verified": False,
        }
        capability_payload = {
            "schema_version": "robot-capability/v1",
            "robot_id": robot_id,
            "adapter": template.get("adapter", "unbound"),
            "platform": template.get("platform", {}),
            "geometry": template.get("geometry", {}),
            "sensors": template.get("sensors", {}),
            "features": features,
        }
        capability = RobotCapability.model_validate(capability_payload)
        temporary = target.with_suffix(".yaml.tmp")
        temporary.write_text(
            yaml.safe_dump(
                capability.model_dump(mode="json"),
                sort_keys=False,
                allow_unicode=True,
            ),
            encoding="utf-8",
        )
        temporary.replace(target)
        record = {
            "schema_version": "robot-enrollment/v1",
            "robot_id": robot_id,
            "profile_id": profile_id,
            "capability_path": str(target),
            "capability_sha256": _digest(target),
            "safety_profile_confirmed": safety_profile_confirmed,
            "bindings_verified": False,
            "calibration_verified": False,
        }
        (self.config_root / "enrollment.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return EnrollmentResult(
            status="ENROLLED_DEGRADED",
            robot_id=robot_id,
            profile_id=profile_id,
            capability_path=target,
            capability_sha256=record["capability_sha256"],
        )
