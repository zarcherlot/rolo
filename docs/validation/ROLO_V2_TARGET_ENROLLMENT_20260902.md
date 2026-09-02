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
- Bundle payload SHA-256: `e7490fef2d422386d9c2cd748dda7e60b17c08bb31ee9e2d29a0574e84146280`
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
