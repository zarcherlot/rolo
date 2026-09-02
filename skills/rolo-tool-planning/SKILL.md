---
name: rolo-tool-planning
description: Turn a user goal and Rolo's discovered tool surface into a bounded, typed ToolPlan.
---

# Rolo Tool Planning

Use this skill after Rolo has produced a target-bound Tool Surface or Adapter Bundle. The
agent may choose tools and fill typed arguments, but Rolo remains the authority for discovery,
policy, execution, evidence, conformance, and release.

## Input

Require a Rolo target/session identity, the tool-surface digest, and the user's goal. If the
surface is absent or stale, ask Rolo for a fresh inspect/bootstrap result before planning.

## Output

Emit a bounded `rolo-tool-plan/v1` containing:

- `goal` and ordered `steps`;
- each step's exact `tool_id`, typed `arguments`, and expected observation;
- `mode` (`readonly` or `mutating`), with mutating steps requiring explicit user approval;
- `surface_digest`, `target_id`, `session_id`, and a deterministic `plan_sha256`.
- `session_nonce` copied from the Tool Surface; it binds the plan to the exact session issuance.

Never emit shell text, free-form argv, guessed tool IDs, or a route that is not present in the
surface. A capability gap is a typed result (`CAPABILITY_GAP`) that points back to the missing
semantic contract; it is not permission to improvise a command. The orchestrator may then start
a bounded Probe gap path, where Rolo probes, verifies, conforms, and publishes only the new tool.
