from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from rolo.adapter_runtime import StaleAdapterReleaseError
from rolo.agent_tool import adapt_app
from rolo.agent_tool import app as agent_tool_app
from rolo.cli import app
from rolo.core.artifacts import ArtifactStore
from rolo.core.config import get_settings
from rolo.core.registry import RobotRegistry
from rolo.stages.adapt.discovery import DiscoveryService
from rolo.stages.adapt.workset import (
    build_operation_workset,
    candidate_detail,
    evidence_snippet,
    resolve_evidence_path,
    wiki_search,
    wiki_section,
)


def _discover(artifact_root: Path, source_root: Path) -> str:
    (source_root / "src/demo_nav").mkdir(parents=True)
    (source_root / "pyproject.toml").write_text(
        '[project]\nname = "adapt-tools-demo"\n\n'
        '[project.scripts]\ndemo-nav = "demo_nav.main:main"\n',
        encoding="utf-8",
    )
    source = source_root / "src/demo_nav/main.py"
    source.write_text('node.create_publisher(Twist, "/cmd_vel", 10)\n', encoding="utf-8")
    registry = RobotRegistry(Path("tests/fixtures/robots"))
    registry.load()
    report, _ = DiscoveryService(ArtifactStore(artifact_root)).run(
        robot=registry.get("demo_diff"),
        urdf_path=Path("tests/fixtures/profiles/differential_drive.urdf"),
        source_roots=[source_root],
    )
    return report.discovery_id


def test_workset_joins_registry_candidates_and_registration(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    source_root = tmp_path / "source"
    discovery_id = _discover(artifact_root, source_root)

    workset = build_operation_workset(artifact_root, tmp_path / "output", "demo_diff", discovery_id)
    velocity = next(item for item in workset.operations if item.operation == "app.teleop.velocity")

    assert workset.registry_operation_count == 294
    assert workset.candidate_operation_count >= 1
    assert velocity.applicability == "OBSERVED"
    assert velocity.implementation == "UNBOUND"
    assert velocity.registration == "NOT_REGISTERED"


def test_workset_surfaces_a_corrupt_current_release(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    source_root = tmp_path / "source"
    discovery_id = _discover(artifact_root, source_root)
    output_root = tmp_path / "output"
    current = output_root / "robots/demo_diff/current.json"
    current.parent.mkdir(parents=True)
    current.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError):
        build_operation_workset(artifact_root, output_root, "demo_diff", discovery_id)


def test_workset_reports_hash_valid_stale_registration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact_root = tmp_path / "artifacts"
    source_root = tmp_path / "source"
    discovery_id = _discover(artifact_root, source_root)
    operation = "app.teleop.velocity"
    release = SimpleNamespace(
        release_id="release-old",
        discovery_id=discovery_id,
        target_fingerprint_sha256="0" * 64,
    )
    bundle = SimpleNamespace(operations=[SimpleNamespace(operation=operation)])
    catalog = SimpleNamespace(
        tools=[SimpleNamespace(operation=operation, availability="VERIFIED")]
    )

    def stale_release(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise StaleAdapterReleaseError(
            "stale fixture",
            release_root=tmp_path / "output/release-old",
            release=release,
            bundle=bundle,
            catalog=catalog,
        )

    monkeypatch.setattr("rolo.stages.adapt.workset.load_current_release", stale_release)

    workset = build_operation_workset(
        artifact_root, tmp_path / "output", "demo_diff", discovery_id
    )
    velocity = next(item for item in workset.operations if item.operation == operation)

    assert workset.release_id == "release-old"
    assert velocity.registration == "STALE"
    assert velocity.implementation == "UNBOUND"


def test_candidate_and_bounded_evidence_queries_are_focused(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    source_root = tmp_path / "source"
    discovery_id = _discover(artifact_root, source_root)

    candidate = candidate_detail(artifact_root, "demo_diff", "app.teleop.velocity", discovery_id)
    snippet = evidence_snippet(
        artifact_root,
        "demo_diff",
        str(source_root / "src/demo_nav/main.py"),
        discovery_id=discovery_id,
    )

    assert candidate["operation"] == "app.teleop.velocity"
    assert candidate["related_executables"]
    assert "/cmd_vel" in snippet["content"]


def test_wiki_can_be_searched_and_read_by_section(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    source_root = tmp_path / "source"
    discovery_id = _discover(artifact_root, source_root)

    search = wiki_search(artifact_root, "demo_diff", "URDF", discovery_id)
    section = wiki_section(artifact_root, "demo_diff", "URDF 结构与语义", discovery_id)

    assert search["matches"]
    assert "URDF 结构与语义" in section["heading"]
    assert "Links" in section["content"]


def test_missing_discovery_root_does_not_authorize_its_parent(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    source_root = tmp_path / "source"
    discovery_id = _discover(artifact_root, source_root)
    source_root.rename(tmp_path / "source-moved")
    sibling = tmp_path / "sibling.txt"
    sibling.write_text("outside discovery scope", encoding="utf-8")

    with pytest.raises(ValueError, match="outside the discovery input roots"):
        resolve_evidence_path(
            artifact_root,
            "demo_diff",
            str(sibling),
            discovery_id,
        )


def test_adapt_operation_cli_uses_compact_workset(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    artifact_root = tmp_path / "artifacts"
    source_root = tmp_path / "source"
    discovery_id = _discover(artifact_root, source_root)
    monkeypatch.setenv("ROLO_ARTIFACT_DIR", str(artifact_root))
    monkeypatch.setenv("ROLO_OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setenv("ROLO_AGENT_DISCOVERY_ID", discovery_id)
    get_settings.cache_clear()

    result = CliRunner().invoke(app, ["adapt", "operations", "summary", "--robot", "demo_diff"])

    assert result.exit_code == 0, result.output
    assert '"registry_operation_count": 294' in result.output
    assert '"operations"' not in result.output


def test_agent_tool_exposes_queries_but_not_discovery_run_or_runtime_invoke() -> None:
    runner = CliRunner()

    root_help = runner.invoke(agent_tool_app, ["--help"])
    adapt_help = runner.invoke(agent_tool_app, ["adapt", "--help"])

    assert root_help.exit_code == 0
    assert adapt_help.exit_code == 0
    assert {group.name for group in agent_tool_app.registered_groups} == {"adapt"}
    assert {group.name for group in adapt_app.registered_groups} == {
        "operations",
        "candidates",
        "executable",
        "launch",
        "dependency",
        "evidence",
        "wiki",
    }
