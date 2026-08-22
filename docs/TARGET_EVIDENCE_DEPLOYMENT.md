# Target Evidence Deployment

Rolo supports two explicit evidence deployment modes. Both produce the same signed,
target-bound `robot-target-evidence-bundle/v1`, and both permit only the deterministic
`hw`, `linux`, and `ros` read-only probes. Selecting a mode changes where those probes run; it
does not change verification or Operation eligibility.

## Security and attribution invariants

- The collector accepts only `mode=READ_ONLY` and the allowlisted `hw`, `linux`, and `ros`
  layers. It has no Operation invocation endpoint.
- Every request is bound to a robot ID, random nonce, and five-minute validity window.
- Every response is bound to the robot ID, collector ID, target host fingerprint, request nonce,
  collection time, layer set, payload digest, and HMAC-SHA256 integrity signature.
- Discovery rejects a bundle more than seven minutes after `collected_at`, even when the original
  request envelope is unavailable. Start Discovery immediately after collection; archived bundles
  are audit evidence, not reusable runtime evidence.
- The controller pins the collector ID and target host fingerprint during installation. Changed
  identity is rejected; discovery never performs trust-on-first-use.
- Repeating installation is idempotent only when robot, mode, collector identity/fingerprint,
  verification-secret digest, and transport paths are unchanged. Replacement or credential
  rotation requires an explicit re-enroll/rotate workflow; this baseline never overwrites a pin.
- Remote transport uses SSH with `BatchMode=yes`, `StrictHostKeyChecking=yes`, and an explicit
  `known_hosts` file. Host-key prompts and fallback to an unpinned host are forbidden.
- With a verified bundle, Discovery uses its target `hw`, `linux`, and `ros` probes and does not
  run those probes on the controller. Controller source trees are supporting static evidence only.
- The 32-byte collector secret must be readable only by the Rolo service identity and provisioned
  through a separate secure channel. Rotate both secret and descriptor after suspected exposure.

The target host fingerprint is a non-reversible SHA-256 identity derived on the target from its
stable machine identity, host name, OS, and architecture. Raw machine IDs are never transmitted.

## Mode A: Rolo runs on the target

Install the baseline wheel on the target and source the robot's ROS/workspace environment. Select
local evidence mode during initialization:

```bash
python -m pip install rolo-<version>-py3-none-any.whl
robotctl init --robot-id wheeltec --evidence-mode local
robotctl target-evidence collect --robot wheeltec --output ./wheeltec-evidence.json
robotctl adapt discover run \
  --robot wheeltec \
  --source-root /path/to/source \
  --build-root /path/to/build \
  --install-root /path/to/install \
  --active-probe runtime-readonly \
  --target-evidence-bundle ./wheeltec-evidence.json
```

Run the two controller commands back-to-back. If setup or transfer delays exceed the freshness
window, collect a new bundle instead of replaying the old one.

`init` creates and pins a target-local collector identity. Codex credentials are required only for
the full Agent chain, never for deterministic evidence collection.

## Mode B: controller plus target-side collector

Install the same wheel on both systems. The target needs only `target-evidence`; it needs no Codex,
OpenAI credentials, Agent workspace, or Tool Gateway access. The controller runs Discovery and the
complete `rolo-adapt-discovery`, `rolo-operation-mapping`, and `rolo-wiki-authoring` chain.

On the target:

```bash
robotctl target-evidence collector-init \
  --robot-id wheeltec \
  --config /etc/rolo/target-evidence-collector.json \
  --secret-file /etc/rolo/target-evidence-collector.key \
  --descriptor-out ./wheeltec-collector.json
```

Provision the descriptor through the configuration channel, the secret through a separate secrets
channel, and the SSH host key through an independently verified `known_hosts` file. Use a dedicated
SSH account and, where supported, restrict it to the fixed collector command.

On the controller:

```bash
robotctl init \
  --robot-id wheeltec \
  --evidence-mode remote \
  --collector-descriptor ./wheeltec-collector.json \
  --verification-secret /etc/rolo/secrets/wheeltec-collector.key \
  --ssh-target rolo-evidence@wheeltec-host \
  --known-hosts /etc/rolo/ssh/known_hosts \
  --collector-config /etc/rolo/target-evidence-collector.json

robotctl target-evidence collect --robot wheeltec --output ./wheeltec-evidence.json
robotctl adapt discover run \
  --robot wheeltec \
  --source-root /path/to/controller/source-copy \
  --active-probe runtime-readonly \
  --target-evidence-bundle ./wheeltec-evidence.json
```

Controller build/install roots must be target artifacts copied without mutation; never pass
controller-native binaries as target evidence. Explicit executable `--help` evidence must be
collected by a future target-side allowlisted Probe, not by executing target binaries remotely.

## Installable baseline contents

The wheel includes the three `rolo-` Agent skills and references under `rolo/bundled_skills`.
Runtime resolution uses an existing configured/check-out path first, then the bundled resource for
the three defaults. A missing explicit override fails instead of silently falling back.

- **target/local:** wheel; optionally Codex for the complete Agent chain;
- **target/remote:** wheel and the fixed collector command only;
- **controller/remote:** wheel, Codex CLI, pinned descriptor, collector secret, and SSH host key.

## Fail-closed troubleshooting

Never bypass these errors:

- `collector state belongs to a different target host`: re-enroll and review hardware replacement;
- collector or target fingerprint mismatch: stop and compare the physical target to deployment;
- payload hash or signature mismatch: discard the bundle and rotate credentials if needed;
- expired request: synchronize clocks and retry; do not expand the protocol window;
- SSH host-key failure: update the pin only after independent host verification.
