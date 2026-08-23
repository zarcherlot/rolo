"""Robot identity registration and discovery-time URDF parsing helpers."""

from __future__ import annotations

import json
import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from rolo.core.config import load_yaml
from rolo.core.hashing import sha256_bytes, sha256_file
from rolo.core.models import RobotCapability
from rolo.core.persistence import atomic_write_text, interprocess_lock

ROBOT_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")
PROFILE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")
MAX_URDF_BYTES = 2 * 1024 * 1024
MAX_URDF_STRUCTURE_ITEMS = 1_000
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
    shape = base_link.find("collision") or base_link.find("visual")
    geometry = shape.find("geometry") if shape is not None else None
    if shape is None or geometry is None:
        return None
    origin = shape.find("origin")
    x, y, _ = _vector(
        origin.get("xyz") if origin is not None else "0 0 0",
        size=3,
        context="base_link geometry origin xyz",
    )
    box = geometry.find("box")
    cylinder = geometry.find("cylinder")
    if box is not None:
        length, width, _ = _vector(box.get("size"), size=3, context="base_link geometry box size")
        if length <= 0 or width <= 0:
            raise ValueError("base_link geometry box dimensions must be greater than zero")
        half_length, half_width = length / 2, width / 2
    elif cylinder is not None:
        radius = _positive_float(cylinder, "radius", context="base_link geometry cylinder")
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


def _origin(element: ET.Element | None, *, context: str) -> dict[str, list[float]]:
    origin = element.find("origin") if element is not None else None
    return {
        "xyz": list(
            _vector(
                (origin.get("xyz") or "0 0 0") if origin is not None else "0 0 0",
                size=3,
                context=f"{context} origin xyz",
            )
        ),
        "rpy": list(
            _vector(
                (origin.get("rpy") or "0 0 0") if origin is not None else "0 0 0",
                size=3,
                context=f"{context} origin rpy",
            )
        ),
    }


def _geometry_description(container: ET.Element, *, context: str) -> dict[str, Any] | None:
    geometry = container.find("geometry")
    if geometry is None:
        return None
    description: dict[str, Any] = {"origin": _origin(container, context=context)}
    box = geometry.find("box")
    cylinder = geometry.find("cylinder")
    sphere = geometry.find("sphere")
    mesh = geometry.find("mesh")
    if box is not None:
        description.update(
            type="box",
            size_m=list(_vector(box.get("size"), size=3, context=f"{context} box size")),
        )
    elif cylinder is not None:
        description.update(
            type="cylinder",
            radius_m=_positive_float(cylinder, "radius", context=f"{context} cylinder"),
            length_m=_positive_float(cylinder, "length", context=f"{context} cylinder"),
        )
    elif sphere is not None:
        description.update(
            type="sphere",
            radius_m=_positive_float(sphere, "radius", context=f"{context} sphere"),
        )
    elif mesh is not None:
        scale = mesh.get("scale")
        description.update(
            type="mesh",
            filename=(mesh.get("filename") or "").strip(),
            scale=list(_vector(scale, size=3, context=f"{context} mesh scale"))
            if scale
            else [1.0, 1.0, 1.0],
        )
    else:
        return None
    return description


def _leaf_parameters(element: ET.Element, *, limit: int = 200) -> dict[str, str]:
    values: dict[str, str] = {}

    def visit(node: ET.Element, path: str) -> None:
        if len(values) >= limit:
            return
        children = list(node)
        text = (node.text or "").strip()
        if not children and text:
            values[path] = text
        for child in children:
            visit(child, f"{path}.{child.tag}" if path else child.tag)

    visit(element, "")
    return values


def _urdf_hardware(root: ET.Element, base_link: str) -> tuple[dict[str, Any], dict[str, Any]]:
    links: list[dict[str, Any]] = []
    link_elements = {
        (link.get("name") or "").strip(): link
        for link in root.findall("link")
        if (link.get("name") or "").strip()
    }
    declared_masses: list[float] = []
    for name, link in sorted(link_elements.items()):
        visuals = [
            item
            for index, visual in enumerate(link.findall("visual"))
            if (item := _geometry_description(visual, context=f"link {name} visual {index}"))
        ]
        collisions = [
            item
            for index, collision in enumerate(link.findall("collision"))
            if (item := _geometry_description(collision, context=f"link {name} collision {index}"))
        ]
        inertial = link.find("inertial")
        inertia_data: dict[str, Any] | None = None
        if inertial is not None:
            mass = inertial.find("mass")
            inertia = inertial.find("inertia")
            inertia_data = {"origin": _origin(inertial, context=f"link {name} inertial")}
            if mass is not None and mass.get("value"):
                value = _positive_float(mass, "value", context=f"link {name} mass")
                inertia_data["mass_kg"] = value
                declared_masses.append(value)
            if inertia is not None:
                tensor: dict[str, float] = {}
                for field in ("ixx", "ixy", "ixz", "iyy", "iyz", "izz"):
                    raw = (inertia.get(field) or "").strip()
                    if raw:
                        value = float(raw)
                        if math.isfinite(value):
                            tensor[field] = value
                inertia_data["tensor_kg_m2"] = tensor
        links.append(
            {
                "name": name,
                "visual": visuals,
                "collision": collisions,
                "inertial": inertia_data,
            }
        )

    wheel_candidates: list[dict[str, float | str]] = []
    for joint in root.findall("joint"):
        parent = joint.find("parent")
        child = joint.find("child")
        parent_name = (parent.get("link") or "").strip() if parent is not None else ""
        child_name = (child.get("link") or "").strip() if child is not None else ""
        xyz = _origin(joint, context=f"joint {(joint.get('name') or 'unknown')}")["xyz"]
        axis_element = joint.find("axis")
        axis = _vector(
            axis_element.get("xyz") if axis_element is not None else "1 0 0",
            size=3,
            context=f"joint {(joint.get('name') or 'unknown')} axis",
        )
        child_link = link_elements.get(child_name)
        if (
            child_link is None
            or parent_name != base_link
            or joint.get("type") not in {"continuous", "revolute"}
            or abs(axis[2]) >= 0.5
        ):
            continue
        geometries = child_link.findall("collision") or child_link.findall("visual")
        for index, container in enumerate(geometries):
            item = _geometry_description(container, context=f"wheel candidate {child_name} {index}")
            if item and item.get("type") == "cylinder":
                wheel_candidates.append(
                    {
                        "link": child_name,
                        "radius_m": float(item["radius_m"]),
                        "width_m": float(item["length_m"]),
                        "x_m": xyz[0] + item["origin"]["xyz"][0],
                        "y_m": xyz[1] + item["origin"]["xyz"][1],
                        "z_m": xyz[2] + item["origin"]["xyz"][2],
                        "axis_x": axis[0],
                        "axis_y": axis[1],
                        "axis_z": axis[2],
                    }
                )
                break

    base = link_elements.get(base_link)
    base_geometry: dict[str, Any] | None = None
    if base is not None:
        containers = base.findall("collision") or base.findall("visual")
        if containers:
            base_geometry = _geometry_description(containers[0], context=f"link {base_link}")
    derived: dict[str, Any] = {}
    if base_geometry and base_geometry.get("type") == "box":
        size = base_geometry["size_m"]
        origin = base_geometry["origin"]["xyz"]
        derived["body_dimensions_m"] = size
        derived["ground_clearance_m"] = max(0.0, origin[2] - size[2] / 2)
    if wheel_candidates:
        radii = sorted({round(float(wheel["radius_m"]), 9) for wheel in wheel_candidates})
        widths = sorted({round(float(wheel["width_m"]), 9) for wheel in wheel_candidates})
        xs = [float(wheel["x_m"]) for wheel in wheel_candidates]
        ys = [float(wheel["y_m"]) for wheel in wheel_candidates]
        derived.update(
            wheel_count=len(wheel_candidates),
            wheel_radii_m=radii,
            wheel_widths_m=widths,
            track_width_m=max(ys) - min(ys) if len(set(ys)) > 1 else None,
            wheelbase_m=max(xs) - min(xs) if len(set(xs)) > 1 else None,
        )
        if base_geometry and base_geometry.get("type") == "box":
            size = base_geometry["size_m"]
            origin = base_geometry["origin"]["xyz"]
            x_min, x_max = origin[0] - size[0] / 2, origin[0] + size[0] / 2
            y_min, y_max = origin[1] - size[1] / 2, origin[1] + size[1] / 2
            z_min, z_max = origin[2] - size[2] / 2, origin[2] + size[2] / 2
            for wheel in wheel_candidates:
                radius, width = float(wheel["radius_m"]), float(wheel["width_m"])
                x_half = width / 2 if abs(float(wheel["axis_x"])) >= 0.5 else radius
                y_half = width / 2 if abs(float(wheel["axis_y"])) >= 0.5 else radius
                x_min, x_max = (
                    min(x_min, float(wheel["x_m"]) - x_half),
                    max(x_max, float(wheel["x_m"]) + x_half),
                )
                y_min, y_max = (
                    min(y_min, float(wheel["y_m"]) - y_half),
                    max(y_max, float(wheel["y_m"]) + y_half),
                )
                z_min, z_max = (
                    min(z_min, float(wheel["z_m"]) - radius),
                    max(z_max, float(wheel["z_m"]) + radius),
                )
            derived["envelope_m"] = [x_max - x_min, y_max - y_min, z_max - z_min]
    if declared_masses:
        derived["declared_mass_kg"] = sum(declared_masses)
        derived["mass_link_count"] = len(declared_masses)
        derived["mass_complete"] = len(declared_masses) == len(link_elements)

    transmissions = []
    for item in root.findall("transmission")[:MAX_URDF_STRUCTURE_ITEMS]:
        transmissions.append(
            {
                "name": (item.get("name") or "").strip(),
                "type": (item.findtext("type") or "").strip(),
                "joints": [
                    {
                        "name": (joint.get("name") or "").strip(),
                        "hardware_interfaces": [
                            (interface.text or "").strip()
                            for interface in joint.findall("hardwareInterface")
                            if interface.text
                        ],
                    }
                    for joint in item.findall("joint")
                ],
                "actuators": [
                    {
                        "name": (actuator.get("name") or "").strip(),
                        "hardware_interfaces": [
                            (interface.text or "").strip()
                            for interface in actuator.findall("hardwareInterface")
                            if interface.text
                        ],
                        "mechanical_reduction": (
                            actuator.findtext("mechanicalReduction") or ""
                        ).strip(),
                    }
                    for actuator in item.findall("actuator")
                ],
            }
        )
    ros2_control = []
    for item in root.findall("ros2_control")[:MAX_URDF_STRUCTURE_ITEMS]:
        hardware = item.find("hardware")
        ros2_control.append(
            {
                "name": (item.get("name") or "").strip(),
                "type": (item.get("type") or "").strip(),
                "plugins": [
                    (plugin.text or "").strip()
                    for plugin in hardware.findall("plugin")
                    if plugin.text
                ]
                if hardware is not None
                else [],
                "hardware_parameters": _leaf_parameters(hardware) if hardware is not None else {},
                "joints": [
                    {
                        "name": (joint.get("name") or "").strip(),
                        "command_interfaces": [
                            (interface.get("name") or "").strip()
                            for interface in joint.findall("command_interface")
                        ],
                        "state_interfaces": [
                            (interface.get("name") or "").strip()
                            for interface in joint.findall("state_interface")
                        ],
                    }
                    for joint in item.findall("joint")
                ],
            }
        )
    gazebo = []
    for item in root.findall("gazebo")[:MAX_URDF_STRUCTURE_ITEMS]:
        sensors = []
        for sensor in item.findall("sensor"):
            sensors.append(
                {
                    "name": (sensor.get("name") or "").strip(),
                    "type": (sensor.get("type") or "").strip(),
                    "update_rate_hz": (sensor.findtext("update_rate") or "").strip(),
                    "parameters": _leaf_parameters(sensor),
                }
            )
        gazebo.append(
            {
                "reference": (item.get("reference") or "").strip(),
                "plugins": [
                    {
                        "name": (plugin.get("name") or "").strip(),
                        "filename": (plugin.get("filename") or "").strip(),
                        "parameters": _leaf_parameters(plugin),
                    }
                    for plugin in item.findall("plugin")
                ],
                "sensors": sensors,
            }
        )
    return {
        "links": links,
        "transmissions": transmissions,
        "ros2_control": ros2_control,
        "gazebo": gazebo,
        "wheel_candidates": wheel_candidates,
    }, {key: value for key, value in derived.items() if value is not None}


def _urdf_structure(root: ET.Element) -> dict[str, Any]:
    links = sorted(
        {name for link in root.findall("link") if (name := (link.get("name") or "").strip())}
    )[:MAX_URDF_STRUCTURE_ITEMS]
    joints: list[dict[str, Any]] = []
    for joint in root.findall("joint")[:MAX_URDF_STRUCTURE_ITEMS]:
        name = (joint.get("name") or "").strip()
        if not name:
            continue
        parent = joint.find("parent")
        child = joint.find("child")
        axis = joint.find("axis")
        dynamics = joint.find("dynamics")
        mimic = joint.find("mimic")
        limit = joint.find("limit")
        limits: dict[str, float] = {}
        for field in ("lower", "upper", "effort", "velocity"):
            raw = (limit.get(field) or "").strip() if limit is not None else ""
            if not raw:
                continue
            try:
                value = float(raw)
            except ValueError:
                continue
            if math.isfinite(value):
                limits[field] = value
        joints.append(
            {
                "name": name,
                "type": (joint.get("type") or "unknown").strip(),
                "parent": (parent.get("link") or "").strip() if parent is not None else "",
                "child": (child.get("link") or "").strip() if child is not None else "",
                "axis": (axis.get("xyz") or "").strip() if axis is not None else "",
                "origin": _origin(joint, context=f"joint {name}"),
                "limits": limits,
                "dynamics": dict(dynamics.attrib) if dynamics is not None else {},
                "mimic": dict(mimic.attrib) if mimic is not None else {},
            }
        )
    return {
        "links": links,
        "joints": joints,
        "truncated": len(root.findall("link")) > len(links)
        or len(root.findall("joint")) > len(joints),
    }


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
        (metadata.get("base_link") or "base_link").strip() if metadata is not None else "base_link"
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
    urdf_hardware, derived_geometry = _urdf_hardware(root, base_link)
    geometry: dict[str, Any] = {
        "joint_velocity_limits": _joint_velocity_limits(root),
        **derived_geometry,
    }
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
            "modality": _required_attribute(sensor, "modality", context=f"URDF rolo sensor {name}"),
            "binding": (sensor.get("binding") or f"unbound://sensor/{name}").strip(),
            "urdf_link": link,
        }

    features: dict[str, Any] = {}
    for feature in metadata.findall("feature") if metadata is not None else ():
        name = _required_attribute(feature, "name", context="URDF rolo feature")
        features[name] = _boolean(
            feature.get("enabled"), context=f"URDF rolo feature {name} enabled"
        )
    features["urdf_structure"] = _urdf_structure(root)
    features["urdf_hardware"] = urdf_hardware
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
            (metadata.get("adapter") or "unbound").strip() if metadata is not None else "unbound"
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
        with interprocess_lock(self.config_root / "enrollment.json"):
            return self._enroll_locked(robot_id)

    def _enroll_locked(self, robot_id: str) -> EnrollmentResult:
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
        atomic_write_text(
            target,
            yaml.safe_dump(
                capability.model_dump(mode="json"),
                sort_keys=False,
                allow_unicode=True,
            ),
            acquire_lock=False,
        )
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
        atomic_write_text(
            self.config_root / "enrollment.json",
            json.dumps(record, ensure_ascii=False, indent=2) + "\n",
            acquire_lock=False,
        )
        return EnrollmentResult(
            status="IDENTITY_REGISTERED",
            robot_id=robot_id,
            capability_path=target,
            capability_sha256=record["capability_sha256"],
        )
