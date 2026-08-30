<!-- status: active; authority: reference; owner: ROLO maintainers; last_reviewed: 2026-08-30 -->

# E23 robot-hosted Workbench plugin contract

Status: E23A-E23C approved; E23D validation candidate

Target baseline: rolo-vis `v0.38.0`

Paired consumer contract: rolo-vis `docs/ROBOT_HOSTED_DELIVERY_CONTRACT.md`

Machine-readable decision catalog:
`schemas/rolo-workbench-plugin-host-contract-design-v1.json`

## 1. Decision

rolo-vis is a read-only plugin delivered with a robot and served by that robot's rolo
process. It is not a separately hosted public application. The production topology has
one browser origin, one rolo listener, no cloud runtime, and no second API process.

The Workbench entry point is `/workbench/`. Browser API requests use `/rolo-api/*`.
The existing rolo root API remains compatible for current CLI clients, tests, and
integrations. E23 must not duplicate endpoint declarations or loop HTTP back into the
same process. A small ASGI route adapter normalizes `/rolo-api/*` to the existing API
path before policy and endpoint dispatch, while `/workbench/*` is served only from the
validated plugin package.

## 2. Route contract

| Browser route | Authority | Required behavior |
| --- | --- | --- |
| `/workbench/` | plugin host | Serve the validated `index.html` |
| `/workbench/assets/*` | plugin host | Serve only package-owned immutable assets |
| `/workbench/*` | plugin host | Scoped SPA fallback to `index.html` |
| `/rolo-api/health` | existing rolo API | Normalize to `/health` |
| `/rolo-api/v1/*` | existing rolo API | Normalize to `/v1/*` without changing semantics |
| `/health`, `/v1/*` | existing rolo API | Preserve the current compatibility surface |

The SPA fallback is never allowed to consume `/rolo-api`, `/health`, `/v1`, unknown
top-level paths, or failed asset requests. A missing asset returns `404`; it must not
return `index.html`. Redirect `/workbench` to `/workbench/` without copying query
parameters into headers or filesystem paths.

## 3. Runtime and binding contract

`robotctl runtime serve` remains the only server command. A configured plugin directory
enables the Workbench route on the same listener; an absent plugin leaves the existing
API-only process unchanged.

The supported production modes are:

1. **Robot-local:** rolo binds to loopback and a browser on the robot opens the local
   Workbench URL.
2. **Trusted reverse proxy:** rolo still binds to loopback. A robot-owned proxy performs
   user access control and forwards the same-origin `/workbench` and `/rolo-api` paths.

Direct non-loopback browser hosting is not an E23 capability. The existing token-based
non-loopback API mode remains API-only because rolo-vis must not receive, persist, or
forward a bearer secret. Plugin hosting must fail closed or stay disabled when rolo is
directly bound off-loopback. No public production URL, tunnel, cross-origin API, CORS
allowlist, hosted secret, or external identity system is introduced.

## 4. Plugin discovery and package boundary

The host reads exactly one explicit plugin directory from a reviewed CLI/configuration
value. It must not recursively scan user directories, repositories, removable media, or
the network. The canonical package layout is:

```text
rolo-vis-<version>/
  rolo.plugin.json
  SHA256SUMS
  dist/client/index.html
  dist/client/assets/*
```

E23C upgrades the manifest to `rolo-plugin/v2`. The v2 manifest freezes:

- plugin identity, semantic version, kind, and relative entry path;
- delivery mode `device-local`, mount path `/workbench/`, and SPA fallback policy;
- API base path `/rolo-api` and required health-advertised API features;
- read-only authority and remote-access policy;
- checksum algorithm and checksum-manifest location.

The path resolver canonicalizes the configured directory and every served file. It
rejects absolute manifest entries, `..` traversal, paths outside the package root,
unexpected reparse/symbolic-link escapes, duplicate checksum entries, missing files,
case-colliding paths, and anything not listed by `SHA256SUMS`. A package checksum proves
transport integrity only; it does not create publisher authenticity or robot authority.

The current `rolo-plugin/v1` manifest remains a historical `v0.37.0` artifact. Strict
E23 hosting does not silently infer v2 integrity or delivery fields from v1.

## 5. Validation and compatibility

Startup validation is deterministic and bounded:

1. parse the manifest with unknown-field rejection;
2. require the supported manifest schema and plugin kind;
3. require `/workbench/` and `/rolo-api` route values exactly;
4. verify every checksum before serving any plugin byte;
5. verify the entry exists and is ordinary bounded content;
6. compare required API features with the server's health feature catalog.

A plugin failure never prevents the control-plane API from starting. The Workbench
route remains unavailable and rolo emits a bounded diagnostic containing only a stable
reason code, plugin ID/version when safely parsed, and corrective action. It must not
expose filesystem paths, raw exceptions, checksums, environment values, or file content.

Compatibility is feature-based. A semantic rolo version may be displayed, but it must
not substitute for required API feature negotiation. A frontend requiring an absent
feature is rejected before its `index.html` becomes available.

## 6. Static response and browser security

- `index.html` uses `Cache-Control: no-store` so an upgrade cannot strand stale entry
  metadata.
- checksum-named assets may use `public, max-age=31536000, immutable`.
- all other package files use `no-cache` unless the contract explicitly promotes them.
- responses set `X-Content-Type-Options: nosniff` and a restrictive, package-compatible
  Content Security Policy.
- MIME type comes from a small allowlist, not arbitrary registry or manifest values.
- directory listings, source maps, hidden files, manifests, checksum files, and source
  files are not browser routes.
- no response reflects a local path, authentication value, or arbitrary request header.

The Workbench remains read-only. Static hosting adds no teleoperation, shell command,
file browsing, upload, capture, recollection, replay, export, or verification authority.

## 7. Lifecycle and rollback

Installation and activation are separate. A package is unpacked into a versioned
directory, validated completely, and then selected by an atomic robot-local pointer.
Failed validation never changes the active version. Rollback selects the last validated
package without rebuilding it. Uninstall refuses to remove the active package until a
different validated version is selected or Workbench hosting is disabled.

E23 does not design an online updater. Package transport may be manual or part of a
later robot deployment workflow, but activation always uses the same local validator.

## 8. E23B approved implementation

The approved E23B implementation adds `rolo_workbench_plugin_dir`, the strict v2 manifest and
checksum validator, an in-process `/rolo-api` path adapter, and a bounded static
authority for `/workbench/`. Files are re-hashed immediately before each response so a
package changed after startup fails with `PACKAGE_CHANGED` instead of serving unchecked
bytes. API-only startup and all legacy root routes remain intact.

## 9. Delivery slices

### E23A: cross-repository contract design

- freeze topology, paths, manifest migration, validation, cache, security, and rollback
  boundaries;
- add machine-readable design assertions in rolo and paired consumer assertions in
  rolo-vis;
- add no runtime host, route advertisement, package, or public deployment.

### E23B: rolo plugin host

- add explicit plugin configuration and bounded validator;
- add the in-process route adapter and static file authority;
- preserve root API compatibility and API-only startup;
- cover loopback, proxy boundary, routing, traversal, checksum, feature, cache, and
  diagnostic behavior.

### E23C: rolo-vis device package

- remove Sites project binding and Sites-only worker/build/test flow;
- emit a relative-asset Vite build and deterministic `rolo-plugin/v2` package;
- keep `/rolo-api` same-origin and retain fail-closed live-data behavior.

### E23D: real-device validation and baseline

- validate against preserved `rolo-data` without modifying the source;
- cover Windows development plus Linux/robot installation, offline operation, trusted
  proxy routing, version mismatch, corruption, rollback, and Observation Bundle flow;
- promote the reviewed result as `v0.38.0` without creating a hosted site.

## 10. E23A acceptance decisions

E23A is ready for review when both repositories agree that:

1. rolo is the production host and Sites is not a production dependency.
2. UI and API share one robot-owned origin at `/workbench/` and `/rolo-api`.
3. Existing root API routes remain compatible.
4. Plugin discovery is explicit and filesystem serving is package-bounded.
5. `rolo-plugin/v2` and `SHA256SUMS` are mandatory before strict hosting.
6. Compatibility is feature-negotiated and fails before UI activation.
7. Remote browser access requires a trusted robot-owned reverse proxy.
8. Plugin failure cannot disable or weaken the control-plane API.
9. `v0.37.0` remains immutable and `v0.38.0` is the first robot-hosted baseline.
