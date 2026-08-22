from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from rolo.core.hashing import sha256_bytes
from rolo.stages.adapt.agent_contracts import (
    AgentArtifactProvenance,
    AgentBudgetUsage,
    AgentOperationProposal,
    AgentStopReason,
    OperationProposalBundle,
    ProposalConfidence,
    ToolSessionBudget,
    ToolSessionDescriptor,
    registry_contract_hashes,
    registry_identity_sha256,
    validate_operation_proposal_bundle,
    validate_tool_session_descriptor,
)
from rolo.stages.adapt.operation_registry import canonical_operation_registry


@dataclass(frozen=True)
class FixtureRegistryResolver:
    registry_version: str
    registry_sha256: str
    contract_catalog_sha256: str
    contracts: dict[str, str]

    @property
    def operation_count(self) -> int:
        return len(self.contracts)

    def contract_sha256_for(self, operation: str) -> str | None:
        return self.contracts.get(operation)


def _fixture_registry(size: int) -> FixtureRegistryResolver:
    contracts = {
        f"app.fixture.operation_{index:03d}": sha256_bytes(f"contract:{index}".encode())
        for index in range(size)
    }
    catalog_sha256 = sha256_bytes(f"catalog:{size}".encode())
    return FixtureRegistryResolver(
        registry_version="rolo-canonical-operation-registry/v1",
        registry_sha256=registry_identity_sha256(
            registry_version="rolo-canonical-operation-registry/v1",
            contract_catalog_sha256=catalog_sha256,
            contract_sha256=contracts,
        ),
        contract_catalog_sha256=catalog_sha256,
        contracts=contracts,
    )


def _current_registry_resolver() -> FixtureRegistryResolver:
    registry = canonical_operation_registry()
    contracts = {
        definition.operation: definition.contract_sha256 for definition in registry.operations
    }
    return FixtureRegistryResolver(
        registry_version=registry.schema_version,
        registry_sha256=registry_identity_sha256(
            registry_version=registry.schema_version,
            contract_catalog_sha256=registry.contract_catalog_sha256,
            contract_sha256=contracts,
        ),
        contract_catalog_sha256=registry.contract_catalog_sha256,
        contracts=contracts,
    )


def _proposal(operation: str, index: int) -> AgentOperationProposal:
    return AgentOperationProposal(
        operation=operation,
        evidence_refs=[f"evidence:{index}"],
        route_resource_ids=[f"ros_topic:/fixture/{index}"],
        confidence=ProposalConfidence.MEDIUM,
        rationale="The collected route and interface evidence support this mapping.",
    )


def _proposal_bundle(
    resolver: FixtureRegistryResolver,
    *,
    operations: list[str] | None = None,
) -> OperationProposalBundle:
    selected = operations if operations is not None else list(resolver.contracts)
    return OperationProposalBundle(
        robot_id="fixture-robot",
        discovery_id="discovery-1",
        target_fingerprint_sha256="a" * 64,
        registry_version=resolver.registry_version,
        registry_sha256=resolver.registry_sha256,
        contract_catalog_sha256=resolver.contract_catalog_sha256,
        registry_operation_count=resolver.operation_count,
        proposals=[_proposal(operation, index) for index, operation in enumerate(selected)],
        budget_usage=AgentBudgetUsage(
            rounds=2,
            input_tokens=4_000,
            output_tokens=2_000,
            elapsed_ms=1_500,
            result_bytes=8_000,
            stop_reason=AgentStopReason.COMPLETED,
        ),
        provenance=AgentArtifactProvenance(
            skill_name="rolo-operation-mapping",
            skill_version="1.0.0",
            model_id="fixture-model",
            input_artifact_sha256={"discovery": "b" * 64},
        ),
    )


def _tool_session(resolver: FixtureRegistryResolver) -> ToolSessionDescriptor:
    operations = list(resolver.contracts)
    created_at = datetime(2026, 8, 22, tzinfo=timezone.utc)
    return ToolSessionDescriptor(
        session_id="session-1",
        nonce="fixture_nonce_1234567890",
        robot_id="fixture-robot",
        release_id="release-1",
        target_fingerprint_sha256="c" * 64,
        registry_version=resolver.registry_version,
        registry_sha256=resolver.registry_sha256,
        registry_operation_count=resolver.operation_count,
        contract_catalog_sha256=resolver.contract_catalog_sha256,
        tool_catalog_sha256="d" * 64,
        state_graph_sha256="e" * 64,
        allowed_operations=operations,
        contract_sha256=dict(registry_contract_hashes(operations, resolver)),
        caller="diagnose-agent",
        stage="diagnose",
        policy_version="policy-v1",
        budget=ToolSessionBudget(
            max_calls=64,
            max_elapsed_s=300,
            max_result_bytes=8_000_000,
        ),
        created_at=created_at,
        expires_at=created_at + timedelta(minutes=30),
    )


@pytest.mark.parametrize("operation_count", [140, 294])
def test_proposal_bundle_contract_is_registry_quantity_independent(
    operation_count: int,
) -> None:
    resolver = _fixture_registry(operation_count)
    bundle = _proposal_bundle(resolver)

    validate_operation_proposal_bundle(bundle, resolver)

    assert len(bundle.proposals) == operation_count
    schema = OperationProposalBundle.model_json_schema()
    serialized_schema = str(schema)
    assert "app.fixture.operation_000" not in serialized_schema
    operation_property = schema["$defs"]["AgentOperationProposal"]["properties"]["operation"]
    assert operation_property["type"] == "string"
    assert "pattern" in operation_property


def test_proposal_bundle_binds_the_current_294_operation_registry() -> None:
    resolver = _current_registry_resolver()
    assert resolver.operation_count == 294

    bundle = _proposal_bundle(resolver)
    validate_operation_proposal_bundle(bundle, resolver)


@pytest.mark.parametrize("operation_count", [140, 294])
def test_tool_session_contract_is_registry_quantity_independent(operation_count: int) -> None:
    resolver = _fixture_registry(operation_count)
    session = _tool_session(resolver)

    validate_tool_session_descriptor(session, resolver)

    assert len(session.allowed_operations) == operation_count
    assert set(session.contract_sha256) == set(session.allowed_operations)


def test_proposal_bundle_rejects_stale_registry_identity_and_unknown_operations() -> None:
    resolver = _fixture_registry(140)
    stale = _proposal_bundle(resolver).model_copy(update={"registry_sha256": "f" * 64})
    with pytest.raises(ValueError, match="Registry identity"):
        validate_operation_proposal_bundle(stale, resolver)

    unknown = _proposal_bundle(
        resolver,
        operations=["app.fixture.operation_999"],
    )
    with pytest.raises(ValueError, match="outside the active Registry"):
        validate_operation_proposal_bundle(unknown, resolver)


def test_proposal_contract_rejects_duplicates_unbound_claims_and_extra_fields() -> None:
    resolver = _fixture_registry(140)
    proposal = _proposal(next(iter(resolver.contracts)), 0)
    with pytest.raises(ValidationError, match="duplicate operations"):
        OperationProposalBundle(
            **{
                **_proposal_bundle(resolver).model_dump(),
                "proposals": [proposal.model_dump(), proposal.model_dump()],
            }
        )

    payload = proposal.model_dump()
    payload["route_resource_ids"] = []
    with pytest.raises(ValidationError, match="target resource binding"):
        AgentOperationProposal.model_validate(payload)

    payload = proposal.model_dump()
    payload["verified"] = True
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        AgentOperationProposal.model_validate(payload)


def test_tool_session_requires_exact_contract_coverage_and_identity() -> None:
    resolver = _fixture_registry(140)
    session = _tool_session(resolver)
    operation = session.allowed_operations[0]
    tampered_hashes = dict(session.contract_sha256)
    tampered_hashes[operation] = "f" * 64
    tampered = session.model_copy(update={"contract_sha256": tampered_hashes})

    with pytest.raises(ValueError, match="contract identity mismatch"):
        validate_tool_session_descriptor(tampered, resolver)

    payload = session.model_dump()
    payload["contract_sha256"].pop(operation)
    with pytest.raises(ValidationError, match="exactly cover"):
        ToolSessionDescriptor.model_validate(payload)


def test_tool_session_ttl_is_positive_and_bounded() -> None:
    resolver = _fixture_registry(140)
    session = _tool_session(resolver)

    for expires_at in (
        session.created_at,
        session.created_at + timedelta(hours=24, seconds=1),
    ):
        with pytest.raises(ValidationError, match="expiry|TTL"):
            ToolSessionDescriptor.model_validate({**session.model_dump(), "expires_at": expires_at})
