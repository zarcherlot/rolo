"""Stage 1 identity-free bundle builder for the combined build stage."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rolo import __version__
from rolo.core.config import load_yaml
from rolo.stages.build.enrollment import PROFILE_ID_PATTERN, list_profiles

ARCH_ALIASES = {"arm64": "aarch64"}
COMMON_DEPLOYMENT_KEYS = ("install_root", "config_root", "artifact_root", "service_user")
SAFE_AGENT_ID = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
SAFE_POSIX_VALUE = re.compile(r"^[A-Za-z0-9_./-]+$")


@dataclass(frozen=True)
class BundleResult:
    bundle: Path
    profile_ids: tuple[str, ...]
    target_arch: str
    version: str
    sha256: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require_string(config: dict[str, Any], key: str) -> str:
    value = config.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"deployment.{key} must be a non-empty string")
    return value


def _require_bool(config: dict[str, Any], key: str) -> bool:
    value = config.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"deployment.coding_agent.{key} must be a boolean")
    return value


def _coding_agent_config(deployment: dict[str, Any]) -> dict[str, Any]:
    value = deployment.get("coding_agent")
    if not isinstance(value, dict):
        raise ValueError("deployment.coding_agent must be an object")
    executor = _require_string(value, "executor")
    provider = _require_string(value, "provider")
    executable = _require_string(value, "executable")
    install_home = _require_string(value, "install_home")
    home = _require_string(value, "home")
    if executor != "codex":
        raise ValueError(f"unsupported deployment coding_agent.executor: {executor}")
    if not SAFE_AGENT_ID.fullmatch(provider):
        raise ValueError("deployment.coding_agent.provider contains unsafe characters")
    if not SAFE_POSIX_VALUE.fullmatch(executable) or ".." in Path(executable).parts:
        raise ValueError("deployment.coding_agent.executable contains unsafe path characters")
    if (
        not install_home.startswith("/")
        or not SAFE_POSIX_VALUE.fullmatch(install_home)
        or ".." in Path(install_home).parts
    ):
        raise ValueError("deployment.coding_agent.install_home must be a safe absolute path")
    if (
        not home.startswith("/")
        or not SAFE_POSIX_VALUE.fullmatch(home)
        or ".." in Path(home).parts
    ):
        raise ValueError("deployment.coding_agent.home must be a safe absolute path")
    timeout = value.get("install_timeout_s")
    if not isinstance(timeout, int) or timeout < 1:
        raise ValueError("deployment.coding_agent.install_timeout_s must be a positive integer")
    return {
        "executor": executor,
        "provider": provider,
        "auto_install": _require_bool(value, "auto_install"),
        "require_auth": _require_bool(value, "require_auth"),
        "executable": executable,
        "install_home": install_home,
        "home": home,
        "install_timeout_s": timeout,
    }


def _resolve_source_revision(project_root: Path, configured: str) -> str:
    if configured != "auto_git":
        return configured
    try:
        result = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unversioned-workspace"
    return result.stdout.strip() if result.returncode == 0 else "unversioned-workspace"


def _service_unit(
    *,
    description: str,
    service_user: str,
    install_root: str,
    config_root: str,
    artifact_root: str,
    command: str,
    robot_identity: bool = False,
    after: Sequence[str] = (),
    wants: Sequence[str] = (),
    requires: Sequence[str] = (),
) -> str:
    identity_env = f"EnvironmentFile={config_root}/robot-identity.env\n" if robot_identity else ""
    after_units = " ".join(("network-online.target", *after))
    wants_units = " ".join(("network-online.target", *wants))
    requires_line = f"Requires={' '.join(requires)}\n" if requires else ""
    return f"""[Unit]
Description={description}
After={after_units}
Wants={wants_units}
{requires_line}

[Service]
Type=simple
User={service_user}
Group={service_user}
WorkingDirectory={install_root}
EnvironmentFile=-{config_root}/rolo.env
{identity_env}Environment=ROLO_CONFIG_DIR={config_root}
Environment=ROLO_ARTIFACT_DIR={artifact_root}
ExecStart={install_root}/venv/bin/robotctl {command}
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
"""


def _discovery_service_unit(
    *,
    service_user: str,
    install_root: str,
    config_root: str,
    artifact_root: str,
    bootstrap_url: str,
) -> str:
    exec_start_pre = (
        f"{install_root}/venv/bin/robotctl bootstrap-wait --robot ${{ROBOT_ID}} "
        f"--url {bootstrap_url} --timeout 15"
    )
    exec_start = (
        f"{install_root}/venv/bin/robotctl discover run --robot ${{ROBOT_ID}} "
        "--source-root ${ROBOT_DISCOVERY_SOURCE_ROOT}"
    )
    return f"""[Unit]
Description=rolo hardware and software discovery
After=network-online.target rolo-bootstrap-agentd.service
Wants=network-online.target
Requires=rolo-bootstrap-agentd.service

[Service]
Type=oneshot
User={service_user}
Group={service_user}
WorkingDirectory={install_root}
EnvironmentFile=-{config_root}/rolo.env
EnvironmentFile={config_root}/robot-identity.env
Environment=ROLO_CONFIG_DIR={config_root}
Environment=ROLO_ARTIFACT_DIR={artifact_root}
ExecStartPre={exec_start_pre}
ExecStart={exec_start}
RemainAfterExit=true
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
"""


def _installer(
    *,
    profile_ids: Sequence[str],
    target_arch: str,
    service_user: str,
    install_root: str,
    config_root: str,
    artifact_root: str,
    coding_agent: dict[str, Any],
) -> str:
    allowed_profiles = " ".join(profile_ids)
    profile_choices = "|".join(profile_ids)
    kernel_arch = ARCH_ALIASES[target_arch]
    auto_install = str(coding_agent["auto_install"]).lower()
    require_auth = str(coding_agent["require_auth"]).lower()
    return f"""#!/usr/bin/env bash
set -euo pipefail

BUNDLE_ROOT="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
ROBOT_ID="${{1:-}}"
PROFILE_ID="${{2:-}}"
CONFIRM="${{3:-}}"
ALLOWED_PROFILES=" {allowed_profiles} "
EXPECTED_ARCH="{kernel_arch}"
ACTUAL_ARCH="$(uname -m)"

usage() {{
  echo "Usage: sudo bash install.sh <robot_id> <{profile_choices}> --confirm-safety-profile" >&2
}}
if [[ ! "$ROBOT_ID" =~ ^[a-z][a-z0-9_-]{{2,63}}$ ]]; then
  usage
  exit 1
fi
if [[ "$ALLOWED_PROFILES" != *" $PROFILE_ID "* ]]; then
  usage
  exit 1
fi
if [[ "$CONFIRM" != "--confirm-safety-profile" ]]; then
  echo "Explicit confirmation of physical geometry and hard motion bounds is required" >&2
  usage
  exit 1
fi
if [[ "$ACTUAL_ARCH" != "$EXPECTED_ARCH" ]]; then
  echo "Architecture mismatch: bundle expects $EXPECTED_ARCH, host reports $ACTUAL_ARCH" >&2
  exit 2
fi
if [[ ! -r /etc/os-release ]]; then
  echo "Cannot verify Ubuntu release" >&2
  exit 2
fi
. /etc/os-release
if [[ "${{ID:-}}" != "ubuntu" ]]; then
  echo "Platform mismatch: Ubuntu is required" >&2
  exit 2
fi
case "${{VERSION_ID:-}}" in
  20.04|22.04|24.04) ;;
  *)
  echo "Platform mismatch: Ubuntu 20.04, 22.04, or 24.04 is required" >&2
  exit 2
  ;;
esac
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3.10 or newer is required" >&2
  exit 2
fi
python3 - <<'PY'
import sys

if sys.version_info[:2] < (3, 10):
    raise SystemExit("Python 3.10 or newer is required")
PY
if ! python3 -m venv --help >/dev/null 2>&1; then
  echo "The Python venv module is required" >&2
  exit 2
fi
if ! compgen -G "/opt/ros/*/setup.bash" >/dev/null; then
  echo "ROS 2 is missing; continuing with bootstrap discovery in DEGRADED mode" >&2
fi

python3 - "$BUNDLE_ROOT" <<'PY'
import hashlib
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
for relative, expected in manifest["files"].items():
    actual = hashlib.sha256((root / relative).read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit(f"Checksum mismatch: {{relative}}")
print(f"Verified {{len(manifest['files'])}} bundle files")
PY

if [[ "${{EUID}}" -ne 0 ]]; then
  echo "Run this installer as root" >&2
  exit 3
fi

SERVICE_USER="{service_user}"
INSTALL_ROOT="{install_root}"
CONFIG_ROOT="{config_root}"
ARTIFACT_ROOT="{artifact_root}"
SERVICE_HOME="{coding_agent['install_home']}"
CODEX_HOME="{coding_agent['home']}"

if ! id "$SERVICE_USER" >/dev/null 2>&1; then
  useradd --system --home-dir "$SERVICE_HOME" --shell /usr/sbin/nologin "$SERVICE_USER"
fi

install -d -o root -g root -m 0755 \
  "$INSTALL_ROOT" "$CONFIG_ROOT" "$CONFIG_ROOT/robots" \
  "$CONFIG_ROOT/profiles" "$CONFIG_ROOT/platforms"
install -d -o "$SERVICE_USER" -g "$SERVICE_USER" -m 0750 \
  "$SERVICE_HOME" "$ARTIFACT_ROOT"
install -d -o "$SERVICE_USER" -g "$SERVICE_USER" -m 0700 "$CODEX_HOME"
python3 -m venv "$INSTALL_ROOT/venv"
"$INSTALL_ROOT/venv/bin/python" -m pip install --upgrade pip
"$INSTALL_ROOT/venv/bin/python" -m pip install "$BUNDLE_ROOT"/wheels/rolo-*.whl

install -m 0644 "$BUNDLE_ROOT/config/robot_use.yaml" "$CONFIG_ROOT/robot_use.yaml"
install -m 0644 "$BUNDLE_ROOT/config/discovery.yaml" "$CONFIG_ROOT/discovery.yaml"
install -m 0644 "$BUNDLE_ROOT/config/deployment.yaml" "$CONFIG_ROOT/deployment.yaml"
install -m 0644 "$BUNDLE_ROOT/config/platforms/arm64.yaml" "$CONFIG_ROOT/platforms/arm64.yaml"
install -m 0644 "$BUNDLE_ROOT"/profiles/*.yaml "$CONFIG_ROOT/profiles/"

ROLO_CONFIG_DIR="$CONFIG_ROOT" \
  "$INSTALL_ROOT/venv/bin/robotctl" enroll init \
  --robot-id "$ROBOT_ID" \
  --profile "$PROFILE_ID" \
  --profile-root "$CONFIG_ROOT/profiles" \
  --confirm-safety-profile

printf 'ROBOT_ID=%s\nPROFILE_ID=%s\n' "$ROBOT_ID" "$PROFILE_ID" \
  > "$CONFIG_ROOT/robot-identity.env"
chmod 0644 "$CONFIG_ROOT/robot-identity.env"
install -d -m 0755 "$INSTALL_ROOT/schemas"
install -m 0644 "$BUNDLE_ROOT"/schemas/*.json "$INSTALL_ROOT/schemas/"

if [[ ! -e "$CONFIG_ROOT/rolo.env" ]]; then
  install -m 0600 "$BUNDLE_ROOT/config/rolo.env.example" "$CONFIG_ROOT/rolo.env"
fi

if [[ "{auto_install}" == "true" ]]; then
  runuser -u "$SERVICE_USER" -- env \
    HOME="$SERVICE_HOME" \
    CODEX_HOME="$CODEX_HOME" \
    ROLO_CONFIG_DIR="$CONFIG_ROOT" \
    ROLO_ARTIFACT_DIR="$ARTIFACT_ROOT" \
    CODING_AGENT_EXECUTOR="{coding_agent['executor']}" \
    CODING_AGENT_PROVIDER="{coding_agent['provider']}" \
    CODING_AGENT_EXECUTABLE="{coding_agent['executable']}" \
    CODING_AGENT_AUTO_INSTALL="true" \
    CODING_AGENT_REQUIRE_AUTH="{require_auth}" \
    CODING_AGENT_INSTALL_TIMEOUT_S="{coding_agent['install_timeout_s']}" \
    CODING_AGENT_INSTALL_HOME="$SERVICE_HOME" \
    CODING_AGENT_HOME="$CODEX_HOME" \
    "$INSTALL_ROOT/venv/bin/robotctl" build agent-prepare --skip-auth
fi

install -m 0644 "$BUNDLE_ROOT/systemd/rolo-bootstrap-agentd.service" /etc/systemd/system/
install -m 0644 "$BUNDLE_ROOT/systemd/rolo-agentd.service" /etc/systemd/system/
install -m 0644 "$BUNDLE_ROOT/systemd/rolo-control-plane.service" /etc/systemd/system/
install -m 0644 "$BUNDLE_ROOT/systemd/rolo-discovery.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable rolo-bootstrap-agentd.service rolo-discovery.service
systemctl enable rolo-agentd.service rolo-control-plane.service
systemctl start rolo-agentd.service rolo-control-plane.service

echo "Installed rolo {__version__} for $ROBOT_ID with profile $PROFILE_ID"
echo "Startup order: bootstrap-agentd -> discovery -> agentd"
echo "Discovery must verify bindings and calibration before motion tools become AVAILABLE"
"""


def _bundle_readme(
    *, profile_ids: Sequence[str], target_arch: str, supported_compute: Sequence[str]
) -> str:
    choices = "|".join(profile_ids)
    return f"""# rolo universal ARM deployment bundle

- Product version: `{__version__}`
- Platform baseline: ARM64 + Ubuntu 20.04/22.04/24.04 + auto-discovered ROS 2
- Supported compute: {", ".join(supported_compute)}
- Robot identities: assigned dynamically at installation
- Structure/sensor profiles: `{", ".join(profile_ids)}`
- Default network exposure: loopback only
- Startup order: `bootstrap-agentd -> discovery -> agentd`

Install the same archive on any compatible robot. Choose the profile from physical structure and
sensors, not from SoC:

```bash
unzip rolo-{__version__}-{target_arch}.zip
cd rolo-{__version__}-{target_arch}
sudo bash install.sh my_robot_01 <{choices}> --confirm-safety-profile
```

The installer creates `/etc/rolo/robots/my_robot_01.yaml`; no robot identity is compiled into
the package. Enrollment refuses to replace a different existing identity. Newly inferred bindings
remain unverified until adapter conformance and calibration gates pass.

This MVP resolves Python dependencies from the configured package index. Production offline
releases must include an ARM64 wheelhouse. SoC-specific BSP and drivers remain behind canonical
adapters and are not implemented by the mock profile templates.
"""


def build_compatible_bundle(
    *,
    wheel: Path,
    project_root: Path = Path("."),
    output_dir: Path = Path("dist/release"),
) -> BundleResult:
    project_root = project_root.resolve()
    wheel = wheel.resolve()
    if not wheel.is_file() or wheel.suffix != ".whl":
        raise ValueError(f"wheel does not exist or is not a .whl file: {wheel}")

    robot_use_path = project_root / "configs" / "robot_use.yaml"
    discovery_config_path = project_root / "configs" / "discovery.yaml"
    deployment_path = project_root / "configs" / "deployment" / "common.yaml"
    platform_config_path = project_root / "configs" / "platforms" / "arm64.yaml"
    profile_root = project_root / "configs" / "profiles"
    schema_dir = project_root / "schemas"
    required = (
        robot_use_path,
        discovery_config_path,
        deployment_path,
        platform_config_path,
        profile_root,
        schema_dir,
    )
    if any(not path.exists() for path in required):
        raise ValueError("bundle config, profile, or schema input is missing")

    deployment = load_yaml(deployment_path)
    coding_agent = _coding_agent_config(deployment)
    platform_config = load_yaml(platform_config_path)
    target_arch = _require_string(deployment, "target_arch")
    if target_arch not in ARCH_ALIASES:
        raise ValueError(f"unsupported target_arch: {target_arch}; only ARM64 is supported")
    if platform_config.get("architecture") != target_arch:
        raise ValueError("platform manifest architecture does not match deployment")

    profile_descriptors = list_profiles(profile_root)
    profile_ids = tuple(item["profile_id"] for item in profile_descriptors)
    if not profile_ids:
        raise ValueError("at least one enrollment profile is required")
    for profile_id in profile_ids:
        if not PROFILE_ID_PATTERN.fullmatch(profile_id):
            raise ValueError(f"invalid profile_id: {profile_id}")
        template = load_yaml(profile_root / f"{profile_id}.yaml")
        if template.get("platform", {}).get("architecture") != target_arch:
            raise ValueError(f"target_arch mismatch in profile {profile_id}")

    compute_entries = platform_config.get("supported_compute", [])
    if not isinstance(compute_entries, list) or not compute_entries:
        raise ValueError("platform supported_compute must be a non-empty list")
    supported_compute_ids = [entry["id"] for entry in compute_entries]
    supported_compute_names = [entry["name"] for entry in compute_entries]
    common_values = {key: _require_string(deployment, key) for key in COMMON_DEPLOYMENT_KEYS}
    source_revision = _resolve_source_revision(
        project_root, _require_string(deployment, "source_revision")
    )
    platform_baseline = deployment.get("platform_baseline")
    install_root = common_values["install_root"]
    config_root = common_values["config_root"]
    artifact_root = common_values["artifact_root"]
    service_user = common_values["service_user"]
    services = deployment.get("services", {})
    control = services.get("control_plane", {})
    bootstrap_agentd = services.get("bootstrap_agentd", {})
    agentd = services.get("agentd", {})
    bundle_name = f"rolo-{__version__}-{target_arch}"
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / f"{bundle_name}.zip"

    with tempfile.TemporaryDirectory(prefix="rolo-bundle-") as temporary:
        root = Path(temporary) / bundle_name
        for relative in ("wheels", "config", "profiles", "schemas", "systemd"):
            (root / relative).mkdir(parents=True)
        (root / "config" / "platforms").mkdir()

        shutil.copy2(wheel, root / "wheels" / wheel.name)
        shutil.copy2(robot_use_path, root / "config" / "robot_use.yaml")
        shutil.copy2(discovery_config_path, root / "config" / "discovery.yaml")
        shutil.copy2(deployment_path, root / "config" / "deployment.yaml")
        shutil.copy2(platform_config_path, root / "config" / "platforms" / "arm64.yaml")
        for profile in sorted(profile_root.glob("*.yaml")):
            shutil.copy2(profile, root / "profiles" / profile.name)
        for schema in sorted(schema_dir.glob("*.json")):
            shutil.copy2(schema, root / "schemas" / schema.name)

        env_text = f"""ROLO_ENV=production
ROLO_CONFIG_DIR={config_root}
ROLO_ARTIFACT_DIR={artifact_root}
ROLO_HOST={control.get('host', '127.0.0.1')}
ROLO_PORT={control.get('port', 8080)}
ROBOT_DISCOVERY_SOURCE_ROOT=/opt/robot-application
CODING_AGENT_PROVIDER={coding_agent['provider']}
CODING_AGENT_EXECUTOR={coding_agent['executor']}
CODING_AGENT_BASE_URL=
CODING_AGENT_API_KEY=
CODING_AGENT_MODEL=
CODING_AGENT_EXECUTABLE={coding_agent['executable']}
CODING_AGENT_TIMEOUT_S=1800
CODING_AGENT_AUTO_INSTALL={str(coding_agent['auto_install']).lower()}
CODING_AGENT_REQUIRE_AUTH={str(coding_agent['require_auth']).lower()}
CODING_AGENT_INSTALL_TIMEOUT_S={coding_agent['install_timeout_s']}
CODING_AGENT_INSTALL_HOME={coding_agent['install_home']}
CODING_AGENT_HOME={coding_agent['home']}
ROBOT_USE_BACKEND=mock
OPENAI_API_KEY=
OPENAI_MODEL=
"""
        (root / "config" / "rolo.env.example").write_text(env_text, encoding="utf-8")
        (root / "systemd" / "rolo-bootstrap-agentd.service").write_text(
            _service_unit(
                description="rolo minimal bootstrap agent daemon",
                service_user=service_user,
                install_root=install_root,
                config_root=config_root,
                artifact_root=artifact_root,
                command=(
                    f"bootstrap-agentd --robot ${{ROBOT_ID}} "
                    f"--host {bootstrap_agentd.get('host', '127.0.0.1')} "
                    f"--port {bootstrap_agentd.get('port', 8100)}"
                ),
                robot_identity=True,
            ),
            encoding="utf-8",
        )
        (root / "systemd" / "rolo-agentd.service").write_text(
            _service_unit(
                description="rolo agent daemon",
                service_user=service_user,
                install_root=install_root,
                config_root=config_root,
                artifact_root=artifact_root,
                command=(
                    f"agentd --robot ${{ROBOT_ID}} --host {agentd.get('host', '127.0.0.1')} "
                    f"--port {agentd.get('port', 8101)}"
                ),
                robot_identity=True,
                after=("rolo-discovery.service",),
                wants=("rolo-bootstrap-agentd.service",),
                requires=("rolo-discovery.service",),
            ),
            encoding="utf-8",
        )
        (root / "systemd" / "rolo-control-plane.service").write_text(
            _service_unit(
                description="rolo control plane",
                service_user=service_user,
                install_root=install_root,
                config_root=config_root,
                artifact_root=artifact_root,
                command=(
                    f"serve --host {control.get('host', '127.0.0.1')} "
                    f"--port {control.get('port', 8080)}"
                ),
                after=("rolo-agentd.service",),
                wants=("rolo-agentd.service",),
            ),
            encoding="utf-8",
        )
        (root / "systemd" / "rolo-discovery.service").write_text(
            _discovery_service_unit(
                service_user=service_user,
                install_root=install_root,
                config_root=config_root,
                artifact_root=artifact_root,
                bootstrap_url=(
                    f"http://127.0.0.1:{bootstrap_agentd.get('port', 8100)}"
                ),
            ),
            encoding="utf-8",
        )
        (root / "install.sh").write_text(
            _installer(
                profile_ids=profile_ids,
                target_arch=target_arch,
                service_user=service_user,
                install_root=install_root,
                config_root=config_root,
                artifact_root=artifact_root,
                coding_agent=coding_agent,
            ),
            encoding="utf-8",
            newline="\n",
        )
        (root / "README.md").write_text(
            _bundle_readme(
                profile_ids=profile_ids,
                target_arch=target_arch,
                supported_compute=supported_compute_names,
            ),
            encoding="utf-8",
        )

        files = {
            path.relative_to(root).as_posix(): sha256_file(path)
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }
        schema_files = sorted((root / "schemas").glob("*.json"))
        schema_digest = hashlib.sha256(
            b"".join(path.read_bytes() for path in schema_files)
        ).hexdigest()
        manifest = {
            "schema_version": "robot-deployment-bundle/v1",
            "product": "rolo",
            "version": __version__,
            "identity_mode": "dynamic_enrollment",
            "included_robot_ids": [],
            "profile_ids": list(profile_ids),
            "target_arch": target_arch,
            "kernel_arch": ARCH_ALIASES[target_arch],
            "platform_baseline": platform_baseline,
            "supported_compute": supported_compute_ids,
            "dependency_mode": deployment.get("dependency_mode", "online_resolve"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_revision": source_revision,
            "common_schema_digest": schema_digest,
            "application_wheel_sha256": sha256_file(root / "wheels" / wheel.name),
            "startup_order": ["bootstrap-agentd", "discovery", "agentd"],
            "files": files,
        }
        (root / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    archive.write(path, arcname=path.relative_to(root.parent))

    return BundleResult(
        bundle=archive_path,
        profile_ids=profile_ids,
        target_arch=target_arch,
        version=__version__,
        sha256=sha256_file(archive_path),
    )
