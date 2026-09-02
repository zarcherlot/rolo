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

The current collector was run inside the target's ROS container with the v2
collector implementation. The resulting bundle is retained locally as the
ignored runtime artifact `.rolo/target-evidence-bundle.json` and covers
`hw`, `linux`, and `ros` in read-only mode.

- Collector: `collector-6c07d8c4c07844a0af54db60012d1810`
- Target fingerprint: `70c798f35729aec4e4ca083b561f37dd45cf70c8dcbecfbe7ecc1110bd1d74c9`
- Bundle payload SHA-256: `a38636533a77eb5222237494dc893bcef2de72aeb65d639a7eac5ca2ac4384f6`
- Independent verification: `PASSED` for payload hash, HMAC signature, target
  identity, and all three layers (`hw,linux,ros`).

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
