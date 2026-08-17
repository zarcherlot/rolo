# Codex executor setup on a robot

rolo defaults to the `codex` Coding Agent executor. Its lifecycle is:

```text
deployment configuration -> automatic installation -> readiness verification -> build execution
```

## Deployment configuration

The bundle reads `coding_agent` from `configs/deployment/common.yaml`:

```yaml
coding_agent:
  executor: codex
  provider: codex
  auto_install: true
  require_auth: true
  executable: codex
  install_home: /var/lib/rolo
  home: /var/lib/rolo/codex
  install_timeout_s: 300
```

Only an allowlisted executor has an installer. The Codex adapter uses the official Linux standalone
installer documented at <https://learn.chatgpt.com/docs/codex/cli>. Provider Base URLs and model
configuration cannot change the installer URL.

During `install.sh`, rolo installs the missing executable as the `rolo` service user and calls:

```bash
/opt/rolo/venv/bin/robotctl build agent-prepare --skip-auth
```

This deployment check verifies installation and version without pretending that a user login is
complete. It writes a secret-free report to:

```text
/var/lib/rolo/artifacts/coding-agent/dependency/latest.json
```

## First authentication

Authentication is a user gate and is not automated. On a headless robot, use device-code login as
the same operating-system user that runs the Coding Agent:

```bash
CODEX_BIN="$(sudo -u rolo -H sh -lc 'command -v codex')"
sudo -u rolo -H env \
  HOME=/var/lib/rolo \
  CODEX_HOME=/var/lib/rolo/codex \
  "$CODEX_BIN" login --device-auth
```

Then verify the complete dependency gate:

```bash
sudo -u rolo -H env \
  HOME=/var/lib/rolo \
  CODEX_HOME=/var/lib/rolo/codex \
  ROLO_CONFIG_DIR=/etc/rolo \
  ROLO_ARTIFACT_DIR=/var/lib/rolo/artifacts \
  CODING_AGENT_INSTALL_HOME=/var/lib/rolo \
  CODING_AGENT_HOME=/var/lib/rolo/codex \
  /opt/rolo/venv/bin/robotctl build agent-prepare
```

Expected readiness is `READY`. `AUTH_REQUIRED`, `INSTALL_REQUIRED`, `UNSUPPORTED`, or `FAILED`
blocks build execution.

## Execution

`build execute` always repeats installation and readiness verification before starting
`codex exec`:

```bash
sudo -u rolo -H env \
  HOME=/var/lib/rolo \
  CODEX_HOME=/var/lib/rolo/codex \
  ROLO_CONFIG_DIR=/etc/rolo \
  ROLO_ARTIFACT_DIR=/var/lib/rolo/artifacts \
  CODING_AGENT_INSTALL_HOME=/var/lib/rolo \
  CODING_AGENT_HOME=/var/lib/rolo/codex \
  /opt/rolo/venv/bin/robotctl build execute \
    --robot my_robot_01 \
    --workspace /opt/robot-application
```

The executor uses the `workspace-write` sandbox. Dependency reports, commands, and run artifacts do
not contain API keys or cached authentication contents.

## Files written on the robot

- `/var/lib/rolo/.local/bin/codex` is the conventional standalone executable location; the actual
  resolved path is recorded in the dependency report.
- `/var/lib/rolo/codex/auth.json` may contain cached authentication when file-backed credential
  storage is used. Treat it as a password.
- `/var/lib/rolo/codex/config.toml` contains optional Codex configuration when created.
- `/var/lib/rolo/artifacts/coding-agent/dependency/latest.json` contains only readiness metadata.

The official authentication and credential-storage behavior is documented at
<https://learn.chatgpt.com/docs/auth>.
