# Adapt real-device hands-on

This procedure starts where repository validation ends. Run it **on the target robot host** (or over
SSH with the target ROS/device environment sourced). Adapt verifies contract/binding integrity and
that an equivalent route exists. It does not execute write operations or claim behavior, reliability,
performance, or safety.

## 1. Prepare the target

```bash
git clone https://github.com/zarcherlot/rolo.git
cd rolo
uv sync --frozen

# Debian/Ubuntu 示例；其他发行版安装其 bubblewrap 软件包
sudo apt-get install bubblewrap

export ROBOT_ID=your_robot_id
export ROLO_ARTIFACT_DIR=/var/lib/rolo/artifacts
export ROLO_OUTPUT_DIR=/var/lib/rolo/adapters
export CODING_AGENT_EXECUTABLE=codex
codex login
```

`ROLO_OUTPUT_DIR` must be outside the checkout. Source the same ROS setup and workspace overlays used
by the robot application before continuing. A BSP and URDF are optional. If a deployment-owned
read-only hardware provider exists, set `ROLO_HARDWARE_EVIDENCE_PROVIDER` to its executable path.
Discovery captures the schema-defined, allowlisted non-secret Runtime Context from this shell. The gated release
reuses that context for adapter `describe` and invocation; changing the ROS domain, RMW selection or
an admitted overlay path requires rediscovery and a new release.

On Linux, Rolo automatically selects `scripts/rolo-adapter-sandbox` when `bubblewrap` is available.
Full Adapt runs the launcher's `--self-test` and fails before Discovery if the launcher is absent or the
kernel cannot create the required namespaces. The bundled launcher exposes an empty sandbox HOME/TMP,
not the host directories. A deployment-owned launcher may
override it through `ROLO_ADAPTER_SANDBOX_LAUNCHER`. Keep sandbox networking isolated for Adapt
`describe`; configure host ROS/DDS networking only when a later, authorized runtime invocation requires it.

## 2. Run the complete signed Adapt journey

Use only paths that exist on this target; `--urdf` is optional. Local mode is the default and needs
no separate `init`, evidence collection, or Discovery command:

```bash
uv run robotctl adapt start \
  --robot-id "$ROBOT_ID" \
  --project-root /path/to/robot-workspace \
  --urdf /path/to/robot.urdf \
  --scratch-root /var/tmp/rolo-adapt-work \
  --timeout 1800
```

The command idempotently enrolls the robot and local collector, creates a fresh signed target
evidence bundle, binds its Hardware/Linux/ROS probes to Discovery, runs the three heuristic Agent
skills, generates the Wiki, starts the real Adapter Agent, freezes its output, and publishes only
after the independent gate passes. Its `robot-adapt-journey/v2` output must contain non-empty
`target_evidence.collector_id`, target fingerprint, bundle digest, gate, handoff, and release ID.

For a controller plus target collector, complete the independent pinning described in
[`TARGET_EVIDENCE_DEPLOYMENT.md`](TARGET_EVIDENCE_DEPLOYMENT.md), then run the same command with
`--evidence-mode remote`. Remote collection failures never fall back to controller probes.

Expected: discovery is `SUCCEEDED` or `PARTIAL`, and at least one candidate intended for adaptation
has an observed ROS topic/service/action, device, or CLI route. `PARTIAL` is acceptable when the
missing facts are unrelated to that operation. A successful full journey reports `COMPLETE` and a
passed gate.

If a manual `ros2 node list` succeeds but discovery reports the ROS probe unavailable, retain the
new run's `ros.json`. Its `command_diagnostics` distinguishes the inherited-shell attempt from the
clean base-setup retry and includes bounded exit-code/stderr evidence; do not interpret this state as
an empty ROS graph.

If the journey returns `BLOCKED`, review the persisted bounded evidence without loading the whole
source tree into the Agent:

```bash
uv run robotctl adapt discover review --robot "$ROBOT_ID"
uv run robotctl adapt operations summary --robot "$ROBOT_ID"
uv run robotctl adapt operations list --robot "$ROBOT_ID" --applicability OBSERVED
uv run robotctl adapt run --robot "$ROBOT_ID" --dry-run
```

The dry run must be `REQUIRES_CODING` and list a non-empty `eligible_operations`. Every
`deferred_operations` entry should have one of the documented stable reasons. If the plan is
`BLOCKED`, inspect the candidate and its focused evidence before changing code:

```bash
uv run robotctl adapt candidates inspect OPERATION --robot "$ROBOT_ID"
uv run robotctl adapt operations inspect OPERATION --robot "$ROBOT_ID"
```

The scratch project is isolated from the Rolo checkout. The Agent queries a bounded local snapshot,
uses the deterministic handoff preflight, returns only structured final-file payloads, and removes
its generated coding files before the workspace is deleted. A successful run publishes a
multi-file-capable bundle, Rolo-owned State Graph v2, full product Tool Catalog, conformance report,
gate report, handoff, and immutable external release.

## 3. Verify the published control surface

These checks are read-only and do **not** invoke a target operation:

```bash
uv run robotctl adapt status --robot "$ROBOT_ID"
uv run robotctl adapt operations summary --robot "$ROBOT_ID"
uv run robotctl adapt operations list --robot "$ROBOT_ID" --registration REGISTERED
uv run robotctl tool catalog --robot "$ROBOT_ID"
uv run robotctl state graph snapshot --robot "$ROBOT_ID"
uv run robotctl tool schema OPERATION --robot "$ROBOT_ID"
uv run robotctl adapt acceptance-pack --robot "$ROBOT_ID" \
  --output ./rolo-adapt-acceptance.json
```

Accept the hands-on run when:

- Adapt status is `COMPLETE` and the independent gate is `PASSED`;
- the Registry count remains the complete product count rather than only target candidates;
- eligible bundle operations are `VERIFIED` and uniquely bound to `bundle:<id>#<entrypoint>`;
- deferred operations are `UNAVAILABLE`, never `DISCOVERED_UNVERIFIED` in the gated catalog;
- the State Graph is `robot-state-graph/v2`, owned by `ROLO_GATE`, and includes operation-to-route
  edges for every bundled operation;
- the release manifest is v2, lists every adapter file, the admitted runtime context and an
  operation-scoped target fingerprint; and
- candidate activation has validated the complete release and matching passed gate before replacing
  the atomic current pointer; and
- running the same discovery again with equivalent evidence leaves Adapt `COMPLETE`.

Stop before `robotctl tool invoke`. Executing a write and assessing success/failure, state closure,
correctness, reliability, performance, and safety belong to Diagnose/Verify and require the target's
normal safety process.

## 4. Evidence to return

Return `rolo-adapt-acceptance.json` and its command-reported SHA-256. It contains the source revision,
Registry identity/count, target evidence digest, discovery status, eligible/deferred Operations and
validated gate/release identity, but no credentials, invocation payloads, private source archives or
raw probe payloads. If pack creation is unavailable during recovery, return the discovery ID, Adapt
run/release ID, `adapt status`, `operations summary`, eligible/deferred lists and any gate error.
