from scripts.validate_registry_migration import build_report


def test_registry_migration_report_has_disjoint_complete_views() -> None:
    report = build_report()

    assert report["status"] == "SUCCEEDED"
    assert report["source_operation_count"] == 294
    assert report["views"] == {
        "AGENT_NATIVE": 73,
        "CANONICAL": 197,
        "PRODUCT_CONTROL": 13,
        "PROVIDER": 11,
    }
    assert report["v1_v2_identity_distinct"] is True

