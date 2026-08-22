# Output contract

The authoritative model is
`rolo.stages.adapt.skill_contracts.AdaptDiscoveryPlan`. The caller must derive the JSON Schema from
`AdaptDiscoveryPlan.model_json_schema()` and validate the returned object before considering any
action.

The v1 object binds the robot, discovery and target fingerprint; contains zero to 32 R0 `PROBE` or
`QUERY` actions; records unknowns, stop conditions, remaining budget and actual usage; and carries
`AgentArtifactProvenance`. `extra="forbid"` applies at every level.

An action's `definition_id` is a reference to a caller-owned whitelist entry. Passing this schema does
not prove that the definition is currently allowed or that its parameters match the definition's own
schema. The orchestrator must check both, recalculate budgets, and execute separately. It must reject
placeholders, stale artifact hashes, non-R0 actions and unknown definition IDs.
