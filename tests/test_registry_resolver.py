import pytest

from rolo.stages.adapt.registry_resolver import load_registry_resolver, resolver_for_identity


def test_v1_resolver_preserves_current_registry_identity_surface() -> None:
    resolver = load_registry_resolver("v1")

    assert resolver.operation_count == 294
    assert resolver.contract_sha256_for("linux.process.list")
    assert resolver.contract_catalog_sha256
    assert resolver.registry_sha256


def test_v2_shadow_resolver_is_explicit_and_narrower() -> None:
    v1 = load_registry_resolver("v1")
    v2 = load_registry_resolver("v2-shadow")

    assert v2.operation_count == 197
    assert v2.registry_version == "v2-shadow"
    assert v2.registry_sha256 != v1.registry_sha256
    assert v2.contract_sha256_for("linux.process.list") is None
    assert v2.contract_sha256_for("app.teleop.velocity")


def test_resolver_rejects_cross_generation_identity() -> None:
    v1 = load_registry_resolver("v1")

    assert resolver_for_identity("v1", v1.registry_sha256).operation_count == 294
    with pytest.raises(ValueError, match="does not match"):
        resolver_for_identity("v2-shadow", v1.registry_sha256)

