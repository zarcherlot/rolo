# Output contract

The Agent-facing writer model is the minimal `AgentMappingDecisionBundle`. It contains only semantic
decisions, rationales, requested verification, unmapped capabilities and unknowns. The deterministic
caller materializes those decisions into `OperationProposalBundle`; the checked-in exported schema
for that final artifact is `schemas/OperationProposalBundle.schema.json`.

The schema treats Operation IDs as opaque canonical strings, not as a fixed 294- or 140-item enum.
Every artifact binds `registry_version`, `registry_sha256`, `contract_catalog_sha256` and
`registry_operation_count`; passing JSON Schema does not establish that identity. The caller must run
`validate_operation_proposal_bundle` with the active Registry resolver and independently resolve all
evidence and resource references against the frozen discovery and Target Operation Slice.

Successful validation can create only `DISCOVERED_UNVERIFIED` candidates. It cannot create Registry
entries, RouteEvidence, eligibility, conformance, Catalog membership or release status.

For semantic-review bindings, the Agent's `route_dispositions` decides each caller-supplied route
independently. The deterministic caller attaches the exact binding plus a satisfied `BINDING_MATCH`
receipt to each `ACCEPT` route and independently recomputes it during validation. The caller derives the effective
operation disposition using the binding's `ANY_OF` or `ALL_OF` mode and materializes only accepted
routes; the provider's operation-level summary cannot override that derivation.
