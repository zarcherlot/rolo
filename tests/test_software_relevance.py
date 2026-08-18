from datetime import datetime, timezone
from pathlib import Path

import pytest

from rolo.core.models import DiscoveryStatus, ProbeResult
from rolo.stages.build.active_discovery import (
    ActiveDiscoveryAnalyzer,
    ActiveDiscoveryInputs,
)
from rolo.stages.build.software_relevance import (
    CandidateResolutionStatus,
    RelevantSoftwareResolver,
    SoftwareDiscoveryPolicy,
    enrich_active_report,
)

COLLECTED_AT = datetime(2026, 8, 18, tzinfo=timezone.utc)


def make_project(root: Path, declarations: list[dict[str, object]]) -> dict[str, object]:
    return {
        "root": str(root),
        "file_count_scanned": 1,
        "scan_truncated": False,
        "build_systems": ["python/pyproject"],
        "packages": ["demo-app"],
        "entrypoints": [
            {"name": "demo-app", "target": "demo.main:main", "source": "pyproject"}
        ],
        "launch_files": [],
        "readmes": [],
        "config_files": [],
        "semantic_candidates": [],
        "ros_names": {"topics": [], "services": [], "actions": []},
        "ros_interfaces": [],
        "protocols": [],
        "languages": ["python"],
        "build_targets": [],
        "declared_dependencies": sorted(
            {str(declaration["name"]) for declaration in declarations}
        ),
        "dependency_declarations": declarations,
        "manifest_digests": {"pyproject.toml": "0" * 64},
        "source_revision": None,
    }


def make_report(
    tmp_path: Path,
    *,
    projects: list[dict[str, object]],
    executables: list[Path] | None = None,
):
    inputs = ActiveDiscoveryInputs(
        source_roots=[tmp_path] if projects else [],
        executables=executables or [],
    )
    return ActiveDiscoveryAnalyzer(
        inputs=inputs,
        projects=projects,
        ros_probe=ProbeResult(
            layer="ros",
            status=DiscoveryStatus.UNAVAILABLE,
            data={"nodes": [], "topics": [], "services": [], "actions": []},
        ),
        tools=[],
        run_root=tmp_path / "run",
        artifact_prefix="artifact://discovery/demo/runs/disc-relevance",
    ).build(
        discovery_id="disc-relevance",
        robot_id="demo",
        technical_status="SUCCEEDED",
        created_at=COLLECTED_AT,
    )


class FakeDistribution:
    def __init__(self, name: str, version: str, root: Path) -> None:
        self.metadata = {"Name": name}
        self.version = version
        self.root = root

    def locate_file(self, value: str) -> Path:
        del value
        return self.root


def test_python_dependencies_resolve_installed_and_missing_without_pip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    declarations = [
        {
            "name": "installed-lib",
            "ecosystem": "python",
            "scope": "runtime",
            "required": True,
            "specifier": ">=1",
            "source": str(tmp_path / "pyproject.toml"),
        },
        {
            "name": "missing-lib",
            "ecosystem": "python",
            "scope": "runtime",
            "required": True,
            "specifier": None,
            "source": str(tmp_path / "pyproject.toml"),
        },
    ]
    project = make_project(tmp_path, declarations)
    report = make_report(tmp_path, projects=[project])

    def fake_distribution(name: str) -> FakeDistribution:
        if name == "installed-lib":
            return FakeDistribution("installed-lib", "2.0", tmp_path / "site-packages")
        from importlib.metadata import PackageNotFoundError

        raise PackageNotFoundError(name)

    monkeypatch.setattr(
        "rolo.stages.build.software_relevance.importlib_metadata.distribution",
        fake_distribution,
    )
    resolution = RelevantSoftwareResolver(
        SoftwareDiscoveryPolicy(), environment={}
    ).resolve(
        discovery_id="disc-relevance",
        projects=[project],
        active_report=report,
        collected_at=COLLECTED_AT,
        enabled=True,
    )
    enrich_active_report(report, resolution)

    by_name = {candidate.name: candidate for candidate in resolution.candidates}
    assert by_name["installed-lib"].status == CandidateResolutionStatus.INSTALLED
    assert by_name["installed-lib"].installed_version == "2.0"
    assert by_name["missing-lib"].status == CandidateResolutionStatus.MISSING
    assert resolution.status == "SUCCEEDED"
    assert [item["name"] for item in report.dependency_summary["missing"]] == [
        "missing-lib"
    ]
    assert report.executables[0].dependencies["missing"][0]["name"] == "missing-lib"


def test_python_version_conflict_is_reported_and_flows_to_build_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    declaration = {
        "name": "installed-lib",
        "ecosystem": "python",
        "scope": "runtime",
        "required": True,
        "specifier": ">=3,<4",
        "source": str(tmp_path / "pyproject.toml"),
    }
    project = make_project(tmp_path, [declaration])
    report = make_report(tmp_path, projects=[project])
    monkeypatch.setattr(
        "rolo.stages.build.software_relevance.importlib_metadata.distribution",
        lambda _: FakeDistribution("installed-lib", "2.0", tmp_path / "site-packages"),
    )

    resolution = RelevantSoftwareResolver(
        SoftwareDiscoveryPolicy(), environment={}
    ).resolve(
        discovery_id="disc-relevance",
        projects=[project],
        active_report=report,
        collected_at=COLLECTED_AT,
        enabled=True,
    )
    enrich_active_report(report, resolution)

    candidate = resolution.candidates[0]
    assert candidate.status == CandidateResolutionStatus.VERSION_CONFLICT
    assert candidate.installed_version == "2.0"
    assert resolution.conflict_count == 1
    assert resolution.installed_count == 0
    assert report.dependency_summary["conflicting"][0]["name"] == "installed-lib"
    assert report.executables[0].dependencies["version_conflicts"][0]["name"] == (
        "installed-lib"
    )
    assert report.global_conflicts == [
        "dependency version conflict: python:installed-lib: installed version '2.0' "
        "does not satisfy constraint '>=3,<4'"
    ]


def test_ros_dependencies_use_static_ament_index_and_distinguish_missing(
    tmp_path: Path,
) -> None:
    prefix = tmp_path / "install"
    resource = prefix / "share/ament_index/resource_index/packages/demo_msgs"
    manifest = prefix / "share/demo_msgs/package.xml"
    resource.parent.mkdir(parents=True)
    manifest.parent.mkdir(parents=True)
    resource.write_text("", encoding="utf-8")
    manifest.write_text(
        "<package><name>demo_msgs</name><version>1.2.3</version></package>",
        encoding="utf-8",
    )
    declarations = [
        {
            "name": "demo_msgs",
            "ecosystem": "ros",
            "scope": "exec_depend",
            "required": True,
            "specifier": None,
            "source": str(tmp_path / "package.xml"),
        },
        {
            "name": "missing_msgs",
            "ecosystem": "ros",
            "scope": "exec_depend",
            "required": True,
            "specifier": None,
            "source": str(tmp_path / "package.xml"),
        },
    ]
    project = make_project(tmp_path, declarations)
    report = make_report(tmp_path, projects=[project])

    resolution = RelevantSoftwareResolver(
        SoftwareDiscoveryPolicy(),
        environment={"AMENT_PREFIX_PATH": str(prefix)},
    ).resolve(
        discovery_id="disc-relevance",
        projects=[project],
        active_report=report,
        collected_at=COLLECTED_AT,
        enabled=True,
    )

    by_name = {candidate.name: candidate for candidate in resolution.candidates}
    assert by_name["demo_msgs"].status == CandidateResolutionStatus.INSTALLED
    assert by_name["demo_msgs"].installed_version == "1.2.3"
    assert by_name["missing_msgs"].status == CandidateResolutionStatus.MISSING
    assert resolution.status == "SUCCEEDED"


def test_ros_dependency_version_constraint_is_compared_from_static_manifest(
    tmp_path: Path,
) -> None:
    prefix = tmp_path / "install"
    resource = prefix / "share/ament_index/resource_index/packages/demo_msgs"
    manifest = prefix / "share/demo_msgs/package.xml"
    resource.parent.mkdir(parents=True)
    manifest.parent.mkdir(parents=True)
    resource.write_text("", encoding="utf-8")
    manifest.write_text(
        "<package><name>demo_msgs</name><version>1.2.3</version></package>",
        encoding="utf-8",
    )
    declaration = {
        "name": "demo_msgs",
        "ecosystem": "ros",
        "scope": "exec_depend",
        "required": True,
        "specifier": ">=2",
        "source": str(tmp_path / "package.xml"),
    }
    project = make_project(tmp_path, [declaration])
    report = make_report(tmp_path, projects=[project])

    resolution = RelevantSoftwareResolver(
        SoftwareDiscoveryPolicy(),
        environment={"AMENT_PREFIX_PATH": str(prefix)},
    ).resolve(
        discovery_id="disc-relevance",
        projects=[project],
        active_report=report,
        collected_at=COLLECTED_AT,
        enabled=True,
    )

    assert resolution.candidates[0].status == "VERSION_CONFLICT"
    assert resolution.conflict_count == 1


def test_inapplicable_python_marker_is_not_queried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    declaration = {
        "name": "platform-only-lib",
        "ecosystem": "python",
        "scope": "runtime",
        "required": True,
        "specifier": ">=1",
        "marker": "sys_platform == 'never'",
        "applicable": False,
        "source": str(tmp_path / "pyproject.toml"),
    }
    project = make_project(tmp_path, [declaration])
    report = make_report(tmp_path, projects=[project])

    def forbidden_distribution(_: str) -> None:
        raise AssertionError("an inapplicable dependency must not be queried")

    monkeypatch.setattr(
        "rolo.stages.build.software_relevance.importlib_metadata.distribution",
        forbidden_distribution,
    )

    resolution = RelevantSoftwareResolver(
        SoftwareDiscoveryPolicy(), environment={}
    ).resolve(
        discovery_id="disc-relevance",
        projects=[project],
        active_report=report,
        collected_at=COLLECTED_AT,
        enabled=True,
    )

    assert resolution.candidates == []
    assert resolution.status == "SUCCEEDED"


def test_python_dependency_name_variants_merge_to_one_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    declarations = [
        {
            "name": name,
            "ecosystem": "python",
            "scope": "runtime",
            "required": True,
            "specifier": specifier,
            "source": str(tmp_path / "pyproject.toml"),
        }
        for name, specifier in (("Demo.Lib", ">=1"), ("demo-lib", "<3"))
    ]
    project = make_project(tmp_path, declarations)
    report = make_report(tmp_path, projects=[project])
    monkeypatch.setattr(
        "rolo.stages.build.software_relevance.importlib_metadata.distribution",
        lambda _: FakeDistribution("demo-lib", "2.0", tmp_path / "site-packages"),
    )

    resolution = RelevantSoftwareResolver(
        SoftwareDiscoveryPolicy(), environment={}
    ).resolve(
        discovery_id="disc-relevance",
        projects=[project],
        active_report=report,
        collected_at=COLLECTED_AT,
        enabled=True,
    )

    assert len(resolution.candidates) == 1
    assert resolution.candidates[0].specifiers == ["<3", ">=1"]
    assert resolution.candidates[0].status == "INSTALLED"


def test_missing_ament_index_is_unknown_not_missing(tmp_path: Path) -> None:
    declarations = [
        {
            "name": "demo_msgs",
            "ecosystem": "ros",
            "scope": "exec_depend",
            "required": True,
            "specifier": None,
            "source": str(tmp_path / "package.xml"),
        }
    ]
    project = make_project(tmp_path, declarations)
    report = make_report(tmp_path, projects=[project])

    resolution = RelevantSoftwareResolver(
        SoftwareDiscoveryPolicy(), environment={}
    ).resolve(
        discovery_id="disc-relevance",
        projects=[project],
        active_report=report,
        collected_at=COLLECTED_AT,
        enabled=True,
    )

    candidate = resolution.candidates[0]
    assert candidate.status == CandidateResolutionStatus.UNKNOWN
    assert resolution.status == "PARTIAL"


def test_binary_without_dependency_declarations_remains_explicitly_unknown(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "vendor-driver"
    executable.write_bytes(b"\x7fELF" + b"\0" * 60)
    report = make_report(tmp_path, projects=[], executables=[executable])

    resolution = RelevantSoftwareResolver(environment={}).resolve(
        discovery_id="disc-relevance",
        projects=[],
        active_report=report,
        collected_at=COLLECTED_AT,
    )
    enrich_active_report(report, resolution)

    assert resolution.status == "PARTIAL"
    assert resolution.candidates == []
    assert resolution.unresolved_executables == [report.executables[0].executable_id]
    assert "dependency declarations unavailable" in report.unknowns[-1]


def test_disabled_relevance_records_policy_block_without_queries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    declarations = [
        {
            "name": "demo-lib",
            "ecosystem": "python",
            "scope": "runtime",
            "required": True,
            "specifier": None,
            "source": str(tmp_path / "pyproject.toml"),
        }
    ]
    project = make_project(tmp_path, declarations)
    report = make_report(tmp_path, projects=[project])

    def forbidden_distribution(_: str) -> None:
        raise AssertionError("metadata query must not run")

    monkeypatch.setattr(
        "rolo.stages.build.software_relevance.importlib_metadata.distribution",
        forbidden_distribution,
    )

    resolution = RelevantSoftwareResolver(
        SoftwareDiscoveryPolicy(), environment={}
    ).resolve(
        discovery_id="disc-relevance",
        projects=[project],
        active_report=report,
        collected_at=COLLECTED_AT,
        enabled=False,
    )

    assert resolution.status == "BLOCKED_BY_POLICY"
    assert resolution.candidates[0].status == "BLOCKED_BY_POLICY"


def test_relevance_candidate_limit_is_explicitly_partial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    declarations = [
        {
            "name": name,
            "ecosystem": "python",
            "scope": "runtime",
            "required": True,
            "specifier": None,
            "source": str(tmp_path / "pyproject.toml"),
        }
        for name in ("first-lib", "second-lib")
    ]
    project = make_project(tmp_path, declarations)
    report = make_report(tmp_path, projects=[project])
    from importlib.metadata import PackageNotFoundError

    def missing_distribution(name: str) -> None:
        raise PackageNotFoundError(name)

    monkeypatch.setattr(
        "rolo.stages.build.software_relevance.importlib_metadata.distribution",
        missing_distribution,
    )

    resolution = RelevantSoftwareResolver(
        SoftwareDiscoveryPolicy(max_candidates=1), environment={}
    ).resolve(
        discovery_id="disc-relevance",
        projects=[project],
        active_report=report,
        collected_at=COLLECTED_AT,
        enabled=True,
    )

    assert resolution.status == "PARTIAL"
    assert resolution.candidate_count == 1
    assert resolution.omitted_candidate_count == 1
    assert "exceeded the configured limit" in resolution.warnings[0]
