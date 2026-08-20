# P0 Adapt acceptance

This document fixes the minimum evidence required before Adapt may publish a robot release. It does
not claim that an operation is correct, reliable, performant, or physically safe. Those judgements
belong to Diagnose and Verify. Adapt proves contract integrity, registration, immutable binding, and
route existence only.

## Route Evidence v2

`robot-route-evidence/v2` is the only representation evaluated inside the Adapt gate. Each record
contains:

- stable resource/interface ID, route kind, and endpoint;
- observed-runtime or declared-static origin and evidence source;
- optional interface type and interface-schema SHA-256;
- optional provider/executable identity and runtime revision;
- optional observation timestamp and explicit collection limitations.

The gate supports exact matching for ROS topics, services, actions, device paths, and CLI
executables. If an expected record supplies a type, schema digest, provider, or runtime revision, the
observed record must supply the same value. Missing optional fields are not invented.

## Conformance ownership

The complete gate surface has two disjoint owners:

1. Rolo validates builtin operation contracts and builtin catalog bindings.
2. Adapter Agent reports local-static checks for bundle candidates only.

An Agent report containing a builtin, omitting a bundle candidate, or adding an unknown operation is
rejected. Agent booleans remain advisory audit input. Rolo independently validates contract digests,
the package `describe` surface, target-observed routes, the generated catalog, and immutable release
hashes.

## Acceptance paths

### Source-only negative path

Source and documentation may create `DISCOVERED_UNVERIFIED` candidates, but never `VERIFIED`
catalog entries. With no matching target runtime probe, promotion must fail and no current release
index may be activated.

The 2026-08-20 local acceptance run used the two external open-source validation projects:

| Project | Discovery | Candidates | Required result |
|---|---:|---:|---|
| Unitree Go1 `unitree_legged_sdk` | `PARTIAL`, `DOC_PROBE` | 0 | no verified operation |
| Wheeltec `wheeltec_drivers` with `mini_akm_robot.urdf` | `PARTIAL`, `DOC_PROBE` | 2 | `app.teleop.velocity` and `app.camera.snapshot` remain declared-static `DISCOVERED_UNVERIFIED` |

The projects are validation input outside the Rolo repository and are not copied into product source.
The automated source-only test uses bounded synthetic equivalents so CI does not depend on desktop
paths or third-party repository availability.

### Simulated target-runtime positive path

The automated test substitutes a target-runtime probe at the discovery boundary, then exercises the
real sequence:

`discovery -> isolated Agent output -> frozen snapshot -> Rolo gate -> Tool Catalog -> State Graph -> immutable release -> generic invoke`

The provider is test-only. Production has no switch that treats source, documentation, or simulation
as physical target evidence.

### Runtime authorization path

The published-release test matrix covers:

- R0 read invocation;
- SENSITIVE deny and allow;
- R2 OS identity and exact operation allowlist deny and allow;
- execution-quiescence lease binding;
- R3 request/robot/operation/input-digest binding;
- session start/stop;
- cancelable start plus its compensation/cancel operation;
- digest-pinned config apply plus independently authorized rollback;
- release/package hash mismatch rejection;
- audit records that contain authorization identifiers but no input/output payload.

The R3 and quiescence programs under `tests/fixtures/providers` are executable protocol fixtures only.
They are never production defaults and still pass through the same request/response models used by a
deployment-owned protected provider.

## Verification commands

```powershell
uv run pytest tests/test_conformance.py tests/test_discovery.py tests/test_stages.py
uv run pytest tests/test_runtime_authorization_e2e.py tests/test_invocation_policy.py tests/test_adapter_runtime.py
uv run pytest
uv run ruff check .
```
