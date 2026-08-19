import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from rolo.cli import app
from rolo.core.artifacts import ArtifactStore
from rolo.core.models import DiscoveryStatus, ProbeResult
from rolo.core.registry import RobotRegistry
from rolo.stages.adapt.active_discovery import (
    ActiveDiscoveryAnalyzer,
    ActiveDiscoveryInputs,
    ActiveProbeMode,
    DiscoveryModeLevel,
    HelpProbeResult,
    HelpProbeStatus,
    run_bounded_help,
)
from rolo.stages.adapt.discovery import ApplicationProbe, DiscoveryService

CREATED_AT = datetime(2026, 8, 18, tzinfo=timezone.utc)


def make_analyzer(
    *,
    inputs: ActiveDiscoveryInputs,
    projects: list[dict[str, object]],
    run_root: Path,
    ros_data: dict[str, object] | None = None,
    evidence_text: dict[Path, str] | None = None,
) -> ActiveDiscoveryAnalyzer:
    return ActiveDiscoveryAnalyzer(
        inputs=inputs,
        projects=projects,
        ros_probe=ProbeResult(
            layer="ros",
            status=DiscoveryStatus.SUCCEEDED,
            data=ros_data or {"nodes": [], "topics": [], "services": [], "actions": []},
        ),
        run_root=run_root,
        artifact_prefix="artifact://discovery/demo/runs/disc-test",
        evidence_text=evidence_text,
    )


def build_report(analyzer: ActiveDiscoveryAnalyzer):
    return analyzer.build(
        discovery_id="disc-test",
        robot_id="demo",
        technical_status="SUCCEEDED",
        created_at=CREATED_AT,
    )


def test_primary_evidence_input_is_required() -> None:
    with pytest.raises(ValidationError, match="at least one --build-root"):
        ActiveDiscoveryInputs()


def test_documentation_led_report_uses_source_only_as_supporting_evidence(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    (source / "src").mkdir(parents=True)
    (source / "pyproject.toml").write_text(
        """[project]
name = "demo-app"
dependencies = ["rclpy>=3", "paho-mqtt"]

[project.scripts]
demo-app = "demo.main:main"
""",
        encoding="utf-8",
    )
    (source / "src/main.py").write_text(
        """# MQTT bridge
def configure(node):
    node.create_publisher(Twist, "/cmd_vel", 10)
""",
        encoding="utf-8",
    )
    (source / "README.md").write_text("demo-app operator guide", encoding="utf-8")
    projects = ApplicationProbe().run([source]).data["projects"]

    report = build_report(
        make_analyzer(
            inputs=ActiveDiscoveryInputs(source_roots=[source]),
            projects=projects,
            run_root=tmp_path / "run",
        )
    )

    assert report.discovery_mode.level == DiscoveryModeLevel.DOC_PROBE
    assert report.evidence_policy.primary_order == [
        "BUILD_ARTIFACT",
        "DOCUMENTATION",
        "PROBE",
    ]
    assert report.evidence_policy.source_role == "SUPPORTING_ONLY"
    executable = report.executables[0]
    assert executable.name == "demo-app"
    assert executable.origin == "SOURCE_DECLARED"
    assert executable.source_analysis.languages == ["python"]
    assert executable.source_analysis.declared_dependencies == ["paho-mqtt", "rclpy"]
    assert executable.communication.network["protocols"] == ["mqtt"]
    assert executable.communication.ros["publishers"][0]["name"] == "/cmd_vel"
    assert executable.evidence["source_support"] == [str(source.resolve())]


def test_supporting_source_scan_ignores_vendored_third_party_trees(tmp_path: Path) -> None:
    source = tmp_path / "source"
    vendor = source / "third-party" / "dependency"
    vendor.mkdir(parents=True)
    (source / "pyproject.toml").write_text('[project]\nname = "demo"\n', encoding="utf-8")
    (source / "README.md").write_text("demo operator guide", encoding="utf-8")
    (vendor / "README.md").write_text("vendored dependency guide", encoding="utf-8")
    (vendor / "CMakeLists.txt").write_text(
        "add_executable(vendor_test vendor.cpp)", encoding="utf-8"
    )

    project = ApplicationProbe().run([source]).data["projects"][0]

    assert project["file_count_scanned"] == 2
    assert project["readmes"] == ["README.md"]
    assert "vendor_test" not in project["build_targets"]


def test_multiple_source_projects_keep_executable_evidence_isolated(tmp_path: Path) -> None:
    specifications = [
        ("alpha", "alpha-only", "mqtt", "/alpha_cmd"),
        ("beta", "beta-only", "grpc", "/beta_cmd"),
    ]
    roots: list[Path] = []
    for name, dependency, protocol, topic in specifications:
        root = tmp_path / name
        root.mkdir()
        roots.append(root)
        (root / "pyproject.toml").write_text(
            f'''[project]
name = "{name}"
dependencies = ["{dependency}"]

[project.scripts]
{name} = "{name}.main:main"
''',
            encoding="utf-8",
        )
        (root / "main.py").write_text(
            f'''# {protocol}
def configure(node):
    node.create_publisher(Twist, "{topic}", 10)
''',
            encoding="utf-8",
        )
        (root / "README.md").write_text(f"{name} operator guide", encoding="utf-8")

    scan = ApplicationProbe().scan(roots)
    report = build_report(
        make_analyzer(
            inputs=ActiveDiscoveryInputs(source_roots=roots),
            projects=scan.probe.data["projects"],
            run_root=tmp_path / "run",
            evidence_text=scan.evidence_text,
        )
    )
    executables = {executable.name: executable for executable in report.executables}

    assert executables["alpha"].source_analysis.declared_dependencies == ["alpha-only"]
    assert executables["beta"].source_analysis.declared_dependencies == ["beta-only"]
    assert executables["alpha"].communication.network["protocols"] == ["mqtt"]
    assert executables["beta"].communication.network["protocols"] == ["grpc"]
    assert [item["name"] for item in executables["alpha"].communication.ros["publishers"]] == [
        "/alpha_cmd"
    ]
    assert [item["name"] for item in executables["beta"].communication.ros["publishers"]] == [
        "/beta_cmd"
    ]


def test_active_analysis_reuses_source_evidence_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "pyproject.toml").write_text(
        """[project]
name = "cached-app"

[project.scripts]
cached-app = "cached.main:main"
""",
        encoding="utf-8",
    )
    (source / "README.md").write_text("Run cached-app --cached over MQTT.", encoding="utf-8")
    (source / "cached.launch.py").write_text(
        'Node(package="cached_pkg", executable="cached-app", name="cached")',
        encoding="utf-8",
    )
    scan = ApplicationProbe().scan([source])

    def forbidden_read(_: Path) -> None:
        raise AssertionError(
            "active analysis reread source text instead of using its scan snapshot"
        )

    monkeypatch.setattr(
        "rolo.stages.adapt.active_discovery._read_bounded_text",
        forbidden_read,
    )
    report = build_report(
        make_analyzer(
            inputs=ActiveDiscoveryInputs(source_roots=[source]),
            projects=scan.probe.data["projects"],
            run_root=tmp_path / "run",
            evidence_text=scan.evidence_text,
        )
    )

    executable = report.executables[0]
    assert executable.invocation.arguments == ["--cached"]
    assert executable.launch_analysis.packages == ["cached_pkg"]


def test_artifact_doc_mode_statically_extracts_launch_without_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install = tmp_path / "install"
    docs = tmp_path / "docs"
    launch = tmp_path / "launch"
    (install / "bin").mkdir(parents=True)
    docs.mkdir()
    launch.mkdir()
    executable_path = install / "bin/vendor-driver.exe"
    executable_path.write_bytes(b"MZ" + b"\0" * 62)
    (docs / "README.md").write_text(
        "Run vendor-driver --port 9000 to expose a TCP endpoint.", encoding="utf-8"
    )
    (launch / "driver.launch.py").write_text(
        """DeclareLaunchArgument("robot_ns", default_value="robot")
Node(package="vendor_pkg", executable="vendor-driver.exe", name="driver",
     namespace=LaunchConfiguration("robot_ns"),
     remappings=[("/cmd", "/robot/cmd")])
# Node(package="ignored_pkg", executable="commented-out", name="ghost")
""",
        encoding="utf-8",
    )

    def forbidden_popen(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"launch or executable was unexpectedly run: {args}, {kwargs}")

    monkeypatch.setattr("rolo.stages.adapt.active_discovery.subprocess.Popen", forbidden_popen)
    report = build_report(
        make_analyzer(
            inputs=ActiveDiscoveryInputs(
                install_roots=[install],
                document_roots=[docs],
                launch_roots=[launch],
            ),
            projects=[],
            run_root=tmp_path / "run",
        )
    )

    assert report.discovery_mode.level == DiscoveryModeLevel.ARTIFACT_DOC
    executable = report.executables[0]
    assert executable.origin == "DISCOVERED_ARTIFACT"
    assert executable.launch_analysis.available is True
    assert executable.launch_analysis.packages == ["vendor_pkg"]
    assert executable.launch_analysis.nodes == ["driver"]
    assert executable.launch_analysis.arguments == ["robot_ns"]
    assert executable.communication.ros["remappings"] == [{"from": "/cmd", "to": "/robot/cmd"}]
    assert all(item.name != "commented-out" for item in report.executables)
    assert executable.communication.network["protocols"] == ["tcp"]


def test_python_launch_extracts_node_scoped_condition_and_package_urdf(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    launch = source / "launch"
    launch.mkdir(parents=True)
    (source / "package.xml").write_text(
        "<package><name>demo_bringup</name></package>", encoding="utf-8"
    )
    (launch / "description.launch.py").write_text(
        """Node(
    package="robot_state_publisher",
    executable="robot_state_publisher",
    name="state_publisher",
    arguments=[os.path.join(
        get_package_share_directory("demo_description"), "urdf", "demo.urdf"
    )],
    condition=IfCondition(LaunchConfiguration("publish_description")),
)
# Node(package="tf2_ros", executable="static_transform_publisher", name="ghost")
""",
        encoding="utf-8",
    )
    scan = ApplicationProbe().scan([source])

    report = build_report(
        make_analyzer(
            inputs=ActiveDiscoveryInputs(source_roots=[source]),
            projects=scan.probe.data["projects"],
            run_root=tmp_path / "run",
            evidence_text=scan.evidence_text,
        )
    )

    executable = next(item for item in report.executables if item.name == "robot_state_publisher")
    assert executable.launch_analysis.conditions == ["if:publish_description"]
    assert executable.launch_analysis.urdf_references == [
        "package://demo_description/urdf/demo.urdf"
    ]
    assert executable.launch_analysis.verification == "STATIC_UNVERIFIED"
    assert all(item.name != "static_transform_publisher" for item in report.executables)


def test_artifact_and_documentation_override_conflicting_source_support(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    install = tmp_path / "install"
    docs = tmp_path / "docs"
    source.mkdir()
    (install / "bin").mkdir(parents=True)
    docs.mkdir()
    (source / "pyproject.toml").write_text(
        """[project]
name = "vendor-driver"

[project.scripts]
vendor-driver = "driver:main"
""",
        encoding="utf-8",
    )
    (source / "driver.py").write_text("# vendor-driver uses MQTT", encoding="utf-8")
    executable_path = install / "bin" / "vendor-driver.exe"
    executable_path.write_bytes(b"MZ" + b"\0" * 62)
    (docs / "vendor-driver.md").write_text(
        "The deployed vendor-driver uses gRPC.", encoding="utf-8"
    )
    scan = ApplicationProbe().scan([source])

    report = build_report(
        make_analyzer(
            inputs=ActiveDiscoveryInputs(
                source_roots=[source],
                install_roots=[install],
                document_roots=[docs],
            ),
            projects=scan.probe.data["projects"],
            run_root=tmp_path / "run",
            evidence_text=scan.evidence_text,
        )
    )

    assert report.discovery_mode.level == DiscoveryModeLevel.ARTIFACT_DOC
    executable = report.executables[0]
    assert executable.communication.network["protocols"] == ["grpc"]
    assert executable.evidence["source_support"] == [str(source.resolve())]


def test_build_root_is_usable_primary_artifact_evidence(tmp_path: Path) -> None:
    build = tmp_path / "build"
    docs = tmp_path / "docs"
    (build / "bin").mkdir(parents=True)
    docs.mkdir()
    executable_path = build / "bin" / "vendor-driver.exe"
    executable_path.write_bytes(b"MZ" + b"\0" * 62)
    (docs / "vendor-driver.md").write_text("Run vendor-driver over MQTT.", encoding="utf-8")

    report = build_report(
        make_analyzer(
            inputs=ActiveDiscoveryInputs(
                build_roots=[build],
                document_roots=[docs],
            ),
            projects=[],
            run_root=tmp_path / "run",
        )
    )

    assert report.discovery_mode.level == DiscoveryModeLevel.ARTIFACT_DOC
    assert report.executables[0].origin == "DISCOVERED_BUILD_ARTIFACT"
    assert report.executables[0].artifact_analysis.build_roots == [str(build.resolve())]


def test_artifact_documents_and_configs_are_isolated_per_executable(tmp_path: Path) -> None:
    install = tmp_path / "install"
    docs = tmp_path / "docs"
    (install / "bin").mkdir(parents=True)
    (install / "config").mkdir()
    docs.mkdir()
    (install / "bin" / "alpha.exe").write_bytes(b"MZ" + b"\0" * 62)
    (install / "bin" / "beta.exe").write_bytes(b"MZ" + b"\0" * 62)
    (install / "config" / "alpha.yaml").write_text("alpha: mqtt", encoding="utf-8")
    (install / "config" / "beta.yaml").write_text("beta: grpc", encoding="utf-8")
    (docs / "alpha.md").write_text("alpha uses MQTT", encoding="utf-8")
    (docs / "beta.md").write_text("beta uses gRPC", encoding="utf-8")

    report = build_report(
        make_analyzer(
            inputs=ActiveDiscoveryInputs(
                install_roots=[install],
                document_roots=[docs],
            ),
            projects=[],
            run_root=tmp_path / "run",
        )
    )
    executables = {item.name: item for item in report.executables}

    assert executables["alpha.exe"].communication.network["protocols"] == ["mqtt"]
    assert executables["beta.exe"].communication.network["protocols"] == ["grpc"]
    assert executables["alpha.exe"].documentation_analysis.references == [
        str((docs / "alpha.md").resolve())
    ]
    assert executables["beta.exe"].documentation_analysis.references == [
        str((docs / "beta.md").resolve())
    ]
    assert executables["alpha.exe"].artifact_analysis.configuration_files == [
        str((install / "config" / "alpha.yaml").resolve())
    ]
    assert executables["beta.exe"].artifact_analysis.configuration_files == [
        str((install / "config" / "beta.yaml").resolve())
    ]
    assert all(
        "capability_candidates" not in type(item).model_fields for item in executables.values()
    )


def test_help_probe_runs_only_explicit_executable_and_report_omits_raw_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    explicit = tmp_path / "explicit.exe"
    install = tmp_path / "install"
    install.mkdir()
    discovered = install / "discovered.exe"
    explicit.write_bytes(b"MZ" + b"\0" * 62)
    discovered.write_bytes(b"MZ" + b"\0" * 62)
    called: list[Path] = []

    def fake_help(path: Path, output_path: Path) -> HelpProbeResult:
        called.append(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            "usage: explicit [--mode MODE] {status,scan}\nRAW_SECRET_CONTENT\n",
            encoding="utf-8",
        )
        return HelpProbeResult(
            status=HelpProbeStatus.SUCCEEDED,
            exit_code=0,
            output_bytes=64,
        )

    monkeypatch.setattr("rolo.stages.adapt.active_discovery.run_bounded_help", fake_help)
    report = build_report(
        make_analyzer(
            inputs=ActiveDiscoveryInputs(
                install_roots=[install],
                executables=[explicit],
                active_probe=ActiveProbeMode.HELP,
            ),
            projects=[],
            run_root=tmp_path / "run",
        )
    )

    assert called == [explicit.resolve()]
    assert report.discovery_mode.level == DiscoveryModeLevel.BINARY_ONLY
    explicit_report = next(item for item in report.executables if item.origin == "EXPLICIT")
    discovered_report = next(
        item for item in report.executables if item.origin == "DISCOVERED_ARTIFACT"
    )
    assert explicit_report.invocation.arguments == ["--mode"]
    assert explicit_report.invocation.help_probe.usage == [
        "usage: explicit [--mode MODE] {status,scan}"
    ]
    assert discovered_report.invocation.help_probe.status == HelpProbeStatus.NOT_PROBED
    assert "RAW_SECRET_CONTENT" not in report.model_dump_json()


def test_help_probe_enforces_output_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("rolo.stages.adapt.active_discovery.MAX_HELP_BYTES", 32)
    output = tmp_path / "python-help.txt"

    result = run_bounded_help(Path(sys.executable), output)

    assert result.status == HelpProbeStatus.OUTPUT_LIMIT
    assert result.truncated is True
    assert result.output_bytes > 32
    assert len(output.read_bytes()) == 32


def test_help_probe_timeout_does_not_wait_for_blocked_output_reader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class BlockedStdout:
        def read(self, _: int) -> bytes:
            time.sleep(0.2)
            return b""

    class FakeProcess:
        stdout = BlockedStdout()
        returncode: int | None = None

        def poll(self) -> int | None:
            return self.returncode

        def terminate(self) -> None:
            self.returncode = -15

        def kill(self) -> None:
            self.returncode = -9

        def wait(self, timeout: float) -> int:
            del timeout
            return self.returncode or 0

    monkeypatch.setattr(
        "rolo.stages.adapt.active_discovery.subprocess.Popen",
        lambda *args, **kwargs: FakeProcess(),
    )
    monkeypatch.setattr("rolo.stages.adapt.active_discovery.HELP_TIMEOUT_S", 0.01)

    result = run_bounded_help(tmp_path / "blocked.exe", tmp_path / "help.txt")

    assert result.status == HelpProbeStatus.TIMED_OUT
    assert result.exit_code == -15


def test_help_probe_count_limit_is_reported_without_running_remaining_binaries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executables = [tmp_path / "first.exe", tmp_path / "second.exe"]
    for executable in executables:
        executable.write_bytes(b"MZ" + b"\0" * 62)
    called: list[Path] = []

    def fake_help(path: Path, output_path: Path) -> HelpProbeResult:
        del output_path
        called.append(path)
        return HelpProbeResult(status=HelpProbeStatus.SUCCEEDED, exit_code=0)

    monkeypatch.setattr("rolo.stages.adapt.active_discovery.MAX_HELP_PROBES", 1)
    monkeypatch.setattr("rolo.stages.adapt.active_discovery.run_bounded_help", fake_help)
    report = build_report(
        make_analyzer(
            inputs=ActiveDiscoveryInputs(
                executables=executables,
                active_probe=ActiveProbeMode.HELP,
            ),
            projects=[],
            run_root=tmp_path / "run",
        )
    )

    assert called == [executables[0].resolve()]
    assert report.technical_status == "PARTIAL"
    assert report.coverage["help_probes"].status == "PARTIAL"
    assert report.executables[1].invocation.help_probe.status == "BLOCKED_BY_POLICY"
    assert report.executables[1].safety["possible_side_effects"] == []


def test_ros_runtime_evidence_is_attributed_only_when_requested(tmp_path: Path) -> None:
    install = tmp_path / "install"
    install.mkdir()
    (install / "driver.exe").write_bytes(b"MZ" + b"\0" * 62)
    ros_data = {
        "nodes": ["/driver"],
        "topics": ["/status"],
        "services": ["/reset"],
        "actions": [],
    }
    static_report = build_report(
        make_analyzer(
            inputs=ActiveDiscoveryInputs(install_roots=[install]),
            projects=[],
            run_root=tmp_path / "static-run",
            ros_data=ros_data,
        )
    )
    runtime_report = build_report(
        make_analyzer(
            inputs=ActiveDiscoveryInputs(
                install_roots=[install],
                active_probe=ActiveProbeMode.RUNTIME_READONLY,
            ),
            projects=[],
            run_root=tmp_path / "runtime-run",
            ros_data=ros_data,
        )
    )

    assert static_report.coverage["ros_runtime"].status == "NOT_PROBED"
    assert static_report.executables[0].communication.ros["nodes"] == []
    assert runtime_report.coverage["ros_runtime"].status == "OBSERVED"
    assert runtime_report.executables[0].communication.ros["nodes"] == ["/driver"]
    assert runtime_report.executables[0].evidence["ros_runtime"] == ["live_ros_graph"]


def test_empty_source_root_is_rejected_instead_of_claiming_a_discovery_mode(
    tmp_path: Path,
) -> None:
    source = tmp_path / "empty-source"
    source.mkdir()
    projects = ApplicationProbe().run([source]).data["projects"]

    with pytest.raises(ValueError, match="no usable primary evidence was collected"):
        build_report(
            make_analyzer(
                inputs=ActiveDiscoveryInputs(source_roots=[source]),
                projects=projects,
                run_root=tmp_path / "run",
            )
        )


def test_documentation_without_an_executable_uses_degraded_doc_probe_mode(
    tmp_path: Path,
) -> None:
    source = tmp_path / "empty-source"
    docs = tmp_path / "docs"
    source.mkdir()
    docs.mkdir()
    (docs / "README.md").write_text("Run vendor-driver --help", encoding="utf-8")
    projects = ApplicationProbe().run([source]).data["projects"]

    report = build_report(
        make_analyzer(
            inputs=ActiveDiscoveryInputs(
                source_roots=[source],
                document_roots=[docs],
            ),
            projects=projects,
            run_root=tmp_path / "run",
        )
    )

    assert report.discovery_mode.level == DiscoveryModeLevel.DOC_PROBE
    assert report.discovery_mode.confidence.value == "LOW"
    assert report.executables == []


def test_non_executable_install_content_falls_back_to_documentation(
    tmp_path: Path,
) -> None:
    install = tmp_path / "install"
    docs = tmp_path / "docs"
    install.mkdir()
    docs.mkdir()
    (install / "metadata.json").write_text('{"name": "vendor-driver"}', encoding="utf-8")
    (docs / "README.md").write_text("Vendor driver package", encoding="utf-8")

    report = build_report(
        make_analyzer(
            inputs=ActiveDiscoveryInputs(
                install_roots=[install],
                document_roots=[docs],
            ),
            projects=[],
            run_root=tmp_path / "run",
        )
    )

    assert report.discovery_mode.level == DiscoveryModeLevel.DOC_PROBE
    assert report.coverage["artifacts"].records == 1
    assert report.executables == []


def test_discovery_cli_does_not_fall_back_to_current_directory() -> None:
    result = CliRunner().invoke(
        app,
        [
            "adapt",
            "discover",
            "run",
            "--robot",
            "demo_diff",
            "--urdf",
            str(Path("tests/fixtures/profiles/differential_drive.urdf").resolve()),
        ],
    )

    assert result.exit_code == 2
    assert "at least one --build-root" in result.output


def test_discovery_does_not_run_host_package_inventory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "pyproject.toml").write_text('[project]\nname = "demo"\n', encoding="utf-8")
    (source / "README.md").write_text("demo operator guide", encoding="utf-8")
    registry = RobotRegistry(Path("tests/fixtures/robots"))
    registry.load()

    def forbidden_ros_probe(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"ROS runtime probe was unexpectedly called: {args}, {kwargs}")

    monkeypatch.setattr(
        "rolo.stages.adapt.discovery.RosProbe.run",
        forbidden_ros_probe,
    )
    report, _ = DiscoveryService(ArtifactStore(tmp_path / "artifacts")).run(
        robot=registry.get("demo_diff"),
        urdf_path=Path("tests/fixtures/profiles/differential_drive.urdf"),
        active_inputs=ActiveDiscoveryInputs(
            source_roots=[source],
        ),
    )

    assert report.software_summary["status"] == "PARTIAL"
    assert report.software_summary["direct_dependency_count"] == 0
    assert report.software_summary["unknown_dependency_count"] == 1
    assert (tmp_path / "artifacts/discovery/demo_diff/latest.json").is_file()
    assert report.probes["ros"].status == "UNAVAILABLE"
    assert report.probes["ros"].warnings == ["ROS runtime inspection was not requested"]


def test_relevant_dependency_findings_flow_to_authoritative_reports(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    missing_name = "rolo-package-that-does-not-exist-7f3d4d"
    (source / "pyproject.toml").write_text(
        f"""[project]
name = "demo"
dependencies = ["{missing_name}>=1"]

[project.scripts]
demo = "demo:main"
""",
        encoding="utf-8",
    )
    (source / "README.md").write_text("demo dependency guide", encoding="utf-8")
    registry = RobotRegistry(Path("tests/fixtures/robots"))
    registry.load()
    artifact_root = tmp_path / "artifacts"

    report, _ = DiscoveryService(ArtifactStore(artifact_root)).run(
        robot=registry.get("demo_diff"),
        urdf_path=Path("tests/fixtures/profiles/differential_drive.urdf"),
        active_inputs=ActiveDiscoveryInputs(source_roots=[source]),
    )

    run_root = artifact_root / "discovery/demo_diff/runs" / report.discovery_id
    dependencies = json.loads((run_root / "direct_dependencies.json").read_text(encoding="utf-8"))
    active = json.loads((run_root / "active_discovery_report.json").read_text(encoding="utf-8"))
    assert dependencies["status"] == "SUCCEEDED"
    assert dependencies["counts_by_status"]["MISSING"] == 1
    assert dependencies["candidates"][0]["name"] == missing_name
    assert dependencies["candidates"][0]["status"] == "MISSING"
    missing_id = dependencies["candidates"][0]["candidate_id"]
    assert active["dependency_summary"]["missing"] == [missing_id]
    assert report.software_summary["missing_dependency_count"] == 1
    assert dependencies["candidates"][0]["required"] is True


def test_version_conflicts_flow_to_authoritative_reports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "pyproject.toml").write_text(
        """[project]
name = "demo"
dependencies = ["conflict-lib>=3"]

[project.scripts]
demo = "demo:main"
""",
        encoding="utf-8",
    )
    (source / "README.md").write_text("demo version guide", encoding="utf-8")

    class Distribution:
        metadata = {"Name": "conflict-lib"}
        version = "2.0"

        @staticmethod
        def locate_file(_: str) -> Path:
            return tmp_path / "site-packages"

    monkeypatch.setattr(
        "rolo.stages.adapt.software_relevance.importlib_metadata.distribution",
        lambda _: Distribution(),
    )
    registry = RobotRegistry(Path("tests/fixtures/robots"))
    registry.load()
    artifact_root = tmp_path / "artifacts"

    report, _ = DiscoveryService(ArtifactStore(artifact_root)).run(
        robot=registry.get("demo_diff"),
        urdf_path=Path("tests/fixtures/profiles/differential_drive.urdf"),
        active_inputs=ActiveDiscoveryInputs(source_roots=[source]),
    )

    run_root = artifact_root / "discovery/demo_diff/runs" / report.discovery_id
    dependencies = json.loads((run_root / "direct_dependencies.json").read_text(encoding="utf-8"))
    active = json.loads((run_root / "active_discovery_report.json").read_text(encoding="utf-8"))
    assert dependencies["counts_by_status"]["VERSION_CONFLICT"] == 1
    assert dependencies["candidates"][0]["status"] == "VERSION_CONFLICT"
    conflict_id = dependencies["candidates"][0]["candidate_id"]
    assert active["dependency_summary"]["conflicting"] == [conflict_id]
    assert report.software_summary["conflicting_dependency_count"] == 1
    assert dependencies["candidates"][0]["required"] is True
