from collections import Counter

from rolo.stages.adapt.operation_governance import (
    ExecutionPath,
    RegistryRole,
    project_operation_roles,
)


def test_role_projection_preserves_v1_count_and_is_deterministic() -> None:
    first = project_operation_roles()
    second = project_operation_roles()

    assert first == second
    assert len(first) == 294
    assert len({item.operation for item in first}) == 294


def test_role_projection_separates_native_control_provider_and_canonical() -> None:
    projection = project_operation_roles()
    roles = Counter(item.registry_role for item in projection)

    assert roles == {
        RegistryRole.CANONICAL: 197,
        RegistryRole.AGENT_NATIVE: 73,
        RegistryRole.PRODUCT_CONTROL: 13,
        RegistryRole.PROVIDER: 11,
    }
    assert all(
        item.execution_path == ExecutionPath.ROS_CLI
        for item in projection
        if item.registry_role == RegistryRole.AGENT_NATIVE and item.current_layer == "ros"
    )
    assert all(
        item.execution_path == ExecutionPath.PROVIDER
        for item in projection
        if item.registry_role == RegistryRole.PROVIDER
    )


def test_agent_native_still_requires_a_security_boundary_but_not_product_contract() -> None:
    projection = project_operation_roles()
    native = next(item for item in projection if item.operation == "linux.process.list")

    assert native.registry_role == RegistryRole.AGENT_NATIVE
    assert native.execution_path == ExecutionPath.DIRECT_RUNNER
    assert native.security_boundary_required is True
    assert native.downstream_contract_required is False
    assert native.target_binding_required is False

