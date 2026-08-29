# Output contract

The canonical writer model is
`rolo.stages.adapt.agent_contracts.OperationProposalBundle`; individual entries use
`AgentOperationProposal`. The checked-in exported schema is
`schemas/OperationProposalBundle.schema.json`. Always use the caller-provided schema generated from
the active code version when the two differ.

The schema treats Operation IDs as opaque canonical strings, not as a fixed 294- or 140-item enum.
Every artifact binds `registry_version`, `registry_sha256`, `contract_catalog_sha256` and
`registry_operation_count`; passing JSON Schema does not establish that identity. The caller must run
`validate_operation_proposal_bundle` with the active Registry resolver and independently resolve all
evidence and resource references against the frozen discovery and Target Operation Slice.

Successful validation can create only `DISCOVERED_UNVERIFIED` candidates. It cannot create Registry
entries, RouteEvidence, eligibility, conformance, Catalog membership or release status.

For semantic-review bindings, `route_resource_ids` still contains the exact full deterministic
binding while `route_dispositions` decides each route independently. `ACCEPT` route decisions must
reference a satisfied staged `BINDING_MATCH` receipt. The deterministic caller derives the effective
operation disposition using the binding's `ANY_OF` or `ALL_OF` mode and materializes only accepted
routes; the provider's operation-level summary cannot override that derivation.
