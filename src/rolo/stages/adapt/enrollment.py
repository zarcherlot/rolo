"""Robot identity registration and discovery-time URDF parsing helpers."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from rolo.core.config import load_yaml
from rolo.core.hashing import sha256_bytes, sha256_file
from rolo.core.models import RobotCapability

ROBOT_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")
PROFILE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")
MAX_URDF_BYTES = 2 * 1024 * 1024
SUPPORTED_DRIVE_MODELS = {"differential", "ackermann"}


@dataclass(frozen=True)
class UrdfProfile:
    profile_id: str
    description: str
    path: Path
    sha256: str
    adapter: str
    platform: dict[str, Any]
    geometry: dict[str, Any]
    sensors: dict[str, Any]
    features: dict[str, Any]
    unresolved_semantics: tuple[str, ...]


@dataclass(frozen=True)
class UrdfSource:
    profile_id: str
    path: Path
    sha256: str


@dataclass(frozen=True)
class EnrollmentResult:
    status: str
    robot_id: str
    capability_path: Path
    capability_sha256: str


def load_urdf_source(path: Path) -> UrdfSource:
    """Validate only the immutable identity envelope needed before discovery."""
    resolved = path.expanduser().resolve()
    if resolved.suffix.lower() != ".urdf" or not resolved.is_file():
        raise ValueError(f"profile must be an existing .urdf file: {resolved}")
    payload = resolved.read_bytes()
    if not payload or len(payload) > MAX_URDF_BYTES:
        raise ValueError("URDF profile is empty or exceeds the 2 MiB limit")
    lowered = payload.lower()
    if b"<!doctype" in lowered or b"<!entity" in lowered:
        raise ValueError("URDF profile must not contain DTD or entity declarations")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ValueError(f"invalid URDF XML: {exc}") from exc
    if root.tag != "robot":
        raise ValueError("URDF root element must be <robot>")
    profile_id = _required_attribute(root, "name", context="URDF robot")
    if not PROFILE_ID_PATTERN.fullmatch(profile_id):
        raise ValueError("URDF robot name must match ^[a-z][a-z0-9_-]{2,63}$")
    normalized_payload = payload.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return UrdfSource(
        profile_id=profile_id,
        path=resolved,
        sha256=sha256_bytes(normalized_payload),
    )


def _required_attribute(element: ET.Element, name: str, *, context: str) -> str:
    value = (element.get(name) or "").strip()
    if not value:
        raise ValueError(f"{context} requires attribute {name}")
    return value


def _positive_float(element: ET.Element, name: str, *, context: str) -> float:
    raw = _required_attribute(element, name, context=context)
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{context} attribute {name} must be numeric") from exc
    if value <= 0:
        raise ValueError(f"{context} attribute {name} must be greater than zero")
    return value


def _vector(raw: str | None, *, size: int, context: str) -> tuple[float, ...]:
    values = (raw or "").split()
    if len(values) != size:
        raise ValueError(f"{context} must contain {size} numeric values")
    try:
        return tuple(float(value) for value in values)
    except ValueError as exc:
        raise ValueError(f"{context} must contain only numeric values") from exc


def _boolean(raw: str | None, *, context: str) -> bool:
    normalized = (raw or "").strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise ValueError(f"{context} must be true or false")


def _footprint(root: ET.Element, base_link_name: str) -> list[list[float]] | None:
    base_link = next(
        (link for link in root.findall("link") if link.get("name") == base_link_name), None
    )
    if base_link is None:
        return None
    collision = base_link.find("collision")
    geometry = collision.find("geometry") if collision is not None else None
    if collision is None or geometry is None:
        return None
    origin = collision.find("origin")
    x, y, _ = _vector(
        origin.get("xyz") if origin is not None else "0 0 0",
        size=3,
        context="base_link collision origin xyz",
    )
    box = geometry.find("box")
    cylinder = geometry.find("cylinder")
    if box is not None:
        length, width, _ = _vector(
            box.get("size"), size=3, context="base_link collision box size"
        )
        if length <= 0 or width <= 0:
            raise ValueError("base_link collision box dimensions must be greater than zero")
        half_length, half_width = length / 2, width / 2
    elif cylinder is not None:
        radius = _positive_float(cylinder, "radius", context="base_link collision cylinder")
        half_length = half_width = radius
    else:
        return None
    return [
        [x + half_length, y + half_width],
        [x + half_length, y - half_width],
        [x - half_length, y - half_width],
        [x - half_length, y + half_width],
    ]


def _joint_velocity_limits(root: ET.Element) -> dict[str, float]:
    limits: dict[str, float] = {}
    for joint in root.findall("joint"):
        name = (joint.get("name") or "").strip()
        limit = joint.find("limit")
        if not name or limit is None or not limit.get("velocity"):
            continue
        limits[name] = _positive_float(limit, "velocity", context=f"joint {name} limit")
    return limits


def _optional_positive_float(
    element: ET.Element | None, name: str, *, context: str
) -> float | None:
    if element is None or not (element.get(name) or "").strip():
        return None
    return _positive_float(element, name, context=context)


def load_urdf_profile(path: Path) -> UrdfProfile:
    source = load_urdf_source(path)
    resolved = source.path
    payload = resolved.read_bytes()
    root = ET.fromstring(payload)
    profile_id = source.profile_id
    links = {(link.get("name") or "").strip() for link in root.findall("link")}
    links.discard("")
    if not links:
        raise ValueError("URDF profile requires at least one named link")

    metadata = root.find("rolo")
    drive_model = (metadata.get("drive_model") or "").strip() if metadata is not None else ""
    if drive_model and drive_model not in SUPPORTED_DRIVE_MODELS:
        raise ValueError(
            f"unsupported drive_model {drive_model}; expected one of "
            f"{', '.join(sorted(SUPPORTED_DRIVE_MODELS))}"
        )
    base_link = (
        (metadata.get("base_link") or "base_link").strip()
        if metadata is not None
        else "base_link"
    )
    footprint = _footprint(root, base_link)
    max_linear = _optional_positive_float(
        metadata,
        "hard_max_linear_velocity_mps",
        context="URDF rolo metadata",
    )
    max_angular = _optional_positive_float(
        metadata,
        "hard_max_angular_velocity_radps",
        context="URDF rolo metadata",
    )
    geometry: dict[str, Any] = {"joint_velocity_limits": _joint_velocity_limits(root)}
    unresolved_semantics: list[str] = []
    if footprint is None:
        unresolved_semantics.append("geometry.footprint_m")
    else:
        geometry["footprint_m"] = footprint
    if max_linear is None:
        unresolved_semantics.append("geometry.hard_max_linear_velocity_mps")
    else:
        geometry["hard_max_linear_velocity_mps"] = max_linear
    if max_angular is None:
        unresolved_semantics.append("geometry.hard_max_angular_velocity_radps")
    else:
        geometry["hard_max_angular_velocity_radps"] = max_angular
    if not drive_model:
        unresolved_semantics.append("platform.drive_model")

    sensors: dict[str, Any] = {}
    for sensor in metadata.findall("sensor") if metadata is not None else ():
        name = _required_attribute(sensor, "name", context="URDF rolo sensor")
        link = _required_attribute(sensor, "link", context=f"URDF rolo sensor {name}")
        if link not in links:
            raise ValueError(f"URDF rolo sensor {name} references unknown link {link}")
        sensors[name] = {
            "semantic_uri": _required_attribute(
                sensor, "semantic_uri", context=f"URDF rolo sensor {name}"
            ),
            "modality": _required_attribute(
                sensor, "modality", context=f"URDF rolo sensor {name}"
            ),
            "binding": (sensor.get("binding") or f"unbound://sensor/{name}").strip(),
            "urdf_link": link,
        }

    features: dict[str, Any] = {}
    for feature in metadata.findall("feature") if metadata is not None else ():
        name = _required_attribute(feature, "name", context="URDF rolo feature")
        features[name] = _boolean(
            feature.get("enabled"), context=f"URDF rolo feature {name} enabled"
        )
    features["robot_use"] = {
        "supported": True,
        "local_visual_detection": False,
        "safety_authority": "none",
    }

    return UrdfProfile(
        profile_id=profile_id,
        description=(
            (metadata.get("description") or f"URDF profile {profile_id}").strip()
            if metadata is not None
            else f"URDF profile {profile_id}"
        ),
        path=resolved,
        sha256=source.sha256,
        adapter=(
            (metadata.get("adapter") or "unbound").strip()
            if metadata is not None
            else "unbound"
        ),
        platform={
            "architecture": "auto_discover",
            "compute": "auto_discover",
            "os": "auto_discover",
            "ros_distro": "auto_discover",
            "drive_model": drive_model or "unresolved",
            "base_link": base_link,
        },
        geometry=geometry,
        sensors=sensors,
        features=features,
        unresolved_semantics=tuple(unresolved_semantics),
    )


class EnrollmentService:
    def __init__(self, *, config_root: Path) -> None:
        self.config_root = config_root.resolve()

    def enroll(
        self,
        *,
        robot_id: str,
    ) -> EnrollmentResult:
        if not ROBOT_ID_PATTERN.fullmatch(robot_id):
            raise ValueError(
                "robot_id must match ^[a-z][a-z0-9_-]{2,63}$ and is assigned at initialization"
            )
        robots_root = self.config_root / "robots"
        robots_root.mkdir(parents=True, exist_ok=True)
        active = sorted(robots_root.glob("*.yaml"))
        target = robots_root / f"{robot_id}.yaml"
        if active:
            if len(active) == 1 and active[0] == target:
                RobotCapability.model_validate(load_yaml(target))
                return EnrollmentResult(
                    status="ALREADY_REGISTERED",
                    robot_id=robot_id,
                    capability_path=target,
                    capability_sha256=sha256_file(target),
                )
            active_ids = ", ".join(path.stem for path in active)
            raise ValueError(
                f"config root already contains registered robot(s): {active_ids}; "
                "one installed instance may own only one robot_id"
            )

        features = {
            "enrollment": {
                "identity_status": "REGISTERED",
                "urdf_status": "NOT_DISCOVERED",
                "semantic_status": "UNRESOLVED",
                "motion_safety_status": "UNAPPROVED",
                "bindings_verified": False,
                "calibration_verified": False,
            },
            "robot_use": {
                "supported": True,
                "local_visual_detection": False,
                "safety_authority": "none",
            },
        }
        capability = RobotCapability.model_validate(
            {
                "schema_version": "robot-capability/v1",
                "robot_id": robot_id,
                "adapter": "unbound",
                "platform": {
                    "architecture": "auto_discover",
                    "compute": "auto_discover",
                    "os": "auto_discover",
                    "ros_distro": "auto_discover",
                    "drive_model": "unresolved",
                },
                "geometry": {},
                "sensors": {},
                "features": features,
            }
        )
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
            "capability_path": str(target),
            "capability_sha256": sha256_file(target),
            "identity_status": "REGISTERED",
            "urdf_status": "NOT_DISCOVERED",
            "semantic_status": "UNRESOLVED",
            "motion_safety_status": "UNAPPROVED",
            "bindings_verified": False,
            "calibration_verified": False,
        }
        (self.config_root / "enrollment.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return EnrollmentResult(
            status="IDENTITY_REGISTERED",
            robot_id=robot_id,
            capability_path=target,
            capability_sha256=record["capability_sha256"],
        )
