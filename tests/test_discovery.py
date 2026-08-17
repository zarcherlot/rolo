from pathlib import Path

import pytest
from typer.testing import CliRunner

from robot_loop.artifacts import ArtifactStore
from robot_loop.cli import app
from robot_loop.config import get_settings
from robot_loop.discovery import (
    ApplicationProbe,
    DiscoveryService,
    detect_compute_platform,
    load_latest_report,
)
from robot_loop.registry import RobotRegistry


def make_application_project(root: Path) -> None:
    (root / "src/demo_nav").mkdir(parents=True)
    (root / "launch").mkdir()
    (root / "config").mkdir()
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
    node.create_subscription(Odometry, "/odom", lambda message: None, 10)
""",
        encoding="utf-8",
    )
    (root / "launch/demo.launch.py").write_text("# launch placeholder\n", encoding="utf-8")
    (root / "config/nav.yaml").write_text("controller: demo\n", encoding="utf-8")
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


def test_application_probe_discovers_build_and_ros_surface(tmp_path: Path) -> None:
    make_application_project(tmp_path)

    result = ApplicationProbe().run([tmp_path])

    assert result.status == "SUCCEEDED"
    project = result.data["projects"][0]
    assert project["packages"] == ["demo-nav", "demo_nav"]
    assert project["entrypoints"] == [
        {"name": "demo-nav", "target": "demo_nav.main:main", "source": "pyproject"}
    ]
    assert project["ros_names"]["topics"] == ["/cmd_vel", "/odom"]
    assert project["launch_files"] == ["launch/demo.launch.py"]
    assert "pyproject.toml" in project["manifest_digests"]


def test_discovery_service_persists_report_and_catalog(tmp_path: Path) -> None:
    project = tmp_path / "application"
    make_application_project(project)
    registry = RobotRegistry(Path("configs/robots"))
    registry.load()
    artifacts = ArtifactStore(tmp_path / "artifacts")

    report, run_path = DiscoveryService(artifacts).run(
        robot=registry.get("robot_a"), source_roots=[project]
    )
    loaded = load_latest_report(artifacts.root, "robot_a")

    assert run_path.is_file()
    assert loaded.discovery_id == report.discovery_id
    assert {tool.operation for tool in report.tool_catalog} >= {
        "hw.inventory.scan",
        "linux.host.inspect",
        "ros.graph.snapshot",
        "app.robot.discover",
        "tool.catalog",
        "app.teleop.velocity",
        "app.localization.status",
    }
    assert (artifacts.root / "discovery/robot_a/latest/tool_catalog.json").is_file()
    assert (artifacts.root / "discovery/robot_a/latest/capability_manifest.json").is_file()
    assert (artifacts.root / "discovery/robot_a/latest/application.json").is_file()
    assert (run_path.parent / "capability_manifest.json").is_file()
    assert (run_path.parent / "tool_catalog.json").is_file()


def test_discovery_and_tool_catalog_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = tmp_path / "application"
    make_application_project(project)
    monkeypatch.setenv("ROBOT_LOOP_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    get_settings.cache_clear()
    runner = CliRunner()

    discovered = runner.invoke(
        app,
        ["discover", "run", "--robot", "robot_a", "--source-root", str(project)],
    )
    catalog = runner.invoke(app, ["tool", "catalog", "--robot", "robot_a"])

    get_settings.cache_clear()
    assert discovered.exit_code == 0, discovered.output
    assert '"status": "PARTIAL"' in discovered.output
    assert catalog.exit_code == 0, catalog.output
    assert '"operation": "hw.inventory.scan"' in catalog.output
