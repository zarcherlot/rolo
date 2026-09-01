<!-- status: active; authority: normative; owner: docs maintainers; last_reviewed: 2026-08-28 -->

# Target Evidence Deployment

Rolo supports two explicit evidence deployment modes. Both produce the same signed,
target-bound evidence bundle (`v2` for normal probe requests, `v3` when a bounded source
snapshot is requested), and both permit only the deterministic
`hw`, `linux`, and `ros` read-only probes. Selecting a mode changes where those probes run; it
does not change verification or Operation eligibility.

## Security and attribution invariants

- The collector accepts only `mode=READ_ONLY`, the allowlisted `hw`, `linux`, and `ros`
  layers, and optional bounded `--help` requests for executables pinned during enrollment. It has
  no Operation invocation endpoint.
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
  rotation uses the explicit staged workflow below; ordinary `configure` never overwrites a pin.
- Remote transport uses SSH with `BatchMode=yes`, `StrictHostKeyChecking=yes`, and an explicit
  `known_hosts` file. Deployment schema v3 pins the SHA-256 of that file and verifies it before
  every connection, so replacing contents at the same path fails closed and requires explicit
  re-enrollment. Host-key prompts and fallback to an unpinned host are forbidden. Use one dedicated
  `known_hosts` file per target so unrelated host rotations do not change its digest.
- With a verified bundle, Discovery uses its target `hw`, `linux`, and `ros` probes and does not
  run those probes on the controller. Controller source trees are supporting static evidence only.
- In remote mode, an Agent-requested second-round hardware, Linux, ROS, or executable-help Probe
  never falls back to the controller host. Rolo records a missing-evidence outcome and requires a
  newly collected signed target bundle.
- The 32-byte collector secret must be readable only by the Rolo service identity and provisioned
  through a separate secure channel. Rotate both secret and descriptor after suspected exposure.

The target host fingerprint is a non-reversible SHA-256 identity derived on the target from its
stable machine identity, host name, OS, and architecture. Raw machine IDs are never transmitted.

## Mode A: Rolo runs on the target

Clone the immutable source baseline on the target and install the locked environment. Rolo
automatically resolves and pins the robot's ROS/workspace setup when ROS is relevant; non-ROS
targets require no ROS setup. The product journey defaults to local signed evidence:

```bash
git clone --branch v0.1.0-rc.2 --depth 1 https://github.com/zarcherlot/rolo.git
cd rolo
uv sync --frozen
# Install the target distribution's bubblewrap package for the full Agent/gate journey.
uv run robotctl adapt start \
  --robot-id wheeltec \
  --project-root /path/to/robot-workspace \
  --urdf /path/to/robot.urdf
```

`adapt start` idempotently establishes the local collector, collects and verifies a fresh bundle,
and passes only its bound probes to Discovery. Repeating the command reuses the pinned collector but
always creates a new nonce and bundle. Use the granular `init`, `target-evidence collect`, and
`adapt discover run --target-evidence-bundle` commands only for recovery and diagnosis.

Codex credentials are required only for the full Agent chain, never for deterministic evidence
collection.

## Mode B: controller plus target-side collector

Install the locked Rolo collector runtime on the target and run `uv sync --frozen` there; the
target needs only `target-evidence` and does not need a controller-side ROS2 workspace, Codex,
OpenAI credentials, Agent workspace, or Tool Gateway access. The controller runs Discovery and the complete `rolo-adapt-discovery`,
`rolo-operation-mapping`, and `rolo-wiki-authoring` chain.

For a non-ROS application, omit ROS setup paths. When `--project-root` is supplied,
`collector-init` discovers declared console entrypoints and conventional robot/application binaries
without executing them, then pins their paths and digests. Use repeated `--allow-executable` options
to override that candidate set with an explicitly reviewed subset.
After signature verification, the controller deterministically derives `cli` Route Evidence from
successful target-side help records. A source manifest declaration with the same canonical entrypoint
name is also required before a product semantic rule can create an Operation candidate. Missing ROS
therefore does not block application discovery, while source-only or failed-help routes remain
unverified. See [NON_ROS_ADAPTATION.md](../adapt/NON_ROS_ADAPTATION.md) for the LeRobot example and exact
release boundary.

On the target:

```bash
uv run robotctl target-evidence collector-init \
  --robot-id wheeltec \
  --project-root /path/to/robot-workspace \
  --config /etc/rolo/target-evidence-collector.json \
  --secret-file /etc/rolo/target-evidence-collector.key \
  --descriptor-out ./wheeltec-collector.json \
  --allow-executable /opt/robot/bin/wheeltec_driver
```

`collector-init` sources nothing during enrollment, but resolves each approved base/overlay setup
path and pins its SHA-256 in collector descriptor v3. Every collection verifies those pins before
sourcing the files and signs the bootstrap evidence into the bundle. Use repeated `--ros-setup`
options when automatic selection is ambiguous. A changed setup file requires collector rotation and
explicit controller re-enrollment; it never falls back to an unpinned shell environment.

Provision the descriptor through the configuration channel, the secret through a separate secrets
channel, and the SSH host key through an independently verified `known_hosts` file. Use a dedicated
SSH account and, where supported, restrict it to the fixed collector command.

Rolo can generate the hardened `authorized_keys` line without modifying the target account:

```bash
robotctl target-evidence ssh-authorized-key \
  --public-key ./controller_ed25519.pub \
  --collector-executable /opt/rolo/.venv/bin/robotctl \
  --collector-config /etc/rolo/target-evidence-collector.json
```

Install the returned line for the dedicated account through the operator's provisioning system. It
uses an exact forced command and disables agent, port and X11 forwarding, PTY allocation, and user
startup files. The generator validates the public key and permits no shell metacharacters in either
Collector path. It deliberately does not create users, edit `sshd_config`, or copy secrets.

On the controller, the initial independent provisioning values can be supplied to the same product
journey. Subsequent runs may omit them and reuse the pinned deployment. A local `--project-root`
is optional: when omitted, the controller requests the target's bounded signed source snapshot,
materializes it only for the current Discovery, and deletes it on return:

```bash
uv run robotctl adapt start \
  --robot-id wheeltec \
  --evidence-mode remote \
  --collector-descriptor ./wheeltec-collector.json \
  --verification-secret /etc/rolo/secrets/wheeltec-collector.key \
  --ssh-target rolo-evidence@wheeltec-host \
  --known-hosts /etc/rolo/ssh/known_hosts \
  --ssh-port 22 \
  --ssh-identity-file /etc/rolo/ssh/wheeltec_ed25519 \
  --collector-executable /opt/rolo/.venv/bin/robotctl \
  --collector-config /etc/rolo/target-evidence-collector.json \
  --discover-only
```

The no-copy form is:

```bash
uv run rolo adapt ssh://rolo-evidence@wheeltec-host/path/to/robot-workspace \
  --robot-id wheeltec \
  --urdf /path/to/robot-workspace/src/simulations/robot/urdf/generated.urdf \
  --discover-only
```

`collector-init --project-root` pins the target source root in the collector descriptor. A source
request admits only bounded text files (with secret-like filename exclusions), signs each file and
the deterministic tree digest, and reports omitted files as `PARTIAL`. The snapshot is evidence,
not an execution authority; it never causes the target to run Codex or any source file.

`--collector-executable` pins the target-side CLI used by the fixed SSH command. Use the absolute
path from the target checkout's locked virtual environment when `robotctl` is not installed in the
SSH account's non-interactive `PATH`. Changing this path later requires explicit re-enrollment, just
like changing the collector config or transport identity.

`--ssh-port` defaults to 22. When `--ssh-identity-file` is supplied, Rolo requires private POSIX
permissions, pins its SHA-256, and invokes OpenSSH with `IdentitiesOnly=yes`. The transport also sets
bounded connect attempts, keepalives, no TTY, and no forwarding. Changing the port or identity later
requires explicit re-enrollment. Rolo retries only transient DNS/TCP timeout, reset, refused, or lost
connection failures, at most twice by default and within the original evidence timeout. It never
retries authentication, host-key, signature, invalid-bundle, or Collector rejection failures.

Before a full Journey, verify the complete pinned path with one disposable signed collection:

```bash
robotctl target-evidence preflight --robot wheeltec --timeout 30 --attempts 2
```

The command returns structured `READY` or `NOT_READY` JSON, including a stable error code, elapsed
time, Collector identity, target fingerprint, SSH port, and `known_hosts` digest. It does not persist
the disposable bundle. Normal `collect` and `adapt start` accept `--attempts` and
`--evidence-attempts`, respectively, from 1 through 3.

Remove `--discover-only` to continue through the Adapter Agent and release. Every executable in the
target collector descriptor's allowlist is requested automatically; the target still verifies its
exact path and digest before bounded `--help` execution. The release gate records whether its
scope is `STRUCTURAL_ONLY` or `TARGET_RUNTIME_READONLY`; the latter proves route identity/help
evidence only and never claims operation outcome or physical behavior.

Controller build/install roots must be target artifacts copied without mutation; never pass
controller-native binaries as target evidence. Each `--allow-executable` is resolved and hashed on
the target during collector enrollment. Later requests carry only its descriptor ID; the collector
refuses unknown IDs, changed hashes, non-files, or oversized binaries, then executes exactly
`[pinned_path, "--help"]` with no shell, no stdin, a reduced environment, a five-second timeout, and
a 200 KB output limit. The signed bundle contains the result and parsed usage, parameters, and
subcommands. Discovery merges that evidence into the Active report and never runs the target binary
on the controller. Because third-party programs can implement `--help` with side effects, operators
must allowlist only reviewed executables and may omit this optional evidence entirely.

### Refreshing an existing local collector

An existing local deployment keeps its pinned allowlist by design. If it was enrolled with only
one executable, run the explicit refresh command before Adapt; it discovers the project entrypoints,
stages a new collector/secret, and records a transition without overwriting the previous state:

```bash
ROLO_CONFIG_ROOT="${ROLO_CONFIG_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/rolo/config}"
DEPLOYMENT="$ROLO_CONFIG_ROOT/target-evidence/wheeltec.json"
CURRENT_COLLECTOR_ID="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["collector"]["collector_id"])' "$DEPLOYMENT")"
robotctl target-evidence collector-refresh \
  --robot wheeltec \
  --project-root /path/to/robot-workspace \
  --config-root "$ROLO_CONFIG_ROOT" \
  --expected-collector-id "$CURRENT_COLLECTOR_ID"
```

The command must return `COLLECTOR_REFRESHED`, list the newly pinned help executables, and emit a
transition path. It does not run `--help`; the next read-only collection performs the bounded probes.
Use `--allow-executable` repeatedly only when an explicitly reviewed subset is required. A stale
expected collector ID is a safety failure and must not be bypassed by deleting or editing the
deployment files.

## Collector rotation and target replacement

Rotation is intentionally a two-step handoff. The target first creates a parallel collector and
secret; it does not overwrite or remove the active collector:

```bash
robotctl target-evidence collector-rotate \
  --previous-config /etc/rolo/target-evidence-collector.json \
  --expected-collector-id collector-OLD \
  --project-root /path/to/robot-workspace \
  --config /etc/rolo/target-evidence-collector-next.json \
  --secret-file /etc/rolo/target-evidence-collector-next.key \
  --descriptor-out ./wheeltec-collector-next.json \
  --allow-executable /opt/robot/bin/wheeltec_driver
```

Transfer the new descriptor and secret through the same separate channels used for initial
enrollment. Then switch the controller pin explicitly. Remote mode also supplies the new target-side
collector config path:

```bash
robotctl target-evidence re-enroll \
  --robot wheeltec \
  --expected-collector-id collector-OLD \
  --reason "scheduled credential rotation" \
  --collector-descriptor ./wheeltec-collector-next.json \
  --verification-secret /etc/rolo/secrets/wheeltec-collector-next.key \
  --collector-config /etc/rolo/target-evidence-collector-next.json \
  --known-hosts /etc/rolo/ssh/known_hosts \
  --ssh-port 22 \
  --ssh-identity-file /etc/rolo/ssh/wheeltec_ed25519
```

For local mode, pass `--collector-state` with the new local state path. For physical target
replacement, initialize a new collector on the replacement host instead of using
`collector-rotate`, independently verify its host fingerprint, and run the same `re-enroll` command
against the expected old pin.

Re-enrollment fails when the expected old collector does not match, the descriptor and local state
disagree, or local signing and verification secrets differ. It writes a
`robot-target-evidence-transition/v1` record under the deployment's `transitions/` directory before
atomically replacing the active configuration. The record contains IDs, fingerprints, secret
digests, modes, the old and new collector executable pins, reason, and timestamp—never secret bytes.
Transition v2 also records the old and new Collector config, SSH target and port, `known_hosts`
digest, and identity-file digest. Existing deployment v1/v2 files are atomically migrated to v3 by
pinning the already-provisioned files on first load; all later in-place changes fail closed.
Collect and verify a fresh bundle using the
new pin before retiring the old collector through the operator's normal secrets-management process.
Rolo does not delete the old state or secret automatically. Rotation creates a fresh executable
allowlist, so repeat every still-approved `--allow-executable`; omitted entries are revoked.
It also creates fresh ROS setup pins, so repeat `--project-root` or every explicit `--ros-setup` in
source order.

## Source baseline contents

The Git checkout includes the three `rolo-` Agent skills under `skills/`. Runtime resolution uses an
existing configured checkout path first; a missing explicit override fails instead of silently
falling back.

- **target/local:** Git checkout plus `uv sync`; optionally Codex for the complete Agent chain;
- **target/remote:** Git checkout plus `uv sync` and the fixed collector command only;
- **controller/remote:** Git checkout plus `uv sync`, Codex CLI, pinned descriptor, collector secret,
  and SSH host key.

## Fail-closed troubleshooting

Never bypass these errors:

- `collector state belongs to a different target host`: re-enroll and review hardware replacement;
- collector or target fingerprint mismatch: stop and compare the physical target to deployment;
- payload hash or signature mismatch: discard the bundle and rotate credentials if needed;
- expired request: synchronize clocks and retry; do not expand the protocol window;
- executable help ID rejected or digest changed: review the target binary and rotate/re-enroll the
  collector allowlist; never substitute an unpinned path;
- SSH host-key failure: update the pin only after independent host verification.

Stable transport error codes include `SSH_CLIENT_UNAVAILABLE`, `SSH_DNS_FAILED`,
`SSH_CONNECTION_REFUSED`, `SSH_TIMEOUT`, `SSH_CONNECTION_LOST`, `SSH_AUTH_FAILED`,
`SSH_HOST_KEY_MISMATCH`, `SSH_HOST_KEY_PIN_CHANGED`, `SSH_IDENTITY_PIN_CHANGED`,
`SSH_OUTPUT_LIMIT`, `COLLECTOR_REJECTED`, and `COLLECTOR_INVALID_BUNDLE`.
