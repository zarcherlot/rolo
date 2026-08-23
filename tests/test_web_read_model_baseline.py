from __future__ import annotations

import json
from pathlib import Path

from rolo.capability_read_models import (
    CapabilityCollection,
    CapabilityDetail,
    CapabilityInferredBinding,
    CapabilitySummary,
)
from rolo.discovery_history_read_models import (
    DiscoveryHeuristicSummary,
    DiscoverySnapshotCollection,
    DiscoverySnapshotSummary,
    DiscoveryTargetEvidenceSummary,
)


def _baseline() -> dict[str, object]:
    path = Path(__file__).parents[1] / "schemas" / "rolo-web-read-model-baseline-v1.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_mvp_web_baseline_matches_published_model_versions() -> None:
    baseline = _baseline()
    assert baseline["schema_version"] == "rolo-web-read-model-baseline/v1"
    assert baseline["status"] == "baseline"
    assert baseline["mode"] == "read-only"

    contracts = baseline["contracts"]
    assert isinstance(contracts, dict)
    expected = {
        "capability_collection": CapabilityCollection,
        "capability_summary": CapabilitySummary,
        "capability_detail": CapabilityDetail,
        "capability_inferred_binding": CapabilityInferredBinding,
        "discovery_collection": DiscoverySnapshotCollection,
        "discovery_summary": DiscoverySnapshotSummary,
        "discovery_heuristic_summary": DiscoveryHeuristicSummary,
        "discovery_target_evidence_summary": DiscoveryTargetEvidenceSummary,
    }
    for name, model in expected.items():
        assert contracts[name] == model.model_fields["schema_version"].default


def test_mvp_web_baseline_keeps_trust_invariants_explicit() -> None:
    invariants = _baseline()["trust_invariants"]
    assert isinstance(invariants, list)
    text = " ".join(str(item) for item in invariants).lower()
    assert "never influences release" in text
    assert "unverified" in text
    assert "backend" in text
    assert "no raw artifact or host paths" in text
