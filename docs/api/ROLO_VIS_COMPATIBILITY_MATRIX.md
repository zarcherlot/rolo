<!-- status: active; authority: reference; owner: rolo maintainers; last_reviewed: 2026-08-31 -->

# rolo-vis Compatibility Matrix

| Surface | Feature | Read scope | Write scope | Failure semantics |
|---|---|---|---|---|
| R0 Jobs | `workbench.job-read-model/v1` | `jobs:read` | `jobs:execute` | unknown Job `404`; invalid persisted identity `409` |
| R1 Target Readiness | `workbench.target-readiness/v1` | `targets:read` | target bootstrap scopes | unavailable facts `409`; missing target `404` |
| R2 Approval/Gate/Recovery | `workbench.approval-gate-read-model/v1` | `approval-gates:read` | explicit approval/recovery scopes | target/job mismatch `409`; unknown Job `404` |
| R4 Artifact Analysis | `workbench.artifact-analysis-read-model/v1` | `artifact-analysis:read` | none | missing summary `503`/`404`; identity/schema mismatch `409` |

The `/health.api_features` list, API routes, canonical schema export, and this
matrix are maintained together. A token configured with read scopes cannot call
mutating endpoints; browser requests never trigger the staging harness. Clients
must feature-negotiate before issuing new requests and fail closed when a
feature is advertised but its payload schema is incompatible.
