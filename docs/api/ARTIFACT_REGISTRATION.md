<!-- status: draft; authority: plan; owner: rolo maintainers; last_reviewed: 2026-09-01 -->

# Artifact registration API

Status: experimental · `RL-09A` · analysis-summary slice only

The control plane is normally a read model over producer-written artifacts. This API is
the first authenticated exception: it accepts one bounded, already-sanitized
`rolo-artifact-analysis-summary/v1` payload so a controlled producer can register a
summary into the same configuration root that the read endpoint serves.

## Endpoint and feature

- Feature: `workbench.artifact-registration/v1`
- Endpoint: `POST /v1/artifact-registrations`
- Required scope: `artifact-analysis:write`
- Read-back: `GET /v1/targets/{target_id}/artifact-analysis` with
  `artifact-analysis:read`

The request schema is `rolo-artifact-registration-request/v1`:

```json
{
  "schema_version": "rolo-artifact-registration-request/v1",
  "kind": "analysis_summary",
  "idempotency_key": "device-window-20260901",
  "target_id": "mentorpi",
  "summary": { "schema_version": "rolo-artifact-analysis-summary/v1" }
}
```

The summary is validated by the existing producer model. It must be target-bound,
`source_kind=rolo_api`, secret-free, bounded, and free of raw paths, URLs, command text,
credentials, and artifact bytes. If `job_id` is present, its persisted Job target must
resolve to the same target profile.

## Idempotency and conflict behavior

- The idempotency key is scoped to the configured artifact root and is persisted with a
  receipt (`rolo-artifact-registration-receipt/v1`). Repeating the exact request returns
  `REPLAYED` without rewriting the summary.
- Reusing a key for a different payload returns `409 ARTIFACT_REGISTRATION_CONFLICT`.
- A target with an existing summary is never overwritten; it also returns `409`.
- An unknown target profile, mismatched Job target, invalid summary, or unsupported
  registration kind is rejected. The API never fetches `artifact://` references or
  accepts a filesystem path as an import instruction.

## Deliberate scope

This slice does not register Job files, Bootstrap/Adapt gates, lifecycle handoffs, or
raw artifact bundles. Those kinds remain producer-owned and require their own canonical
writer, identity binding, audit, replay, and recovery design before being enabled under
this endpoint. The feature is therefore experimental and must not be used as release or
physical-outcome authority.
