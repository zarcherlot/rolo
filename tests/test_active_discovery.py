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
from rolo.core.models import DiscoveryStatus, ProbeResult, ToolDescriptor
from rolo.core.registry import RobotRegistry
from rolo.stages.build.active_discovery import (
    ActiveDiscoveryAnalyzer,
    ActiveDiscoveryInputs,
    ActiveProbeMode,
    ConfirmationDecision,
    DiscoveryModeLevel,
    HelpProbeResult,
    HelpProbeStatus,
    confirmation_matches_report,
    run_bounded_help,
    write_confirmation,
)
from rolo.stages.build.discovery import ApplicationProbe, DiscoveryService

CREATED_AT = datetime(2026, 8, 18, tzinfo=timezone.utc)


def make_tool() -> ToolDescriptor:
    return ToolDescriptor(
        operation="app.test.inspect",
        canonical_cli=["robotctl", "app", "test", "inspect"],
        layer="application",
        description="Inspect the discovered application",
        availability="DISCOVERED_UNVERIFIED",
        adapter="unbound",
        evidence=["static discovery"],
    )


def make_analyzer(
    *,
    inputs: ActiveDiscoveryInputs,
    projects: list[dict[str, object]],
    run_root: Path,
    ros_data: dict[str, object] | None = None,
) -> ActiveDiscoveryAnalyzer:
    return ActiveDiscoveryAnalyzer(
        inputs=inputs,
        projects=projects,
        ros_probe=ProbeResult(
            layer="ros",
            status=DiscoveryStatus.SUCCEEDED,
            data=ros_data or {"nodes": [], "topics": [], "services": [], "actions": []},
        ),
        tools=[make_tool()],
        run_root=run_root,
        artifact_prefix="artifact://discovery/demo/runs/disc-test",
    )


def build_report(analyzer: ActiveDiscoveryAnalyzer):
    return analyzer.build(
        discovery_id="disc-test",
        robot_id="demo",
        technical_status="SUCCEEDED",
        created_at=CREATED_AT,
    )


def test_primary_evidence_input_is_required() -> None:
    with pytest.raises(ValidationError, match="at least one --source-root"):
        ActiveDiscoveryInputs(document_roots=[Path("docs")])


def test_source_first_report_contains_source_protocol_and_ros_evidence(
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
    projects = ApplicationProbe().run([source]).data["projects"]

    report = build_report(
        make_analyzer(
            inputs=ActiveDiscoveryInputs(source_roots=[source]),
            projects=projects,
            run_root=tmp_path / "run",
        )
    )

    assert report.discovery_mode.level == DiscoveryModeLevel.SOURCE_FIRST
    executable = report.executables[0]
    assert executable.name == "demo-app"
    assert executable.origin == "SOURCE_DECLARED"
    assert executable.source_analysis.languages == ["python"]
    assert executable.source_analysis.declared_dependencies == ["paho-mqtt", "rclpy"]
    assert executable.communication.network["protocols"] == ["mqtt"]
    assert executable.communication.ros["publishers"][0]["name"] == "/cmd_vel"


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
     remappings=[("/cmd", "/robot/cmd")])
""",
        encoding="utf-8",
    )

    def forbidden_popen(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"launch or executable was unexpectedly run: {args}, {kwargs}")

    monkeypatch.setattr("rolo.stages.build.active_discovery.subprocess.Popen", forbidden_popen)
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
    assert executable.communication.ros["remappings"] == [
        {"from": "/cmd", "to": "/robot/cmd"}
    ]
    assert executable.communication.network["protocols"] == ["tcp"]


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

    monkeypatch.setattr("rolo.stages.build.active_discovery.run_bounded_help", fake_help)
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
    monkeypatch.setattr("rolo.stages.build.active_discovery.MAX_HELP_BYTES", 32)
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
        "rolo.stages.build.active_discovery.subprocess.Popen",
        lambda *args, **kwargs: FakeProcess(),
    )
    monkeypatch.setattr("rolo.stages.build.active_discovery.HELP_TIMEOUT_S", 0.01)

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

    monkeypatch.setattr("rolo.stages.build.active_discovery.MAX_HELP_PROBES", 1)
    monkeypatch.setattr("rolo.stages.build.active_discovery.run_bounded_help", fake_help)
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


def test_empty_source_root_degrades_instead_of_claiming_high_confidence(
    tmp_path: Path,
) -> None:
    source = tmp_path / "empty-source"
    source.mkdir()
    projects = ApplicationProbe().run([source]).data["projects"]

    report = build_report(
        make_analyzer(
            inputs=ActiveDiscoveryInputs(source_roots=[source]),
            projects=projects,
            run_root=tmp_path / "run",
        )
    )

    assert report.discovery_mode.level == DiscoveryModeLevel.BINARY_ONLY
    assert report.coverage["source"].status == "PARTIAL"
    assert "source roots contained no usable source" in " ".join(report.warnings)


def test_confirmation_is_bound_to_exact_report_hash_and_identity(tmp_path: Path) -> None:
    executable = tmp_path / "driver.exe"
    executable.write_bytes(b"MZ" + b"\0" * 62)
    report = build_report(
        make_analyzer(
            inputs=ActiveDiscoveryInputs(executables=[executable]),
            projects=[],
            run_root=tmp_path / "run",
        )
    )
    report_path = tmp_path / "active_discovery_report.json"
    report_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")

    confirmation = write_confirmation(
        report_path=report_path,
        robot_id="demo",
        discovery_id="disc-test",
        decision=ConfirmationDecision.ACCEPT,
        corrections=None,
    )

    assert confirmation_matches_report(confirmation, report_path) is True
    document = json.loads(report_path.read_text(encoding="utf-8"))
    document["warnings"].append("changed after confirmation")
    report_path.write_text(json.dumps(document), encoding="utf-8")
    assert confirmation_matches_report(confirmation, report_path) is False


def test_discovery_cli_does_not_fall_back_to_current_directory() -> None:
    result = CliRunner().invoke(
        app,
        [
            "build",
            "discover",
            "run",
            "--robot",
            "demo_diff",
            "--urdf",
            str(Path("configs/profiles/differential_drive.urdf").resolve()),
        ],
    )

    assert result.exit_code == 2
    assert "at least one --source-root" in result.output


def test_discovery_does_not_run_host_package_inventory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "pyproject.toml").write_text(
        '[project]\nname = "demo"\n', encoding="utf-8"
    )
    registry = RobotRegistry(Path("configs/local/robots"))
    registry.load()

    def forbidden_ros_probe(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"ROS runtime probe was unexpectedly called: {args}, {kwargs}")

    monkeypatch.setattr(
        "rolo.stages.build.discovery.RosProbe.run",
        forbidden_ros_probe,
    )
    report, _ = DiscoveryService(ArtifactStore(tmp_path / "artifacts")).run(
        robot=registry.get("demo_diff"),
        urdf_path=Path("configs/profiles/differential_drive.urdf"),
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


def test_relevant_dependency_findings_flow_to_reports_and_build_inputs(
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
    registry = RobotRegistry(Path("configs/local/robots"))
    registry.load()
    artifact_root = tmp_path / "artifacts"

    report, _ = DiscoveryService(ArtifactStore(artifact_root)).run(
        robot=registry.get("demo_diff"),
        urdf_path=Path("configs/profiles/differential_drive.urdf"),
        active_inputs=ActiveDiscoveryInputs(source_roots=[source]),
    )

    run_root = artifact_root / "discovery/demo_diff/runs" / report.discovery_id
    dependencies = json.loads(
        (run_root / "direct_dependencies.json").read_text(encoding="utf-8")
    )
    active = json.loads(
        (run_root / "active_discovery_report.json").read_text(encoding="utf-8")
    )
    build_inputs = json.loads(
        (artifact_root / "build/demo_diff/latest/inputs.json").read_text(encoding="utf-8")
    )

    assert dependencies["status"] == "SUCCEEDED"
    assert dependencies["counts_by_status"]["MISSING"] == 1
    assert dependencies["candidates"][0]["name"] == missing_name
    assert dependencies["candidates"][0]["status"] == "MISSING"
    missing_id = dependencies["candidates"][0]["candidate_id"]
    assert active["dependency_summary"]["missing"] == [missing_id]
    assert report.software_summary["missing_dependency_count"] == 1
    assert any(
        item == f"dependency:python:{missing_name}:MISSING"
        for item in build_inputs["unresolved_dependencies"]
    )


def test_version_conflicts_flow_to_summary_report_and_build_inputs(
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

    class Distribution:
        metadata = {"Name": "conflict-lib"}
        version = "2.0"

        @staticmethod
        def locate_file(_: str) -> Path:
            return tmp_path / "site-packages"

    monkeypatch.setattr(
        "rolo.stages.build.software_relevance.importlib_metadata.distribution",
        lambda _: Distribution(),
    )
    registry = RobotRegistry(Path("configs/local/robots"))
    registry.load()
    artifact_root = tmp_path / "artifacts"

    report, _ = DiscoveryService(ArtifactStore(artifact_root)).run(
        robot=registry.get("demo_diff"),
        urdf_path=Path("configs/profiles/differential_drive.urdf"),
        active_inputs=ActiveDiscoveryInputs(source_roots=[source]),
    )

    run_root = artifact_root / "discovery/demo_diff/runs" / report.discovery_id
    dependencies = json.loads(
        (run_root / "direct_dependencies.json").read_text(encoding="utf-8")
    )
    active = json.loads(
        (run_root / "active_discovery_report.json").read_text(encoding="utf-8")
    )
    build_inputs = json.loads(
        (artifact_root / "build/demo_diff/latest/inputs.json").read_text(encoding="utf-8")
    )

    assert dependencies["counts_by_status"]["VERSION_CONFLICT"] == 1
    assert dependencies["candidates"][0]["status"] == "VERSION_CONFLICT"
    conflict_id = dependencies["candidates"][0]["candidate_id"]
    assert active["dependency_summary"]["conflicting"] == [conflict_id]
    assert report.software_summary["conflicting_dependency_count"] == 1
    assert "dependency:python:conflict-lib:VERSION_CONFLICT" in build_inputs[
        "unresolved_dependencies"
    ]
