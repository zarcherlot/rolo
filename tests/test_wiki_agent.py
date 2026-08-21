import json
import subprocess
from pathlib import Path

import pytest

from rolo.stages.adapt.wiki_agent import (
    MAX_AGENT_CONTEXT_CHARS,
    CodexWikiInsightProvider,
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
        output = Path(command[command.index("--output-last-message") + 1])
        output.write_text(
            json.dumps(
                {
                    "robot_id": "demo",
                    "discovery_id": "disc-test",
                    "findings": [
                        {
                            "category": "MAINTENANCE",
                            "statement": "可能需要核对部署版本。",
                            "confidence": "LOW",
                            "basis": ["active_discovery.executables"],
                            "verification": "只读核对部署清单。",
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
    assert command[command.index("--sandbox") + 1] == "read-only"
    assert "workspace-write" not in command
    assert "fixture-secret" not in " ".join(command)
    assert bundle.findings[0].source == "ADAPT_AGENT_SKILL"
    assert "UNTRUSTED DISCOVERY EVIDENCE" in str(captured["input"])
    environment = captured["environment"]
    assert isinstance(environment, dict)
    assert environment["CODEX_API_KEY"] == "fixture-secret"


def test_wiki_agent_context_compacts_large_executable_reports() -> None:
    report, active = _review_inputs()
    template = active.executables[-1]
    expanded = active.model_copy(
        update={
            "executables": [
                template.model_copy(
                    update={"executable_id": f"exe-{index}", "name": f"driver-{index}"}
                )
                for index in range(200)
            ]
        }
    )

    context = _selected_context(report, expanded)
    encoded = json.dumps(context, ensure_ascii=False, indent=2)

    assert len(encoded) < MAX_AGENT_CONTEXT_CHARS
    assert context["active_discovery"]["reported_executable_count"] == 200
    assert context["active_discovery"]["context_executable_count"] == 40
