<!-- status: archived; authority: normative; owner: rolo maintainers; last_reviewed: 2026-09-02; source_of_truth: ../architecture/ROLO_V2_CORE_DESIGN_ZH.md -->

# Artifact Analysis Producer Contract

Status: released read-only producer contract

Rolo publishes `rolo-artifact-analysis-summary/v1` through the negotiated feature
`workbench.artifact-analysis-read-model/v1`. The endpoint is:

```text
GET /v1/targets/{target_id}/artifact-analysis
GET /v1/jobs/{job_id}/artifact-analysis
```

Both routes require the `artifact-analysis:read` scope and return the same bounded
`ArtifactAnalysisSummary` schema. The producer binds `target_id`, `robot_id`,
`discovery_id`, and (when present) `job_id` before returning a response. A missing
summary is reported as `404 ARTIFACT_ANALYSIS_NOT_AVAILABLE`; malformed or
identity-mismatched data fails closed with `409 ARTIFACT_ANALYSIS_INVALID`.

The public projection contains metrics, operations, graph nodes, stages, findings,
redacted digests, freshness, gate/release-neutral labels, and limitations. It never
contains artifact bytes, file paths, URLs, SSH transport details, credentials,
commands, or executable argv. `source_kind` is always `rolo_api` for producer data,
and `contains_secret_payloads` is always `false`. Analysis status does not imply
capability readiness, job success, physical outcome, or release readiness.

For local live-gate development, run `python scripts/rolo-live-harness.py --port
8765`. The harness creates a temporary deterministic dataset with READY,
WORKSPACE_MISSING, HOST_KEY_REQUIRED, and UNREACHABLE target states, independent
approval/gate outcomes, and one sanitized artifact summary. It performs no host
connections or mutations.

