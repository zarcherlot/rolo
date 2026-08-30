from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel

from rolo.stages.adapt.agent_contracts import OperationProposalBundle
from rolo.stages.adapt.codex_output_schema import codex_output_schema
from rolo.stages.adapt.skill_contracts import AdaptDiscoveryPlan
from rolo.stages.adapt.wiki_insights import RoloWikiInsightBundle


def _all_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | set().union(*(_all_keys(item) for item in value.values()), set())
    if isinstance(value, list):
        return set().union(*(_all_keys(item) for item in value), set())
    return set()


def _assert_all_properties_required(value: Any) -> None:
    if isinstance(value, dict):
        if isinstance(value.get("properties"), dict):
            assert value.get("required") == list(value["properties"])
        for item in value.values():
            _assert_all_properties_required(item)
    elif isinstance(value, list):
        for item in value:
            _assert_all_properties_required(item)


def test_codex_output_schema_removes_unsupported_property_bounds() -> None:
    for model in (AdaptDiscoveryPlan, OperationProposalBundle):
        canonical = model.model_json_schema()
        compatible = codex_output_schema(
            model,
            fixed_string_map_keys={"input_artifact_sha256": ["discovery", "registry"]},
            fixed_string_enums={"unknown": ["runtime graph unavailable"]},
            closed_object_fields=("parameters",),
        )

        assert "maxProperties" in _all_keys(canonical)
        assert "maxProperties" not in _all_keys(compatible)
        assert "minProperties" not in _all_keys(compatible)
        _assert_all_properties_required(compatible)
        assert compatible is not canonical

        provenance = compatible["$defs"]["AgentArtifactProvenance"]
        hashes = provenance["properties"]["input_artifact_sha256"]
        assert list(hashes["properties"]) == ["discovery", "registry"]
        assert hashes["required"] == ["discovery", "registry"]
        assert hashes["additionalProperties"] is False

        if model is AdaptDiscoveryPlan:
            assert "JsonValue" not in compatible["$defs"]
            action = compatible["$defs"]["DiscoveryPlanAction"]
            parameters = action["properties"]["parameters"]
            assert parameters["properties"] == {}
            assert parameters["required"] == []
            assert parameters["additionalProperties"] is False


def test_codex_output_schema_can_pin_agent_unknowns_to_caller_values() -> None:
    compatible = codex_output_schema(
        RoloWikiInsightBundle,
        fixed_string_map_keys={"input_artifact_sha256": ["discovery-context"]},
        fixed_string_enums={"unknown": ["platform.compute", "platform.drive_model"]},
    )

    assessment = compatible["$defs"]["RoloWikiUnknownAssessment"]
    assert assessment["properties"]["unknown"]["enum"] == [
        "platform.compute",
        "platform.drive_model",
    ]


def test_codex_output_schema_can_pin_array_items_to_caller_values() -> None:
    refs = ["probes.ros.status", "active_discovery.unknowns[0]"]
    compatible = codex_output_schema(
        RoloWikiInsightBundle,
        fixed_string_enums={"basis": refs, "counter_evidence_refs": refs},
    )

    finding = compatible["$defs"]["RoloWikiHeuristicFinding"]
    assessment = compatible["$defs"]["RoloWikiUnknownAssessment"]
    assert finding["properties"]["basis"]["items"]["enum"] == refs
    assert finding["properties"]["counter_evidence_refs"]["items"]["enum"] == refs
    assert assessment["properties"]["basis"]["items"]["enum"] == refs


def test_codex_output_schema_removes_defaults_next_to_references() -> None:
    class DemoDisposition(str, Enum):
        ACCEPT = "ACCEPT"

    class DemoModel(BaseModel):
        disposition: DemoDisposition = DemoDisposition.ACCEPT

    canonical = DemoModel.model_json_schema()
    compatible = codex_output_schema(DemoModel)

    canonical_disposition = canonical["properties"]["disposition"]
    compatible_disposition = compatible["properties"]["disposition"]

    assert canonical_disposition["$ref"] == "#/$defs/DemoDisposition"
    assert canonical_disposition["default"] == "ACCEPT"
    assert compatible_disposition == {"$ref": "#/$defs/DemoDisposition"}
