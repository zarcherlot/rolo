from __future__ import annotations

import json
from pathlib import Path


def _design() -> dict[str, object]:
    path = Path(__file__).parents[1] / "schemas" / "rolo-episode-contract-design-v1.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _revision_contract() -> str:
    path = Path(__file__).parents[1] / "docs" / "EPISODE_REVISION_HISTORY_CONTRACT.md"
    return path.read_text(encoding="utf-8")


def test_episode_contract_design_is_versioned_and_baseline_relative() -> None:
    design = _design()
    assert design["schema_version"] == "rolo-episode-contract-design/v1"
    assert design["status"] == "e2-implementation-review"
    assert design["base_read_model_baseline"] == "rolo-vis-mvp-read-model-v1"
    assert design["contracts"] == {
        "collection": "rolo-episode-collection/v1",
        "summary": "rolo-episode-summary/v1",
        "detail": "rolo-episode-detail/v1",
        "timeline_page": "rolo-episode-timeline-page/v1",
        "timeline_event": "rolo-episode-timeline-event/v1",
        "asset_summary": "rolo-episode-asset-summary/v1",
        "finding_summary": "rolo-episode-finding-summary/v1",
    }


def test_episode_contract_keeps_lifecycle_outcome_and_verification_separate() -> None:
    design = _design()
    assert design["episode_states"] != design["execution_outcomes"]
    assert design["execution_outcomes"] != design["verification_states"]
    assert "UNKNOWN" in design["execution_outcomes"]
    assert "UNVERIFIED" in design["verification_states"]


def test_episode_contract_preserves_timeline_and_evidence_authority() -> None:
    design = _design()
    assert {"COMMAND", "OBSERVATION", "AGENT", "OUTCOME"} <= set(
        design["timeline_lanes"]
    )
    assert set(design["authorities"]) == {
        "DECLARED",
        "OBSERVED",
        "INFERRED",
        "HUMAN_CONFIRMED",
        "VERIFIED",
    }
    assert set(design["world_kinds"]) == {"PHYSICAL", "SIMULATED", "REPLAYED"}


def test_episode_contract_forbids_internal_locations_and_payloads() -> None:
    forbidden = set(_design()["forbidden_fields"])
    assert {
        "artifact_ref",
        "local_path",
        "remote_path",
        "signed_url",
        "credential",
        "command_payload",
        "model_prompt",
        "model_response",
    } <= forbidden


def test_episode_v1_defers_unsafe_or_unstable_surfaces() -> None:
    deferred = " ".join(_design()["deferred"]).lower()
    assert "asset content" in deferred
    assert "live streaming" in deferred
    assert "compare" in deferred
    assert "remediation" in deferred


def test_episode_e1_publishes_only_a_sanitized_server_owned_projection() -> None:
    implementation = _design()["implementation"]
    assert implementation == {
        "health_feature": "workbench.episode-read-model/v1",
        "publication_schema": "rolo-episode-published-projection/v1",
        "publication_location": "episodes/{robot_id}/published/{episode_id}.json",
        "producer_record_schema": "rolo-episode-producer-record/v1",
        "producer_record_location": (
            "episodes/{robot_id}/records/{episode_id}/revision-{revision}.json"
        ),
        "producer_projection": "implemented-e2",
        "evidence_integration": "rolo-evidence-record/v1",
    }


def test_episode_revision_history_is_feature_negotiated_and_read_only() -> None:
    contract = _revision_contract()
    assert "workbench.episode-revision-history/v1" in contract
    assert "rolo-episode-revision-collection/v1" in contract
    assert "rolo-episode-revision-summary/v1" in contract
    assert "?revision={revision}" in contract
    assert "Deltas remain neutral `right - left` facts" in contract
    assert "adds no replay, recollection, export, remediation" in contract
