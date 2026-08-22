import json
import subprocess
from hashlib import sha256
from pathlib import Path

import pytest

from rolo.stages.adapt.wiki_agent import (
    MAX_AGENT_CONTEXT_CHARS,
    MAX_AGENT_EVIDENCE_REFS,
    CodexWikiInsightProvider,
    _bounded_context,
    _bounded_evidence_reference_allowlist,
    _selected_context,
)
from tests.test_wiki import _review_inputs


def test_codex_wiki_insight_provider_is_read_only_and_normalizes_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    skill = tmp_path / "SKILL.md"
    skill.write_text(
        "---\nname: fixture\ndescription: fixture\n---\nReturn bounded JSON.",
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        captured["input"] = kwargs["input"]
        captured["environment"] = kwargs["env"]
        prompt = str(kwargs["input"])
        context = prompt.split("UNTRUSTED DISCOVERY EVIDENCE:\n", 1)[1]
        context_sha256 = sha256(context.encode("utf-8")).hexdigest()
        output = Path(command[command.index("--output-last-message") + 1])
        output.write_text(
            json.dumps(
                {
                    "robot_id": "demo",
                    "discovery_id": "disc-test",
                    "provenance": {
                        "skill_name": "rolo-wiki-authoring",
                        "skill_version": "1.0.0",
                        "model_id": "fixture-model",
                        "input_artifact_sha256": {
                            "discovery-context": context_sha256
                        },
                    },
                    "findings": [
                        {
                            "category": "MAINTENANCE",
                            "statement": "可能需要核对部署版本。",
                            "confidence": "LOW",
                            "basis": ["active_discovery.executables"],
                            "verification": "只读核对部署清单。",
                            "author_skill_version": "1.0.0",
                        }
                    ],
                    "unknown_assessments": [
                        {
                            "unknown": "dependency declarations unavailable: exe-hook",
                            "classification": "COLLECTED_EVIDENCE_REVIEW",
                            "assessment": "现有构建清单可能包含依赖声明。",
                            "confidence": "LOW",
                            "basis": ["active_discovery.unknowns[0]"],
                            "next_step": "只读检查构建清单。",
                            "author_skill_version": "1.0.0"
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("rolo.stages.adapt.wiki_agent.shutil.which", lambda _: "codex")
    monkeypatch.setattr("rolo.stages.adapt.wiki_agent.subprocess.run", fake_run)
    report, active = _review_inputs()
    provider = CodexWikiInsightProvider(
        skill_path=skill,
        executable="codex",
        api_key="fixture-secret",
    )

    bundle = provider.infer(report, active)

    command = captured["command"]
    assert isinstance(command, list)
    assert "--skip-git-repo-check" in command
    assert command[command.index("--sandbox") + 1] == "read-only"
    assert "workspace-write" not in command
    assert "fixture-secret" not in " ".join(command)
    assert bundle.findings[0].source == "ADAPT_AGENT_SKILL"
    assert bundle.findings[0].author_skill_version == "1.0.0"
    assert bundle.unknown_assessments[0].source == "ADAPT_AGENT_SKILL"
    assert bundle.unknown_assessments[0].author_skill_version == "1.0.0"
    assert bundle.provenance.skill_version == "1.0.0"
    assert "TRUSTED OUTPUT BINDINGS" in str(captured["input"])
    assert "allowed_evidence_refs" in str(captured["input"])
    assert "allowed_unknown_assessments" in str(captured["input"])
    assert "UNTRUSTED DISCOVERY EVIDENCE" in str(captured["input"])
    environment = captured["environment"]
    assert isinstance(environment, dict)
    assert environment["CODEX_API_KEY"] == "fixture-secret"


def test_wiki_evidence_allowlist_is_bounded_and_prefers_addressable_parents() -> None:
    context = {
        "active_discovery": {
            "unknowns": [f"unknown-{index}" for index in range(1_000)],
        },
        "operation_candidates": [{"operation": "app.camera.snapshot"}],
    }

    refs = _bounded_evidence_reference_allowlist(context)

    assert len(refs) == MAX_AGENT_EVIDENCE_REFS
    assert "active_discovery.unknowns" in refs
    assert "operation_candidates[0].operation" in refs


def test_wiki_insight_context_uses_a_serialized_character_budget() -> None:
    context = {
        "robot_id": "demo",
        "discovery_id": "disc-large",
        "executables": [{"name": f"exe-{index}", "evidence": "x" * 20_000} for index in range(100)],
    }

    bounded = _bounded_context(context)
    encoded = json.dumps(bounded, ensure_ascii=False, separators=(",", ":"))

    assert len(encoded) <= MAX_AGENT_CONTEXT_CHARS
    assert bounded["context_budget"]["truncated"] is True
    assert bounded["context_budget"]["original_chars"] > MAX_AGENT_CONTEXT_CHARS


def test_wiki_insight_context_preserves_unknowns_while_trimming_executables() -> None:
    unknown = "geometry.drive_model unavailable"
    context = {
        "robot_id": "demo",
        "discovery_id": "disc-large",
        "status": "PARTIAL",
        "active_discovery": {
            "unknowns": [unknown],
            "warnings": [],
            "executables": [
                {"name": f"exe-{index}", "evidence": "x" * 10_000}
                for index in range(100)
            ],
        },
    }

    bounded = _bounded_context(context)

    assert bounded["active_discovery"]["unknowns"] == [unknown]
    assert len(json.dumps(bounded, ensure_ascii=False, separators=(",", ":"))) <= (
        MAX_AGENT_CONTEXT_CHARS
    )


def test_selected_context_prioritizes_candidate_and_unknown_executables() -> None:
    report, active = _review_inputs()

    selected = _selected_context(report, active)
    executable_ids = {
        item["executable_id"] for item in selected["active_discovery"]["executables"]
    }

    assert "exe-hook" in executable_ids
    assert "exe-voice" in executable_ids
    assert selected["active_discovery"]["required_context_executable_count"] == 2
    assert selected["active_discovery"]["unknowns"] == active.unknowns
