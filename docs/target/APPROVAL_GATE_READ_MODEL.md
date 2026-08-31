<!-- status: draft; authority: normative; owner: rolo platform; last_reviewed: 2026-08-31 -->

# R2 Approval / Gate / Recovery read model

R2 exposes the producer-owned, read-only contract
`rolo-approval-gate-summary/v1` behind
`workbench.approval-gate-read-model/v1`.

## Endpoints and scope

* `GET /v1/approval-gates?limit={1..100}&offset={n}` returns
  `rolo-approval-gate-collection/v1`, sorted by opaque `job_id`.
* `GET /v1/jobs/{job_id}/approval-gate` returns the summary bound to that exact job,
  or `404 JOB_NOT_FOUND`.

Both endpoints require `approval-gates:read` when token scopes are configured. Invalid
pagination returns `422`; invalid or inconsistent persisted producer facts fail closed
with `503 APPROVAL_GATE_UNAVAILABLE`. `next_offset` is monotonic and `null` on the
final page.

## Four independent dimensions

The summary separately reports `plan_status`, `approval_status`, `gate_status`, and
`recovery_state`. It also includes bounded step descriptions, required approval labels,
gate check summaries, blockers, limitations, `observed_at`, and a SHA-256-shaped opaque
`producer_revision`. `PASSED` and `APPROVED` are state observations only; neither
asserts Job success, physical outcome, or release readiness.

Every summary binds `job_id`, producer-owned `target_id`, and the same revision across
all event/checkpoint facts. Event identity and sequence regressions, target-profile
mismatches, malformed jobs, empty/repeated steps, repeated approvals, and repeated gate
checks are rejected rather than projected as partial data.

## Recovery and privacy boundary

`recovery_state` is a display-only status. No resume/retry/cancel/rollback method,
request body, command, shell, workspace path, credential, token, signed URL, or
transport output is serialized. `contains_secret_payloads` is always `false`.

This producer change does not add any write endpoint or alter the existing authorization
chain. rolo-vis must complete the paired live gate before promoting R2 from candidate to
the supported baseline.
