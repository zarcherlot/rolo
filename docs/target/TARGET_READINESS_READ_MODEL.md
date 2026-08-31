<!-- status: draft; authority: normative; owner: rolo platform; last_reviewed: 2026-08-31 -->

# R1 Target Readiness read model

This release adds the producer-owned, read-only R1 contract
`rolo-target-readiness-summary/v1` behind the feature gate
`workbench.target-readiness/v1`.

## Endpoints

* `GET /v1/targets/readiness?limit={1..100}&offset={n}` returns
  `rolo-target-readiness-collection/v1`. Items are sorted by opaque `target_id` and
  `next_offset` is `null` on the final page.
* `GET /v1/targets/{target_id}/readiness` returns one
  `rolo-target-readiness-summary/v1` or `404 TARGET_NOT_FOUND`.

Both endpoints require the `targets:read` scope when API token scopes are configured.
Malformed or unavailable producer facts fail closed with `503 TARGET_READINESS_UNAVAILABLE`;
FastAPI returns `422` for invalid pagination values.

## Contract and privacy boundary

The summary reports `target_kind`, `state`, `reachable`, `host_key_pinned`,
`platform`, `architecture`, `workspace_accessible`, `companion`, bounded
`blockers`/`diagnostics`/`limitations`, `observed_at`, `freshness`, and an opaque
`producer_revision`. `contains_secret_payloads` is always `false`.

No target URI, host, SSH user, workspace path, credential reference, token, key,
known-hosts material, command, transport detail, or artifact bytes are serialized.
Local targets are checked against the producer's filesystem. SSH targets remain
`HOST_KEY_REQUIRED` until their host key is approved and otherwise report
`UNREACHABLE` with `freshness: unknown` until the paired read-only probe is available.

R1 is a producer contract only in this change. rolo-vis must complete its paired
live gate before promoting this feature from candidate to the supported baseline.
