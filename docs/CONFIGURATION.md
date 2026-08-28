# Rolo configuration and optional ROS bootstrap

Rolo runs without a configuration file. Linux defaults follow XDG and remain outside the Git
checkout:

```text
~/.config/rolo/config.yaml           optional operator settings
~/.local/state/rolo/config/          identity and collector state
~/.local/share/rolo/artifacts/       Discovery, Wiki, Journey, Gate and audit artifacts
~/.local/share/rolo/output/          immutable Adapter releases
system temporary directory           deleted Agent workspaces
```

The runtime creates required directories for the current user. Environment variables and existing
`.env` deployments remain compatible. Precedence is CLI, environment, user YAML, `.env`, then
built-in defaults.

## Coding Agent selection

The `agent` section is deliberately split into two independent choices:

```yaml
agent:
  provider: anthropic       # model endpoint/vendor or an internal relay
  executor: claude-code    # local Agent product/harness adapter
  base_url: https://gateway.example/v1
  model: claude-sonnet
  api_key_env: ANTHROPIC_API_KEY
  executable: claude
  timeout_s: 1800
  auto_install: false
  require_auth: true
```

Rolo ships the Codex Adapt and downstream executors and exposes an executor SPI (`rolo.agent_provider`). Other
products can register an adapter through the `rolo.agent_executors` Python entry-point group;
plugins may also provide their own dependency adapter for installation and authentication. The
lifecycle, evidence, approval, and release contracts do not change. Rolo never persists the
secret itself in plans or artifacts: only the environment-variable name and a boolean
`api_key_configured` flag are recorded.

The interactive chat transport uses the same split through the harness registry. Codex is built in;
Claude Code or another product can register a `settings=...` harness factory through the
`rolo.harnesses` entry-point group. Harnesses receive the configured provider/model/base URL and
resolved key at runtime, stream output through the console callback, and do not receive lifecycle
authority. This lets a product plugin change the model transport without changing Rolo's
authorization or artifact contracts.

Executor factories receive the immutable `AdapterAgentConfig` as `agent_config`, so a plugin can
choose its own invocation protocol while preserving the same provider/model/key contract.

Downstream plugins additionally implement `execute_stage(task, workspace, on_output)` and return
only artifact references. The canonical `diagnose run`/`verify run` commands wrap that method with
Rolo authorization, stream persistence, output-root checks, and the stage handoff validator; a
plugin cannot publish `latest/handoff.json` directly through the CLI contract.

If `coding_agent_api_key` is omitted, Rolo resolves the key from the configured
`coding_agent_api_key_env` variable at runtime. This permits the same checked-in YAML to be
used with OpenAI, Anthropic, or a relay by changing only the provider-specific environment.

## Manage the user file

```bash
uv run robotctl config show
uv run robotctl config init
uv run robotctl config validate
```

`init` never overwrites an existing file. `show` and `validate` emit only the supported non-secret
settings. A complete template is checked in at [`../config/rolo.default.yaml`](../config/rolo.default.yaml).

## Agent-native rollout

The family-level Linux/ROS/HW observation catalog is disabled by default:

```yaml
agent_native:
  mode: off       # off | shadow | canary | active
  robot_ids: ""
  run_ids: ""
  max_calls: 64
  max_elapsed_s: 600
  max_result_bytes: 8000000
```

`shadow` enables bounded observations for comparison, while `canary` requires an exact robot or
run selector. Neither mode changes eligibility or release authority. `active` should only be used
after native parity and artifact/evidence review; writes, calibration, reset, actuator, power and
firmware operations remain Canonical.

## ROS setup resolution

Non-ROS projects need no ROS setup and continue with host, Application/CLI, protocol, process, and
device-interface evidence. When the target or project is ROS-relevant, before signed target evidence
collection local mode resolves setup files in this order:

1. explicitly configured `ros.setup_files`;
2. the single `/opt/ros/<distro>/setup.bash`, using inherited `ROS_DISTRO` when available;
3. `<project-root>/install/local_setup.bash`, or `setup.bash` when no local setup exists.

Rolo does not source `.bashrc`, `.profile`, or Agent-selected files. Multiple base distributions or
multiple project overlays are an error. Resolve ambiguity explicitly:

```yaml
schema_version: rolo-config/v1

ros:
  auto_source: true
  setup_files:
    - /opt/ros/humble/setup.bash
    - /home/robot/wheeltec_ws/install/local_setup.bash
  domain_id: "0"
  rmw_implementation: rmw_fastrtps_cpp
```

Setup scripts are executable code and remain an operator trust boundary. Collector enrollment pins
their resolved paths and SHA-256 digests. Collection verifies the pins, sources the files through
`bash --noprofile --norc`, admits only the bounded ROS/RMW and runtime path environment, and writes
the bootstrap record into the signed ROS probe. A changed or missing setup file fails closed.

Remote mode performs the same process inside the target collector. The controller never substitutes
its own ROS environment for failed target collection.
