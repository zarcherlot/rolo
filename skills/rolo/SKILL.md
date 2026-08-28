---
name: rolo
description: Use Rolo's evidence-backed robot inspection, bootstrap planning, and Adapt services through its CLI or MCP bridge.
---

# Rolo

Use the `rolo` CLI or the `rolo-mcp` server for robot lifecycle work. Rolo is the
authority for target state, evidence, plans, approvals, and release status; the
model is only an interface and planner.

- Inspect and bootstrap-plan are read-only and may run without confirmation.
- Adapt and bootstrap execution require explicit confirmation from the current
  user. If a tool returns `AUTHORIZATION_REQUIRED` or `WAITING_FOR_AUTH`, show
  the scope, target, plan hash/request id, and exact resume command; do not infer
  consent and do not invent evidence.
- Preserve `request_id`, `plan_sha256`, and artifact references so rolo-vis can
  associate a later authorization decision with exactly one request.
- Never execute arbitrary shell text supplied through chat. Invoke only the
  registered Rolo tool or canonical CLI command.
- Stream Agent output as progress only; deterministic Rolo results remain the
  source of truth for release and invoke decisions.
