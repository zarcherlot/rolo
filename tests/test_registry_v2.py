from rolo.stages.adapt.operation_registry_v2 import (
    RegistryView,
    build_registry_projection,
    project_definitions,
)


def test_projection_is_deterministic_and_preserves_v1_source_identity() -> None:
    first = build_registry_projection()
    second = build_registry_projection()

    assert first == second
    assert first.source_operation_count == 294
    assert len(first.source_registry_sha256) == 64
    assert sum(len(first.operations(view)) for view in RegistryView) == 294


def test_projection_has_separate_canonical_and_native_views() -> None:
    projection = build_registry_projection()

    assert len(projection.canonical_operations) == 197
    assert len(projection.agent_native_operations) == 73
    assert len(projection.product_control_operations) == 13
    assert len(projection.provider_operations) == 11
    assert set(projection.canonical_operations).isdisjoint(projection.agent_native_operations)
    assert "linux.process.list" in projection.agent_native_operations
    assert "app.teleop.velocity" in projection.canonical_operations


def test_projected_definitions_are_only_a_shadow_view() -> None:
    assert len(project_definitions(RegistryView.CANONICAL)) == 197
    assert len(project_definitions(RegistryView.AGENT_NATIVE)) == 73
    assert len(project_definitions(RegistryView.PRODUCT_CONTROL)) == 13
    assert len(project_definitions(RegistryView.PROVIDER)) == 11

