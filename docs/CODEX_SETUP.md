# Codex executor setup in a uv workspace

rolo defaults to the `codex` Adapter Agent executor. rolo itself is installed only through a Git
checkout followed by `uv sync --frozen`; the commands below run from that checkout.

```text
.env configuration -> adapt run -> automatic dependency readiness -> Agent -> gate -> handoff
```

## Configuration

`.env` is optional. Code defaults already select Codex, automatic installation, and authentication
verification. Create a Git-ignored `.env` at the repository root only when persistent overrides are
needed; `.env.example` is a reference and does not need to be copied.

```dotenv
CODING_AGENT_EXECUTOR=codex
CODING_AGENT_PROVIDER=codex
CODING_AGENT_AUTO_INSTALL=true
CODING_AGENT_REQUIRE_AUTH=true
CODING_AGENT_EXECUTABLE=codex
CODING_AGENT_INSTALL_TIMEOUT_S=300
CODING_AGENT_INSTALL_HOME=
CODING_AGENT_HOME=
```

Empty home values use the current user's home and `~/.codex`. Only an allowlisted executor has an
installer. The Codex adapter uses the official Linux standalone installer documented at
<https://learn.chatgpt.com/docs/codex/cli>; provider Base URLs and model settings cannot change the
installer source.

## Configuration inspection and readiness

Inspect the effective secret-free configuration before running Adapt:

```bash
uv run robotctl adapt agent-config
```

`adapt run` checks readiness immediately before Agent execution and downloads Codex only when it is
missing and automatic installation is enabled. It writes a secret-free report under:

```text
.rolo/artifacts/coding-agent/dependency/latest.json
```

## First authentication

Authentication is a user gate and is not automated. On a headless robot, run device-code login as
the same operating-system user that owns the Git checkout:

```bash
codex login --device-auth
```

The next `adapt run` must observe `READY`. `AUTH_REQUIRED`, `INSTALL_REQUIRED`, `UNSUPPORTED`, or
`FAILED` blocks Agent execution. An explicitly configured API key can satisfy provider
authentication, but the key remains process-local and is never written to plans or artifacts.

## Execution

After discovery and optional Wiki correction, one command performs readiness, Agent execution, frozen
output capture, the independent conformance gate, and handoff publication:

```bash
uv run robotctl adapt run \
  --robot "$ROBOT_ID" \
  --scratch-root /path/outside/rolo
```

The executor uses the `workspace-write` sandbox. Dependency reports, commands, and run artifacts do
not contain API keys or cached authentication contents.

The isolated workspace also receives `ROLO_AGENT_TOOL`, a temporary read-only launcher for Rolo's
discovery queries. `ROLO_AGENT_DISCOVERY_ID` pins every query to the plan snapshot. The initial prompt
contains only a compact workset/coverage summary; Codex uses the launcher to retrieve one operation,
candidate, executable, launch record, dependency view, Wiki section, or bounded evidence snippet as
needed. The launcher disappears with the temporary workspace and is never published as adapter code.

## Files written for the current user

- `~/.local/bin/codex` is the conventional standalone executable location; the resolved path is
  recorded in the dependency report.
- `~/.codex/auth.json` may contain cached authentication when file-backed credential storage is
  used. Treat it as a password.
- `~/.codex/config.toml` contains optional Codex configuration when created.
- `.rolo/artifacts/coding-agent/dependency/latest.json` contains readiness metadata only.

The official authentication and credential-storage behavior is documented at
<https://learn.chatgpt.com/docs/auth>.
