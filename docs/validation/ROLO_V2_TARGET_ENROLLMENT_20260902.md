<!-- status: frozen; authority: reference; owner: rolo maintainers; target: raspberrypi/192.168.10.167 -->

# Rolo v2 target enrollment record

## Result

The physical target `mentorpi` is enrolled for key-only Rolo access:

- SSH target: `pi@192.168.10.167:22`
- Workspace/container source: `/home/ubuntu/ros2_ws` in `MentorPi`
- Pinned host key: ECDSA SHA-256 `aFHbH0ko9ZzobJZEfeoAKyWjbYfP/zqmgvTwXMMKMnQ`
- Dedicated controller key fingerprint: `SHA256:hNgRHAhVT2MmNwDv21Ly4yzPhTynKMjFS+vzNDqjYXA`
- Host-key file digest: `2f4e2b4a6c8c616b07a27750c5c798ff9cdd4437d0f3d1930ec3802e9f8c09d2`
- Identity-file digest: `1b24e6da3bccd7aaca1ca4d648759bc715172d843775cce272ab8c219219595f`

The password was used once during enrollment to install the dedicated public
key. Subsequent Rolo transport uses `BatchMode=yes`, `IdentitiesOnly=yes`, a
pinned `known_hosts` file, and no password fallback.

## Current evidence and conformance

The current collector was run inside the target's Middleware container with the v2
collector implementation. The resulting bundle is retained locally as the
ignored runtime artifact `.rolo/config/target-evidence/mentorpi-bundle.json` and covers
hardware, OS, and Middleware in read-only mode.

- Collector: `collector-6c07d8c4c07844a0af54db60012d1810`
- Target fingerprint: `70c798f35729aec4e4ca083b561f37dd45cf70c8dcbecfbe7ecc1110bd1d74c9`
- Bundle payload SHA-256: `59b2163b2af173bb6a1096804d2ba830d53d6f4891ce915097c7aeb4c0cd87c2`
- Bundle observed at: `2026-09-02T07:54:31Z`
- Independent verification: `PASSED` for payload hash, HMAC signature, target
  identity, and all three current provider layers.

## Application gap loop

Using a fresh signed evidence snapshot on 2026-09-02, the first narrow
application loop was run without invoking any service, action, executable, or
actuator. The four bundles were generated and independently conformed:

- `startup`: `PASS` — lifecycle-ready Middleware routes were observed;
- `navigation`: `PASS` — motion, localization, range, and frame routes were observed;
- `manipulation`: `PASS` — arm/gripper control and joint-state routes were observed;
- `mapping`: `FAIL` / `NOT_FOUND` — no map, occupancy, SLAM, or costmap route was present
  in this snapshot, so Rolo retained a rejected bundle instead of claiming support.

The application contract is provider-neutral. These observations come from the
current target's Middleware provider; route presence is not a behavioral or
physical-safety certificate. The generated candidate, adapter bundle, and
conformance artifacts remain in the ignored local `.rolo/artifacts/application/`
tree.

## Application operation slice

The v1 application contract contains 137 operation IDs. Rolo v2 keeps those IDs
as the semantic identity, while using four small application families only as
discovery buckets. The first implementation slice covers 32 read-only operation
IDs on `mentorpi` (R0/R1); write operations remain deferred until a separate
mutation-safety contract exists.

Against the fresh bundle above:

- `23/32` operations produced a candidate and passed independent
  `ROUTE_BINDING` conformance;
- each passing adapter binds to an existing read-only native observation Tool
  (`native.middleware.graph.inspect` or `native.middleware.observe`) with a
  fixed mode and endpoint argument;
- `9/32` remained `NOT_FOUND`: `app.map.{inspect,list,export}`,
  `app.navigation.{costmap.inspect,path.inspect}`, and
  `app.gnss.{list,status,inspect,sample}`.

`ROUTE_BINDING` proves only that the operation's minimum runtime route was
observed and the adapter is safe to expose to an Agent. It does not yet prove
normalized operation output or physical behavior; that is the next conformance
stage after the Agent consumes the bound native Tool.

## First write canary

After the read-only operation slice, Rolo ran one human-confirmed write canary for
`app.base.stop`. The preflight used the fresh evidence bundle collected at
`2026-09-02T08:53:46Z` (`payload_sha256=d06f03e476f27e7e9a27fc035cb9c72e5ce4ff66745aa5e57bc2733a255492e1`)
and a separate `native.middleware.graph.inspect` call. It found `/cmd_vel` with
type `geometry_msgs/msg/Twist` and `Subscription count: 1`.

The fixed canary then sent exactly one zero-Twist `ros2 topic pub --once` request
through the pinned SSH connector. The target returned exit code `0`, and the
route was rechecked successfully. This is a `PASS` for request acceptance and
route continuity only; it is not proof of physical stop state or a safety
certificate. No navigation, actuator, arm, gripper, map, or parameter operation
was invoked.

The canary candidate and report are retained in the ignored runtime artifact
tree at `.rolo/artifacts/application/mentorpi/operations/app_base_stop/write-canary/`.

## Navigation write discovery

Using a fresh evidence bundle collected at `2026-09-02T09:02:03Z`
(`payload_sha256=9ed9b0872041061d409615550e342243e35ee874a4266328a07997dc0973b4f5`),
Rolo checked every v1 navigation write operation:

| operation | candidate | bundle | conformance | result |
|---|---|---|---|---|
| `app.navigation.start` | `DEFERRED` | `DEFERRED_WRITE` | `FAIL` | no navigation execution supervisor route |
| `app.navigation.pause` | `DEFERRED` | `DEFERRED_WRITE` | `FAIL` | no navigation execution supervisor route |
| `app.navigation.resume` | `DEFERRED` | `DEFERRED_WRITE` | `FAIL` | no navigation execution supervisor route |
| `app.navigation.cancel` | `DEFERRED` | `DEFERRED_WRITE` | `FAIL` | no navigation execution supervisor route |
| `app.navigation.stop` | `DEFERRED` | `DEFERRED_WRITE` | `FAIL` | no navigation execution supervisor route |
| `app.navigation.recover` | `DEFERRED` | `DEFERRED_WRITE` | `FAIL` | no navigation execution supervisor route |

The target graph exposed `/cmd_vel` and odometry routes, but no navigation action
or service server. Rolo therefore did not send a navigation goal, pause, cancel,
stop, resume, or recovery request. The previously validated `app.base.stop` zero-
Twist canary remains a separate base-control operation and is not counted as
navigation conformance.

The first bundle produced by the pre-v2 target installation was deliberately
not accepted: its declared hash did not match the v2 verifier after model
normalization. Rolo v2 now hashes the normalized `TargetEvidenceBundle` form
at collection time, so producer and verifier use exactly the same canonical
bytes.

## Local enrollment artifacts

- Profile: `.rolo/config/target-profiles/mentorpi.json`
- Deployment: `.rolo/config/target-evidence/mentorpi.json`
- Pinned host key: `.rolo/config/keys/raspberrypi_known_hosts`
- Dedicated identity: `.rolo/config/keys/raspberrypi_192_168_10_167`
- Verification secret: `.rolo/config/secrets/mentorpi-collector.key`

All of these runtime artifacts are ignored by Git. The private key and
verification secret must never be copied into source control or conversation
logs; revoke the public key on the target when this enrollment is retired.
