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

## Manage the user file

```bash
uv run robotctl config show
uv run robotctl config init
uv run robotctl config validate
```

`init` never overwrites an existing file. `show` and `validate` emit only the supported non-secret
settings. A complete template is checked in at [`../config/rolo.default.yaml`](../config/rolo.default.yaml).

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
