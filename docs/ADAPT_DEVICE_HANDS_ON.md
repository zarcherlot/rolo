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

export ROBOT_ID=your_robot_id
export ROLO_ARTIFACT_DIR=/var/lib/rolo/artifacts
export ROLO_OUTPUT_DIR=/var/lib/rolo/adapters
export CODING_AGENT_EXECUTABLE=codex
codex login
```

`ROLO_OUTPUT_DIR` must be outside the checkout. Source the same ROS setup and workspace overlays used
by the robot application before continuing. A BSP and URDF are optional. If a deployment-owned
read-only hardware provider exists, set `ROLO_HARDWARE_EVIDENCE_PROVIDER` to its executable path.

## 2. Collect target evidence

Use only paths that exist on this target; omit unavailable optional arguments:

```bash
uv run robotctl adapt discover run \
  --robot "$ROBOT_ID" \
  --urdf /path/to/robot.urdf \
  --build-root /path/to/build \
  --install-root /path/to/install \
  --doc-root /path/to/docs \
  --launch-root /path/to/launch \
  --source-root /path/to/source \
  --active-probe runtime-readonly
```

Expected: discovery is `SUCCEEDED` or `PARTIAL`, and at least one candidate intended for adaptation
has an observed ROS topic/service/action, device, or CLI route. `PARTIAL` is acceptable when the
missing facts are unrelated to that operation.

Review the bounded evidence without loading the whole source tree into the Agent:

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

## 3. Run the real Adapter Agent and gate

```bash
mkdir -p /var/tmp/rolo-adapt-work
uv run robotctl adapt run \
  --robot "$ROBOT_ID" \
  --scratch-root /var/tmp/rolo-adapt-work \
  --timeout 1800
```

The scratch project is isolated from the Rolo checkout. The Agent queries a bounded local snapshot,
uses the deterministic handoff preflight, returns only structured final-file payloads, and removes
its generated coding files before the workspace is deleted. A successful run must publish a
multi-file-capable bundle, Rolo-owned State Graph v2, full product Tool Catalog, conformance report,
gate report, handoff, and immutable external release.

## 4. Verify the published control surface

These checks are read-only and do **not** invoke a target operation:

```bash
uv run robotctl adapt status --robot "$ROBOT_ID"
uv run robotctl adapt operations summary --robot "$ROBOT_ID"
uv run robotctl adapt operations list --robot "$ROBOT_ID" --registration REGISTERED
uv run robotctl tool catalog --robot "$ROBOT_ID"
uv run robotctl state graph snapshot --robot "$ROBOT_ID"
uv run robotctl tool schema OPERATION --robot "$ROBOT_ID"
```

Accept the hands-on run when:

- Adapt status is `COMPLETE` and the independent gate is `PASSED`;
- the Registry count remains the complete product count rather than only target candidates;
- eligible bundle operations are `VERIFIED` and uniquely bound to `bundle:<id>#<entrypoint>`;
- deferred operations are `UNAVAILABLE`, never `DISCOVERED_UNVERIFIED` in the gated catalog;
- the State Graph is `robot-state-graph/v2`, owned by `ROLO_GATE`, and includes operation-to-route
  edges for every bundled operation;
- the release manifest is v2, lists every adapter file and a target fingerprint; and
- running the same discovery again with equivalent evidence leaves Adapt `COMPLETE`.

Stop before `robotctl tool invoke`. Executing a write and assessing success/failure, state closure,
correctness, reliability, performance, and safety belong to Diagnose/Verify and require the target's
normal safety process.

## 5. Evidence to return

Return the discovery ID, Adapt run/release ID, output from `adapt status` and `operations summary`,
the eligible/deferred operation lists, and any gate error. Do not return credentials, invocation
payloads, or private source archives.
