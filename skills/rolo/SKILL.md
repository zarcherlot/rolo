---
name: rolo
description: Use Rolo's evidence-backed robot enrollment, Probe tools, bootstrap planning, and conformance through its CLI.
---

# Rolo

Use the `rolo` CLI or `robotctl` CLI for robot lifecycle work. Rolo is the
authority for target state, evidence, plans, approvals, and release status; the
model is only an interface and planner.

- Inspect, bootstrap-plan, Probe and target-evidence collection are read-only and
  may run without confirmation. v2 has no host-mutating bootstrap command.
- Preserve `request_id`, `plan_sha256`, and artifact references so the current Agent can
  associate a later authorization decision with exactly one request.
- Never execute arbitrary shell text supplied through chat. Invoke only the
  registered Rolo tool or canonical CLI command.
- Stream Agent output as progress only; deterministic Rolo results remain the
  source of truth for release and invoke decisions.
