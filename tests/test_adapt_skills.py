from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from rolo.stages.adapt.agent_contracts import (
    AgentArtifactProvenance,
    AgentBudgetUsage,
    AgentStopReason,
)
from rolo.stages.adapt.skill_contracts import (
    AdaptDiscoveryPlan,
    DiscoveryPlanAction,
    DiscoveryRemainingBudget,
)
from rolo.stages.adapt.wiki_insights import RoloWikiInsightBundle, WikiInsightBundle

ROOT = Path(__file__).resolve().parents[1]
SKILLS = (
    "rolo-adapt-discovery",
    "rolo-operation-mapping",
    "rolo-wiki-authoring",
)
SHA = "a" * 64


def _frontmatter(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    _empty, raw, _body = text.split("---", 2)
    value = yaml.safe_load(raw)
    assert isinstance(value, dict)
    return value


@pytest.mark.parametrize("skill_name", SKILLS)
def test_rolo_skill_is_independently_loadable_and_references_its_contract(
    skill_name: str,
) -> None:
    skill = ROOT / "skills" / skill_name / "SKILL.md"
    reference = skill.parent / "references" / "output-schema.md"

    metadata = _frontmatter(skill)

    assert metadata["name"] == skill_name
    assert isinstance(metadata["description"], str)
    assert len(metadata["description"]) >= 40
    assert reference.is_file()
    body = skill.read_text(encoding="utf-8")
    assert "references/output-schema.md" in body
    assert "provenance" in body.casefold()
    assert "placeholder" in body.casefold()
    assert "fallback" in body.casefold()


def test_legacy_wiki_skill_is_an_explicit_read_only_fallback() -> None:
    legacy = (ROOT / "skills" / "robot-wiki-heuristics" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    assert "Deprecated" in legacy
    assert "rolo-wiki-authoring" in legacy
    assert "read-only" in legacy


def _discovery_plan(**updates: object) -> AdaptDiscoveryPlan:
    values: dict[str, object] = {
        "robot_id": "demo",
        "discovery_id": "disc-1",
        "target_fingerprint_sha256": SHA,
        "actions": [
            DiscoveryPlanAction(
                action_id="inspect-ros-graph",
                kind="PROBE",
                definition_id="ros.graph.read",
                parameters={"domain_id": 7},
                expected_evidence_types=["ros.graph"],
                rationale="Resolve the missing online graph observation.",
            )
        ],
        "unknowns": ["Online ROS graph has not been observed."],
        "stop_conditions": ["Stop after one successful graph observation."],
        "remaining_budget": DiscoveryRemainingBudget(
            rounds=1,
            elapsed_ms=5_000,
            result_bytes=50_000,
            failures=1,
        ),
        "budget_usage": AgentBudgetUsage(
            rounds=1,
            input_tokens=500,
            output_tokens=100,
            elapsed_ms=200,
            result_bytes=1_000,
            stop_reason=AgentStopReason.COMPLETED,
        ),
        "provenance": AgentArtifactProvenance(
            skill_name="rolo-adapt-discovery",
            skill_version="1.0.0",
            model_id="fixture-model",
            input_artifact_sha256={"evidence-index": SHA},
        ),
    }
    values.update(updates)
    return AdaptDiscoveryPlan.model_validate(values)


def test_discovery_plan_is_strict_r0_and_provenance_bound() -> None:
    plan = _discovery_plan()

    assert plan.schema_version == "rolo-adapt-discovery-plan/v1"
    assert plan.actions[0].risk == "R0"
    assert plan.provenance.input_artifact_sha256 == {"evidence-index": SHA}

    payload = plan.model_dump(mode="json")
    payload["unexpected"] = True
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        AdaptDiscoveryPlan.model_validate(payload)

    payload = plan.model_dump(mode="json")
    payload["actions"][0]["risk"] = "R1"
    with pytest.raises(ValidationError):
        AdaptDiscoveryPlan.model_validate(payload)


def test_discovery_plan_rejects_duplicates_and_placeholders() -> None:
    action = _discovery_plan().actions[0]
    with pytest.raises(ValidationError, match="action IDs must be unique"):
        _discovery_plan(actions=[action, action])

    with pytest.raises(ValidationError, match="placeholders"):
        _discovery_plan(unknowns=["TODO inspect the ROS graph"])

    payload = _discovery_plan().model_dump(mode="json")
    payload["actions"][0]["parameters"] = {"path": "<placeholder>"}
    with pytest.raises(ValidationError, match="placeholders"):
        AdaptDiscoveryPlan.model_validate(payload)


def test_wiki_new_writer_and_legacy_reader_are_separate() -> None:
    current = RoloWikiInsightBundle(
        robot_id="demo",
        discovery_id="disc-1",
        provenance=AgentArtifactProvenance(
            skill_name="rolo-wiki-authoring",
            skill_version="1.0.0",
            model_id="fixture-model",
            input_artifact_sha256={"evidence-index": SHA},
        ),
    )
    legacy = WikiInsightBundle.model_validate(
        {
            "schema_version": "robot-wiki-insights/v1",
            "robot_id": "demo",
            "discovery_id": "disc-1",
        }
    )

    assert current.schema_version == "rolo-wiki-insights/v1"
    assert legacy.schema_version == "robot-wiki-insights/v1"
    with pytest.raises(ValidationError):
        RoloWikiInsightBundle.model_validate(legacy.model_dump(mode="json"))


def test_wiki_writer_schema_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        RoloWikiInsightBundle.model_validate(
            {
                "robot_id": "demo",
                "discovery_id": "disc-1",
                "eligibility": "VERIFIED",
                "provenance": {
                    "skill_name": "rolo-wiki-authoring",
                    "skill_version": "1.0.0",
                    "model_id": "fixture-model",
                    "input_artifact_sha256": {"evidence-index": SHA},
                },
            }
        )


def test_wiki_writer_requires_matching_author_and_artifact_provenance() -> None:
    provenance = AgentArtifactProvenance(
        skill_name="rolo-wiki-authoring",
        skill_version="1.0.0",
        model_id="fixture-model",
        input_artifact_sha256={"evidence-index": SHA},
    )
    with pytest.raises(ValidationError, match="author versions must match"):
        RoloWikiInsightBundle.model_validate(
            {
                "robot_id": "demo",
                "discovery_id": "disc-1",
                "provenance": provenance,
                "findings": [
                    {
                        "category": "MAINTENANCE",
                        "statement": "The deployed revision may need review.",
                        "confidence": "LOW",
                        "basis": ["release.summary"],
                        "verification": "Compare the read-only release manifest.",
                        "author_skill_version": "2.0.0",
                    }
                ],
            }
        )
