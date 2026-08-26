import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rolo.cli import app
from rolo.core.artifacts import ArtifactStore
from rolo.core.config import get_settings, load_yaml
from rolo.core.models import ProbeResult, RobotCapability
from rolo.core.registry import RobotRegistry
from rolo.stages.adapt.active_discovery import (
    ActiveDiscoveryInputs,
    DiscoveryModeLevel,
)
from rolo.stages.adapt.discovery import (
    UBUNTU_ROS_DEFAULTS,
    ApplicationProbe,
    DiscoveryService,
    HardwareProbe,
    _build_operation_candidates,
    _extract_parameter_default_ros_names,
    _extract_ros_config_names,
    _hardware_reconciliation,
    _semantic_bindings,
    detect_compute_platform,
    load_latest_report,
)
from rolo.stages.adapt.enrollment import EnrollmentService
from rolo.stages.adapt.operation_registry import materialize_active_catalog
from rolo.stages.adapt.semantic_mapping import SemanticOperationRule
from rolo.stages.discovery_manifest import DiscoveryRunManifest
from rolo.targets import TargetSourceProjectSummary


def test_linux_hardware_probe_degrades_when_bus_enumeration_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("rolo.stages.adapt.discovery.platform.system", lambda: "Linux")
    monkeypatch.setattr("rolo.stages.adapt.discovery._device_tree_model", lambda: None)
    monkeypatch.setattr(
        "rolo.stages.adapt.discovery._run",
        lambda *args, **kwargs: {"available": False, "returncode": None, "error": "missing"},
    )

    result = HardwareProbe().run()

    assert result.status == "PARTIAL"
    assert result.data["compute_platform"] == "unknown"
    assert len(result.warnings) == 3


def test_observed_hardware_overrides_urdf_and_records_difference() -> None:
    robot = RobotCapability(
        schema_version="robot-capability/v1",
        robot_id="sensor_bot",
        adapter="unbound",
        platform={},
        geometry={},
        sensors={
            "front_camera": {
                "modality": "camera_rgb",
                "model": "declared-camera",
                "urdf_link": "camera_link",
            }
        },
        features={},
    )

    result = _hardware_reconciliation(
        robot,
        {
            "components": [
                {
                    "kind": "sensor",
                    "name": "front_camera",
                    "modality": "camera_rgb",
                    "model": "observed-camera",
                    "driver": "uvcvideo",
                    "source": "sysfs_dev",
                }
            ]
        },
    )

    assert result["effective"][0]["model"] == "observed-camera"
    assert result["effective"][0]["effective_source"] == "probe"
    assert result["differences"] == [
        {
            "component": "front_camera",
            "field": "model",
            "urdf": "declared-camera",
            "observed": "observed-camera",
            "effective": "observed-camera",
        }
    ]


def make_application_project(root: Path) -> None:
    (root / "src/demo_nav").mkdir(parents=True)
    (root / "launch").mkdir()
    (root / "config").mkdir()
    (root / "usb_cam_launcher/config").mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        """[project]
name = "demo-nav"
version = "1.0.0"

[project.scripts]
demo-nav = "demo_nav.main:main"
""",
        encoding="utf-8",
    )
    (root / "package.xml").write_text(
        "<package format='3'><name>demo_nav</name><version>1.0.0</version>"
        "<description>test</description><maintainer email='dev@example.com'>dev</maintainer>"
        "<license>Apache-2.0</license></package>",
        encoding="utf-8",
    )
    (root / "src/demo_nav/main.py").write_text(
        """def configure(node):
    node.create_publisher(Twist, "/cmd_vel", 10)
    node.create_publisher(Image, "/image_raw", 10)
    node.create_subscription(Odometry, "/odom", lambda message: None, 10)
""",
        encoding="utf-8",
    )
    (root / "launch/demo.launch.py").write_text(
        'DeclareLaunchArgument("max_vel_x", default_value="0.45")\n'
        'DeclareLaunchArgument("enabled", default_value="true")\n'
        'Node(package="demo_nav", executable="demo-nav", name="navigator", '
        'condition=IfCondition(LaunchConfiguration("enabled")))\n'
        '# DeclareLaunchArgument("max_vel_x", default_value="9.9")\n',
        encoding="utf-8",
    )
    (root / "config/nav.yaml").write_text("controller:\n  max_vel_theta: 1.2\n", encoding="utf-8")
    (root / "usb_cam_launcher/config/params.yaml").write_text("camera: enabled\n", encoding="utf-8")
    (root / "README.md").write_text(
        "Documentation only; discovery must not execute text from this file.\n", encoding="utf-8"
    )


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("NVIDIA Jetson AGX Orin Developer Kit", "nvidia_jetson_orin"),
        ("Rockchip RK3588 Evaluation Board", "rockchip_rk3588"),
        ("Raspberry Pi 5 Model B Rev 1.0", "raspberry_pi"),
        (None, "unknown"),
    ],
)
def test_detect_compute_platform(model: str | None, expected: str) -> None:
    assert detect_compute_platform(model) == expected


def test_supported_ubuntu_versions_have_ros_discovery_defaults() -> None:
    assert UBUNTU_ROS_DEFAULTS == {
        "20.04": "foxy",
        "22.04": "humble",
        "24.04": "jazzy",
    }


def test_legacy_discovery_manifest_does_not_claim_the_current_runtime_version() -> None:
    manifest = DiscoveryRunManifest.model_validate(
        {
            "robot_id": "legacy-robot",
            "discovery_id": "disc-legacy",
            "files": [
                {
                    "path": "report.json",
                    "sha256": "0" * 64,
                    "size_bytes": 1,
                }
            ],
        }
    )

    assert manifest.producer.name == "rolo"
    assert manifest.producer.version == "unknown"


def test_application_probe_discovers_build_and_ros_surface(tmp_path: Path) -> None:
    make_application_project(tmp_path)

    result = ApplicationProbe().run([tmp_path])

    assert result.status == "SUCCEEDED"
    project = result.data["projects"][0]
    assert project["packages"] == ["demo-nav", "demo_nav"]
    assert project["entrypoints"] == [
        {"name": "demo-nav", "target": "demo_nav.main:main", "source": "pyproject"}
    ]
    assert project["ros_names"]["topics"] == ["/cmd_vel", "/image_raw", "/odom"]
    assert project["launch_files"] == ["launch/demo.launch.py"]
    assert {
        (candidate["field"], candidate["value"], candidate["source_kind"])
        for candidate in project["semantic_candidates"]
    } == {
        ("geometry.hard_max_linear_velocity_mps", 0.45, "launch"),
        ("geometry.hard_max_angular_velocity_radps", 1.2, "config"),
    }
    assert all(
        candidate["status"] == "DISCOVERED_UNVERIFIED" and candidate["safety_authority"] == "none"
        for candidate in project["semantic_candidates"]
    )
    assert "pyproject.toml" in project["manifest_digests"]


def test_application_probe_normalizes_python_and_ros_dependency_constraints(
    tmp_path: Path,
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        """[project]
name = "constraint-demo"
dependencies = [
  "requests[security]>=2.0; python_version >= '3'",
  "legacy-only; python_version < '0'",
]
""",
        encoding="utf-8",
    )
    (tmp_path / "package.xml").write_text(
        """<package format="3">
<name>constraint_demo</name><version>1.0.0</version>
<description>test</description><maintainer email="dev@example.com">dev</maintainer>
<license>Apache-2.0</license>
<exec_depend version_gte="1.2" version_lt="2.0">demo_msgs</exec_depend>
</package>
""",
        encoding="utf-8",
    )

    project = ApplicationProbe().run([tmp_path]).data["projects"][0]
    declarations = {
        (item["ecosystem"], item["name"]): item for item in project["dependency_declarations"]
    }

    assert declarations[("python", "requests")]["specifier"] == ">=2.0"
    assert declarations[("python", "requests")]["extras"] == ["security"]
    assert declarations[("python", "requests")]["applicable"] is True
    assert declarations[("python", "legacy-only")]["applicable"] is False
    assert declarations[("ros", "demo_msgs")]["specifier"] == "<2.0,>=1.2"


def test_unresolved_ros_name_template_is_retained_as_source_evidence_but_not_routable() -> None:
    bindings = _semantic_bindings(
        {
            "ros": ProbeResult(
                layer="ros",
                status="UNAVAILABLE",
                data={"topics": [], "ros_distro": "humble", "rmw": None},
            ),
            "application": ProbeResult(
                layer="application",
                status="SUCCEEDED",
                data={
                    "projects": [
                        {
                            "root": "/workspace",
                            "ros_names": {
                                "topics": [
                                    "/%s/camera_publisher/rgb0/image",
                                    "/controller/cmd_vel",
                                ]
                            },
                        }
                    ]
                },
            ),
        }
    )

    assert "semantic://actuator/base/velocity_command" in bindings
    assert "semantic://sensor/front_camera/image" not in bindings


def test_semantic_operation_candidates_are_driven_by_registry_linked_rules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    custom_rule = SemanticOperationRule(
        rule_id="custom_camera_status",
        topic_segments=["custom_feed"],
        semantic_uri="semantic://sensor/custom/feed",
        operations=["app.camera.status"],
    )
    monkeypatch.setattr(
        "rolo.stages.adapt.discovery.matching_semantic_rules",
        lambda _topic: [custom_rule],
    )
    bindings = _semantic_bindings(
        {
            "ros": ProbeResult(
                layer="ros",
                status="UNAVAILABLE",
                data={"topics": []},
            ),
            "application": ProbeResult(
                layer="application",
                status="SUCCEEDED",
                data={
                    "projects": [
                        {
                            "root": "C:\\workspace\\custom_robot",
                            "ros_names": {"topics": ["/vendor/custom_feed"]},
                        }
                    ]
                },
            ),
        }
    )

    candidates = _build_operation_candidates(bindings)

    assert [item.operation for item in candidates] == ["app.camera.status"]
    assert candidates[0].route_evidence[0].endpoint == "/vendor/custom_feed"


def test_semantic_rules_expand_beyond_camera_and_velocity() -> None:
    bindings = _semantic_bindings(
        {
            "ros": ProbeResult(
                layer="ros",
                status="SUCCEEDED",
                data={
                    "topics": [
                        "/front/scan [sensor_msgs/msg/LaserScan]",
                        "/chassis/imu [sensor_msgs/msg/Imu]",
                        "/gps/fix [sensor_msgs/msg/NavSatFix]",
                    ]
                },
            ),
            "application": ProbeResult(
                layer="application",
                status="SUCCEEDED",
                data={"projects": []},
            ),
        }
    )

    candidates = _build_operation_candidates(bindings)

    assert {item.operation for item in candidates} == {
        "app.gnss.sample",
        "app.imu.sample",
        "app.lidar.snapshot",
    }


def test_literal_topic_parameters_are_discovered_from_config_and_cpp_defaults() -> None:
    config_names = _extract_ros_config_names(
        """
        node:
          ros__parameters:
            scan_topic: /front/scan
            pointcloud_topic: /front/points
            serial_port: /dev/ttyUSB0
        """,
        suffix=".yaml",
    )
    cpp_names = _extract_parameter_default_ros_names(
        'declare_parameter<std::string>("scan_topic", "/fallback/scan");\n'
        'declare_parameter<std::string>("frame_id", "laser");\n'
    )

    assert config_names == {
        "topics": ["/front/points", "/front/scan"],
        "services": [],
        "actions": [],
    }
    assert cpp_names == {
        "topics": ["/fallback/scan"],
        "services": [],
        "actions": [],
    }


def test_application_probe_integrates_vendor_topic_defaults(tmp_path: Path) -> None:
    config = tmp_path / "driver" / "params" / "lidar.yaml"
    source = tmp_path / "driver" / "src" / "driver.cpp"
    config.parent.mkdir(parents=True)
    source.parent.mkdir(parents=True)
    config.write_text(
        "node:\n  ros__parameters:\n    scan_topic: /front/scan\t# vendor tab\n",
        encoding="utf-8",
    )
    source.write_text(
        'declare_parameter<std::string>("pointcloud_topic", "/front/points");\n',
        encoding="utf-8",
    )

    project = ApplicationProbe().run([tmp_path]).data["projects"][0]

    assert "/front/scan" in project["ros_names"]["topics"]
    assert "/front/points" in project["ros_names"]["topics"]


def test_discovery_service_persists_report_and_operation_candidates(tmp_path: Path) -> None:
    project = tmp_path / "application"
    make_application_project(project)
    registry = RobotRegistry(Path("tests/fixtures/robots"))
    registry.load()
    artifacts = ArtifactStore(tmp_path / "artifacts")

    report, run_path = DiscoveryService(artifacts).run(
        robot=registry.get("demo_diff"),
        urdf_path=Path("tests/fixtures/profiles/differential_drive.urdf"),
        source_roots=[project],
    )
    loaded = load_latest_report(artifacts.root, "demo_diff")

    assert run_path.is_file()
    assert loaded.discovery_id == report.discovery_id
    assert {candidate.operation for candidate in report.operation_candidates} >= {
        "app.teleop.velocity",
        "app.localization.status",
        "app.camera.snapshot",
    }
    camera = next(
        candidate
        for candidate in report.operation_candidates
        if candidate.operation == "app.camera.snapshot"
    )
    assert camera.status == "DISCOVERED_UNVERIFIED"
    latest_index = artifacts.root / "discovery/demo_diff/latest.json"
    assert latest_index.is_file()
    assert json.loads(latest_index.read_text(encoding="utf-8"))["discovery_id"] == (
        report.discovery_id
    )
    adapt_inputs = artifacts.root / "adapt/demo_diff/latest/inputs.json"
    assert adapt_inputs.is_file()
    assert json.loads(adapt_inputs.read_text(encoding="utf-8"))["semantic_context_ref"].endswith(
        "/semantic_context.json"
    )
    assert (artifacts.root / "diagnose/demo_diff/latest/inputs.json").is_file()
    assert (artifacts.root / "verify/demo_diff/latest/inputs.json").is_file()
    for layer in ("hw", "linux", "ros", "application"):
        assert (run_path.parent / f"{layer}.json").is_file()
    assert (run_path.parent / "capability_manifest.json").is_file()
    assert not (run_path.parent / "operation_candidates.json").exists()
    assert not (run_path.parent / "tool_catalog.json").exists()
    assert (run_path.parent / "software_summary.json").is_file()
    assert "packages" not in report.capability_manifest["observed"]["software_stack"]
    wiki_path = run_path.parent / "robot_wiki.md"
    manifest = json.loads((run_path.parent / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["producer"]["name"] == "rolo"
    assert manifest["producer"]["version"]
    assert wiki_path.is_file()
    wiki = wiki_path.read_text(encoding="utf-8")
    assert "## 应用程序与启动关系" in wiki
    assert "节点=navigator" in wiki
    assert "条件=if:enabled" in wiki
    assert "状态=`STATIC_UNVERIFIED`" in wiki
    assert "### URDF 结构与语义" in wiki
    assert "Links（5）" in wiki
    assert "front_camera_link" in wiki
    assert "front_camera | sensor/camera_rgb | unknown | front_camera_link | urdf" in wiki
    assert "URDF 状态" not in wiki
    assert "语义状态" not in wiki
    assert "URDF 来源" not in wiki
    assert "URDF SHA-256" not in wiki
    assert "## 启动拓扑（静态未验证）" not in wiki
    assert "robot_wiki.md" not in {item["path"] for item in manifest["files"]}
    wiki_path.write_text(
        wiki_path.read_text(encoding="utf-8") + "\n## 总工修正\nCAN-FD 总线已复核。\n",
        encoding="utf-8",
    )
    assert load_latest_report(artifacts.root, "demo_diff").discovery_id == report.discovery_id

    run_path.write_text(run_path.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_latest_report(artifacts.root, "demo_diff")


def test_discovery_accepts_target_manifest_without_controller_source_roots(
    tmp_path: Path,
) -> None:
    registry = RobotRegistry(Path("tests/fixtures/robots"))
    registry.load()
    artifacts = ArtifactStore(tmp_path / "artifacts")

    report, run_path = DiscoveryService(artifacts).run(
        robot=registry.get("demo_diff"),
        active_inputs=ActiveDiscoveryInputs(
            target_workspace_manifest_sha256="a" * 64,
        ),
    )
    active = json.loads(
        (run_path.parent / "active_discovery_report.json").read_text(
            encoding="utf-8"
        )
    )

    assert report.status.value != "FAILED"
    assert active["inputs"]["target_workspace_manifest_sha256"] == "a" * 64
    assert active["inputs"]["source_roots"] == []
    assert active["discovery_mode"]["level"] == DiscoveryModeLevel.TARGET_METADATA
    assert active["inputs"]["target_source_summary_sha256"] is None
    assert active["coverage"]["target_source_analysis"]["status"] == "NOT_PROVIDED"
    assert active["coverage"]["target_workspace_metadata"] == {
        "status": "OBSERVED",
        "records": 1,
        "truncated": False,
        "warnings": [],
    }
    assert report.probes["application"].data["projects"] == []


def test_discovery_consumes_verified_target_source_summary_without_local_scan(
    tmp_path: Path,
) -> None:
    registry = RobotRegistry(Path("tests/fixtures/robots"))
    registry.load()
    project = TargetSourceProjectSummary(
        root=".",
        file_count_scanned=4,
        scan_truncated=False,
        build_systems=["python/pyproject"],
        packages=["remote-driver"],
        declared_dependencies=["pyserial"],
        languages=["python"],
        manifest_digests={"pyproject.toml": "b" * 64},
        source_revision="c" * 40,
    )
    target_probe = ProbeResult(
        layer="application",
        status="SUCCEEDED",
        data={
            "projects": [project.model_dump(mode="json")],
            "route_evidence": [],
            "target_source_discovery": {
                "target_id": "demo_diff",
                "robot_id": "demo_diff",
                "workspace_id": "workspace-demo-diff",
                "request_sha256": "d" * 64,
                "summary_sha256": "e" * 64,
                "observed_at": "2026-08-26T09:00:00Z",
            },
        },
    )

    report, run_path = DiscoveryService(ArtifactStore(tmp_path / "artifacts")).run(
        robot=registry.get("demo_diff"),
        active_inputs=ActiveDiscoveryInputs(
            target_workspace_manifest_sha256="a" * 64,
        ),
        target_application_probe=target_probe,
    )
    active = json.loads(
        (run_path.parent / "active_discovery_report.json").read_text(encoding="utf-8")
    )

    assert report.status.value != "FAILED"
    assert report.probes["application"].data["projects"][0]["packages"] == [
        "remote-driver"
    ]
    assert report.source_roots == []
    assert active["discovery_mode"]["level"] == DiscoveryModeLevel.TARGET_SOURCE
    assert active["inputs"]["target_source_summary_sha256"] == "e" * 64
    assert active["coverage"]["target_source_analysis"]["status"] == "OBSERVED"

    with pytest.raises(ValueError, match="robot identity"):
        DiscoveryService(ArtifactStore(tmp_path / "other-artifacts")).run(
            robot=registry.get("demo_diff"),
            active_inputs=ActiveDiscoveryInputs(
                target_workspace_manifest_sha256="a" * 64,
            ),
            target_application_probe=target_probe.model_copy(
                update={
                    "data": {
                        **target_probe.data,
                        "target_source_discovery": {
                            **target_probe.data["target_source_discovery"],
                            "robot_id": "other-robot",
                        },
                    }
                }
            ),
        )


def test_unresolved_urdf_semantics_flow_into_debug_and_test_inputs(tmp_path: Path) -> None:
    project = tmp_path / "application"
    make_application_project(project)
    robot = RobotCapability.model_validate(
        {
            "schema_version": "robot-capability/v1",
            "robot_id": "structural_unit",
            "adapter": "unbound",
            "platform": {"drive_model": "unresolved"},
            "geometry": {},
            "sensors": {},
            "features": {
                "enrollment": {
                    "unresolved_semantics": [
                        "platform.drive_model",
                        "geometry.hard_max_linear_velocity_mps",
                        "geometry.hard_max_angular_velocity_radps",
                    ]
                }
            },
        }
    )
    artifacts = ArtifactStore(tmp_path / "artifacts")

    structural_urdf = tmp_path / "structural_unit.urdf"
    structural_urdf.write_text(
        '<robot name="structural_unit"><link name="base_link"/></robot>',
        encoding="utf-8",
    )
    DiscoveryService(artifacts).run(robot=robot, urdf_path=structural_urdf, source_roots=[project])

    for stage in ("diagnose", "verify"):
        inputs = json.loads(
            (artifacts.root / stage / "structural_unit/latest/inputs.json").read_text(
                encoding="utf-8"
            )
        )
        assert "geometry.hard_max_linear_velocity_mps" in inputs["unresolved_semantics"]
        assert {candidate["field"] for candidate in inputs["semantic_candidates"]} == {
            "geometry.hard_max_linear_velocity_mps",
            "geometry.hard_max_angular_velocity_radps",
        }
        assert all(
            candidate["safety_authority"] == "none" for candidate in inputs["semantic_candidates"]
        )


def test_discovery_parses_registered_urdf_and_keeps_motion_unapproved(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "discovery-rover"\n', encoding="utf-8"
    )
    (tmp_path / "README.md").write_text("discovery rover guide", encoding="utf-8")
    config_root = tmp_path / "config"
    result = EnrollmentService(config_root=config_root).enroll(
        robot_id="discovery_rover",
    )
    registered = RobotCapability.model_validate(load_yaml(result.capability_path))
    assert registered.geometry == {}

    artifacts = ArtifactStore(tmp_path / "artifacts")
    report, _ = DiscoveryService(artifacts).run(
        robot=registered,
        urdf_path=Path("tests/fixtures/profiles/differential_drive.urdf"),
        source_roots=[tmp_path],
    )
    discovered = report.capability_manifest["expected_profile"]

    assert discovered["platform"]["drive_model"] == "differential"
    assert discovered["geometry"]["hard_max_linear_velocity_mps"] == 0.8
    enrollment = discovered["features"]["enrollment"]
    assert enrollment["urdf_status"] == "SCANNED"
    assert enrollment["semantic_status"] == "RESOLVED"
    assert enrollment["motion_safety_status"] == "UNAPPROVED"


def test_discovery_records_hash_for_supplied_urdf(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "hash-rover"\n', encoding="utf-8")
    (tmp_path / "README.md").write_text("hash rover guide", encoding="utf-8")
    profile_path = tmp_path / "robot.urdf"
    profile_path.write_text('<robot name="hash_rover"><link name="base_link"/></robot>')
    config_root = tmp_path / "config"
    result = EnrollmentService(config_root=config_root).enroll(
        robot_id="hash_rover",
    )
    registered = RobotCapability.model_validate(load_yaml(result.capability_path))
    report, _ = DiscoveryService(ArtifactStore(tmp_path / "artifacts")).run(
        robot=registered,
        urdf_path=profile_path,
        source_roots=[tmp_path],
    )

    enrollment = report.capability_manifest["expected_profile"]["features"]["enrollment"]
    assert enrollment["profile_path"] == str(profile_path.resolve())
    assert len(enrollment["profile_sha256"]) == 64


def test_registration_defers_semantic_validation_until_discovery(tmp_path: Path) -> None:
    profile_path = tmp_path / "deferred.urdf"
    profile_path.write_text(
        """<robot name="deferred_rover">
<link name="base_link"/>
<rolo drive_model="unsupported_drive"/>
</robot>
""",
        encoding="utf-8",
    )
    result = EnrollmentService(config_root=tmp_path / "config").enroll(
        robot_id="deferred_rover",
    )
    assert result.status == "IDENTITY_REGISTERED"
    registered = RobotCapability.model_validate(load_yaml(result.capability_path))

    with pytest.raises(ValueError, match="unsupported drive_model"):
        DiscoveryService(ArtifactStore(tmp_path / "artifacts")).run(
            robot=registered,
            urdf_path=profile_path,
            source_roots=[tmp_path],
        )


def test_discovery_allows_missing_hardware_profile_in_test_environment(tmp_path: Path) -> None:
    project = tmp_path / "application"
    make_application_project(project)
    enrollment = EnrollmentService(config_root=tmp_path / "config").enroll(
        robot_id="profileless_robot"
    )
    robot = RobotCapability.model_validate(load_yaml(enrollment.capability_path))

    report, path = DiscoveryService(ArtifactStore(tmp_path / "artifacts")).run(
        robot=robot,
        source_roots=[project],
    )

    expected = report.capability_manifest["expected_profile"]
    state = expected["features"]["enrollment"]
    assert path.is_file()
    assert state["urdf_status"] == "NOT_PROVIDED"
    assert state["semantic_status"] == "PARTIAL"
    assert "platform.drive_model" in state["unresolved_semantics"]
    assert report.status == "PARTIAL"


@pytest.mark.parametrize(
    ("vendor", "source", "expected_candidates"),
    [
        (
            "unitree_go1",
            'send_udp("192.168.123.10", 8007, high_command)\n',
            set(),
        ),
        (
            "wheeltec",
            'node.create_publisher(Twist, "/cmd_vel", 10)\n'
            'node.create_subscription(Odometry, "/odom", callback, 10)\n',
            {"app.teleop.velocity", "app.localization.status"},
        ),
    ],
)
def test_source_only_vendor_projects_never_create_verified_operations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    vendor: str,
    source: str,
    expected_candidates: set[str],
) -> None:
    project = tmp_path / vendor
    project.mkdir()
    (project / "pyproject.toml").write_text(
        f'[project]\nname = "{vendor}"\n\n[project.scripts]\n{vendor} = "driver:main"\n',
        encoding="utf-8",
    )
    (project / "driver.py").write_text(source, encoding="utf-8")
    monkeypatch.setattr(
        "rolo.stages.adapt.discovery.RosProbe.run",
        lambda self: ProbeResult(
            layer="ros",
            status="UNAVAILABLE",
            data={"nodes": [], "topics": [], "services": [], "actions": []},
        ),
    )
    registry = RobotRegistry(Path("tests/fixtures/robots"))
    registry.load()

    report, _ = DiscoveryService(ArtifactStore(tmp_path / "artifacts")).run(
        robot=registry.get("demo_diff"),
        source_roots=[project],
    )
    candidates = {candidate.operation: candidate for candidate in report.operation_candidates}
    catalog = materialize_active_catalog(report)

    assert set(candidates) == expected_candidates
    assert all(candidate.status == "DISCOVERED_UNVERIFIED" for candidate in candidates.values())
    assert all(
        route.evidence_origin == "DECLARED_STATIC"
        for candidate in candidates.values()
        for route in candidate.route_evidence
    )
    assert all(
        route.endpoint.startswith("/")
        for candidate in candidates.values()
        for route in candidate.route_evidence
        if route.kind.startswith("ros_")
    )
    assert not any(tool.availability == "VERIFIED" for tool in catalog.tools)


def test_discovery_and_product_registry_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "application"
    make_application_project(project)
    monkeypatch.setenv("ROLO_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("WIKI_INSIGHTS_AGENT_ENABLED", "false")
    get_settings.cache_clear()
    runner = CliRunner()

    discovered = runner.invoke(
        app,
        [
            "adapt",
            "discover",
            "run",
            "--robot",
            "demo_diff",
            "--urdf",
            str(Path("tests/fixtures/profiles/differential_drive.urdf").resolve()),
            "--source-root",
            str(project),
        ],
    )
    registry = runner.invoke(app, ["tool", "registry", "--layer", "hw"])
    catalog = runner.invoke(app, ["tool", "catalog", "--robot", "demo_diff"])
    review = runner.invoke(app, ["adapt", "discover", "review", "--robot", "demo_diff"])

    get_settings.cache_clear()
    assert discovered.exit_code == 0, discovered.output
    assert '"status": "PARTIAL"' in discovered.output
    assert registry.exit_code == 0, registry.output
    assert '"operation": "hw.inventory.scan"' in registry.output
    assert catalog.exit_code == 2
    assert review.exit_code == 0, review.output
    assert "# 机器人 Wiki：demo_diff" in review.output
    assert "## 运行时与通信接口" in review.output
    assert "### ROS 运行时与拓扑" in review.output


def test_product_registry_conservatively_classifies_motion_operations() -> None:
    from rolo.stages.adapt.operation_registry import canonical_operation_registry

    operations = {item.operation: item for item in canonical_operation_registry().operations}
    assert operations["app.base.velocity"].access == "write"
    assert operations["app.base.velocity"].risk == "R3"
    assert operations["app.base.status"].access == "read"
    assert operations["app.base.status"].risk == "R0"
    assert operations["app.safety.emergency_stop"].access == "write"
    assert operations["app.safety.emergency_stop"].risk == "R3"
    assert operations["app.safety.emergency_stop"].cancelable is False
    assert operations["linux.host.reboot"].cancelable is False


def test_product_registry_exposes_a_complete_authored_contract_vocabulary() -> None:
    from rolo.stages.adapt.operation_registry import canonical_operation_registry

    operations = {item.operation: item for item in canonical_operation_registry().operations}
    velocity = operations["app.teleop.velocity"]
    assert velocity.contract_lifecycle.value == "GATEABLE"
    assert velocity.contract_version == "1.1.0"
    assert velocity.data_classification.value == "INTERNAL"
    assert velocity.contract_sha256 is not None
    assert velocity.input_schema["required"] == ["linear_x_mps", "angular_z_radps"]
    assert velocity.canonical_cli[-4:] == [
        "--robot",
        "{robot_id}",
        "--input",
        "{input_json}",
    ]
    assert all(
        item.contract_lifecycle.value in {"GATEABLE", "RELEASED"}
        for item in operations.values()
    )


def test_incomplete_contract_definition_still_cannot_enter_conformance() -> None:
    from rolo.contract_catalog import ContractLifecycle
    from rolo.stages.adapt.operation_registry import (
        canonical_operation_registry,
        validate_definition_contract,
    )

    definition = next(
        item
        for item in canonical_operation_registry().operations
        if item.operation == "hw.actuator.command"
    )
    incomplete_definition = definition.model_copy(
        update={"contract_lifecycle": ContractLifecycle.DRAFT}
    )

    with pytest.raises(ValueError, match="contract is incomplete"):
        validate_definition_contract(incomplete_definition)
