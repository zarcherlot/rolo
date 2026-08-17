from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from robot_loop import __version__
from robot_loop.config import load_yaml

ARCH_ALIASES = {"arm64": "aarch64"}
COMMON_DEPLOYMENT_KEYS = ("install_root", "config_root", "artifact_root", "service_user")


@dataclass(frozen=True)
class BundleResult:
    bundle: Path
    robot_ids: tuple[str, ...]
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
    robot_profile: bool = False,
    after_discovery: bool = False,
) -> str:
    profile_env = f"EnvironmentFile={config_root}/robot-profile.env\n" if robot_profile else ""
    discovery_dependency = " robot-loop-discovery.service" if after_discovery else ""
    return f"""[Unit]
Description={description}
After=network-online.target{discovery_dependency}
Wants=network-online.target{discovery_dependency}

[Service]
Type=simple
User={service_user}
Group={service_user}
WorkingDirectory={install_root}
EnvironmentFile=-{config_root}/robot-loop.env
{profile_env}Environment=ROBOT_LOOP_CONFIG_DIR={config_root}
Environment=ROBOT_LOOP_ARTIFACT_DIR={artifact_root}
ExecStart={install_root}/venv/bin/robotctl {command}
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
"""


def _discovery_service_unit(
    *, service_user: str, install_root: str, config_root: str, artifact_root: str
) -> str:
    exec_start = (
        f"{install_root}/venv/bin/robotctl discover run --robot ${{ROBOT_ID}} "
        "--source-root ${ROBOT_DISCOVERY_SOURCE_ROOT}"
    )
    return f"""[Unit]
Description=Robot Loop hardware and software discovery
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User={service_user}
Group={service_user}
WorkingDirectory={install_root}
EnvironmentFile=-{config_root}/robot-loop.env
EnvironmentFile={config_root}/robot-profile.env
Environment=ROBOT_LOOP_CONFIG_DIR={config_root}
Environment=ROBOT_LOOP_ARTIFACT_DIR={artifact_root}
ExecStart={exec_start}
RemainAfterExit=true
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
"""


def _installer(
    *,
    robot_ids: Sequence[str],
    target_arch: str,
    service_user: str,
    install_root: str,
    config_root: str,
    artifact_root: str,
) -> str:
    allowed = " ".join(robot_ids)
    kernel_arch = ARCH_ALIASES[target_arch]
    return f"""#!/usr/bin/env bash
set -euo pipefail

BUNDLE_ROOT="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
ROBOT_ID="${{1:-}}"
ALLOWED_ROBOTS=" {allowed} "
EXPECTED_ARCH="{kernel_arch}"
ACTUAL_ARCH="$(uname -m)"

if [[ "$ALLOWED_ROBOTS" != *" $ROBOT_ID "* ]]; then
  echo "Usage: sudo bash install.sh <{("|".join(robot_ids))}>" >&2
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
if [[ "${{ID:-}}" != "ubuntu" || "${{VERSION_ID:-}}" != "22.04" ]]; then
  echo "Platform mismatch: Ubuntu 22.04 is required" >&2
  exit 2
fi
if [[ ! -r /opt/ros/humble/setup.bash ]]; then
  echo "ROS 2 Humble was not found at /opt/ros/humble" >&2
  exit 2
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
  echo "Run this installer as root (for example: sudo bash install.sh $ROBOT_ID)" >&2
  exit 3
fi

SERVICE_USER="{service_user}"
INSTALL_ROOT="{install_root}"
CONFIG_ROOT="{config_root}"
ARTIFACT_ROOT="{artifact_root}"

if ! id "$SERVICE_USER" >/dev/null 2>&1; then
  useradd --system --home-dir "$ARTIFACT_ROOT" --shell /usr/sbin/nologin "$SERVICE_USER"
fi

install -d -o root -g root -m 0755 \
  "$INSTALL_ROOT" "$CONFIG_ROOT" "$CONFIG_ROOT/robots" "$CONFIG_ROOT/platforms"
install -d -o "$SERVICE_USER" -g "$SERVICE_USER" -m 0750 "$ARTIFACT_ROOT"
python3 -m venv "$INSTALL_ROOT/venv"
"$INSTALL_ROOT/venv/bin/python" -m pip install --upgrade pip
"$INSTALL_ROOT/venv/bin/python" -m pip install "$BUNDLE_ROOT"/wheels/robot_loop-*.whl

for profile in {allowed}; do
  rm -f "$CONFIG_ROOT/robots/$profile.yaml"
done
install -m 0644 "$BUNDLE_ROOT/profiles/$ROBOT_ID/capability.yaml" \
  "$CONFIG_ROOT/robots/$ROBOT_ID.yaml"
install -m 0644 "$BUNDLE_ROOT/profiles/$ROBOT_ID/deployment.yaml" \
  "$CONFIG_ROOT/deployment.yaml"
install -m 0644 "$BUNDLE_ROOT/config/robot_use.yaml" "$CONFIG_ROOT/robot_use.yaml"
install -m 0644 "$BUNDLE_ROOT/config/discovery.yaml" "$CONFIG_ROOT/discovery.yaml"
install -m 0644 "$BUNDLE_ROOT/config/platforms/arm64.yaml" "$CONFIG_ROOT/platforms/arm64.yaml"
printf 'ROBOT_ID=%s\n' "$ROBOT_ID" > "$CONFIG_ROOT/robot-profile.env"
chmod 0644 "$CONFIG_ROOT/robot-profile.env"
install -d -m 0755 "$INSTALL_ROOT/schemas"
install -m 0644 "$BUNDLE_ROOT"/schemas/*.json "$INSTALL_ROOT/schemas/"

if [[ ! -e "$CONFIG_ROOT/robot-loop.env" ]]; then
  install -m 0600 "$BUNDLE_ROOT/config/robot-loop.env.example" "$CONFIG_ROOT/robot-loop.env"
fi

install -m 0644 "$BUNDLE_ROOT/systemd/robot-loop-agentd.service" /etc/systemd/system/
install -m 0644 "$BUNDLE_ROOT/systemd/robot-loop-control-plane.service" /etc/systemd/system/
install -m 0644 "$BUNDLE_ROOT/systemd/robot-loop-discovery.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now robot-loop-discovery.service
systemctl enable --now robot-loop-agentd.service robot-loop-control-plane.service

echo "Installed Robot Loop {__version__} with profile $ROBOT_ID"
echo "Check with: systemctl status robot-loop-agentd robot-loop-control-plane"
"""


def _bundle_readme(
    *, robot_ids: Sequence[str], target_arch: str, supported_compute: Sequence[str]
) -> str:
    choices = "|".join(robot_ids)
    return f"""# Robot Loop compatible ARM deployment bundle

- Product version: `{__version__}`
- Platform baseline: ARM64 + Ubuntu 22.04 + ROS 2 Humble
- Supported compute: {", ".join(supported_compute)}
- Included robot profiles: `{", ".join(robot_ids)}`
- Default network exposure: loopback only

Install the same archive on each target and select the local profile:

```bash
unzip robot-loop-{__version__}-{target_arch}.zip
cd robot-loop-{__version__}-{target_arch}
sudo bash install.sh <{choices}>
```

Only the selected profile is activated under `/etc/robot-loop`; the common runtime and schema are
identical on both robots. The default backend is `mock`. Put `OPENAI_API_KEY` and an image-capable
`OPENAI_MODEL` in `/etc/robot-loop/robot-loop.env` to enable remote multimodal `robot_use`.

This MVP bundle resolves Python dependencies from the configured package index. A production
offline release must include an ARM64 wheelhouse. SoC-specific ROS/vendor drivers stay behind the
canonical adapter and profile binding; they are not implemented by this mock bundle.
"""


def build_compatible_bundle(
    *,
    robot_ids: Sequence[str],
    wheel: Path,
    project_root: Path = Path("."),
    output_dir: Path = Path("dist/release"),
) -> BundleResult:
    project_root = project_root.resolve()
    wheel = wheel.resolve()
    selected = tuple(dict.fromkeys(robot_ids))
    if not selected:
        raise ValueError("at least one robot profile is required")
    if not wheel.is_file() or wheel.suffix != ".whl":
        raise ValueError(f"wheel does not exist or is not a .whl file: {wheel}")

    robot_use_path = project_root / "configs" / "robot_use.yaml"
    discovery_config_path = project_root / "configs" / "discovery.yaml"
    platform_config_path = project_root / "configs" / "platforms" / "arm64.yaml"
    schema_dir = project_root / "schemas"
    if (
        not robot_use_path.is_file()
        or not discovery_config_path.is_file()
        or not platform_config_path.is_file()
        or not schema_dir.is_dir()
    ):
        raise ValueError("robot_use/discovery/platform config or schema directory is missing")

    platform_config = load_yaml(platform_config_path)
    compute_entries = platform_config.get("supported_compute", [])
    if not isinstance(compute_entries, list) or not compute_entries:
        raise ValueError("platform supported_compute must be a non-empty list")
    supported_compute_ids = [entry["id"] for entry in compute_entries]
    supported_compute_names = [entry["name"] for entry in compute_entries]

    profiles: list[tuple[str, Path, Path, dict[str, Any], dict[str, Any]]] = []
    for robot_id in selected:
        capability_path = project_root / "configs" / "robots" / f"{robot_id}.yaml"
        deployment_path = project_root / "configs" / "deployment" / f"{robot_id}.yaml"
        if not capability_path.is_file() or not deployment_path.is_file():
            raise ValueError(f"profile inputs are missing for {robot_id}")
        capability = load_yaml(capability_path)
        deployment = load_yaml(deployment_path)
        if capability.get("robot_id") != robot_id or deployment.get("robot_id") != robot_id:
            raise ValueError(f"robot_id mismatch in profile {robot_id}")
        profiles.append((robot_id, capability_path, deployment_path, capability, deployment))

    first_deployment = profiles[0][4]
    target_arch = _require_string(first_deployment, "target_arch")
    if target_arch not in ARCH_ALIASES:
        raise ValueError(f"unsupported target_arch: {target_arch}; only ARM64 is supported")
    common_values = {key: _require_string(first_deployment, key) for key in COMMON_DEPLOYMENT_KEYS}
    source_revision_setting = _require_string(first_deployment, "source_revision")
    platform_baseline = first_deployment.get("platform_baseline")

    for robot_id, _, _, capability, deployment in profiles:
        if capability.get("platform", {}).get("architecture") != target_arch:
            raise ValueError(f"target_arch mismatch in capability {robot_id}")
        if deployment.get("target_arch") != target_arch:
            raise ValueError(f"target_arch mismatch in deployment {robot_id}")
        if deployment.get("source_revision") != source_revision_setting:
            raise ValueError("all profiles must use the same source_revision")
        if deployment.get("platform_baseline") != platform_baseline:
            raise ValueError("all profiles must use the same platform_baseline")
        configured_compute = deployment.get("hardware_profile", {}).get("compute")
        if configured_compute not in {"auto_discover", *supported_compute_ids}:
            raise ValueError(f"unsupported compute platform in deployment {robot_id}")
        for key, value in common_values.items():
            if deployment.get(key) != value:
                raise ValueError(f"all profiles must use the same {key}")

    install_root = common_values["install_root"]
    source_revision = _resolve_source_revision(project_root, source_revision_setting)
    config_root = common_values["config_root"]
    artifact_root = common_values["artifact_root"]
    service_user = common_values["service_user"]
    services = first_deployment.get("services", {})
    control = services.get("control_plane", {})
    agentd = services.get("agentd", {})
    bundle_name = f"robot-loop-{__version__}-{target_arch}"
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / f"{bundle_name}.zip"

    with tempfile.TemporaryDirectory(prefix="robot-loop-bundle-") as temporary:
        root = Path(temporary) / bundle_name
        for relative in ("wheels", "config", "profiles", "schemas", "systemd"):
            (root / relative).mkdir(parents=True)

        shutil.copy2(wheel, root / "wheels" / wheel.name)
        shutil.copy2(robot_use_path, root / "config" / "robot_use.yaml")
        shutil.copy2(discovery_config_path, root / "config" / "discovery.yaml")
        (root / "config" / "platforms").mkdir()
        shutil.copy2(platform_config_path, root / "config" / "platforms" / "arm64.yaml")
        for robot_id, capability_path, deployment_path, _, _ in profiles:
            profile_root = root / "profiles" / robot_id
            profile_root.mkdir()
            shutil.copy2(capability_path, profile_root / "capability.yaml")
            shutil.copy2(deployment_path, profile_root / "deployment.yaml")
        for schema in sorted(schema_dir.glob("*.json")):
            shutil.copy2(schema, root / "schemas" / schema.name)

        env_text = f"""ROBOT_LOOP_ENV=production
ROBOT_LOOP_CONFIG_DIR={config_root}
ROBOT_LOOP_ARTIFACT_DIR={artifact_root}
ROBOT_LOOP_HOST={control.get("host", "127.0.0.1")}
ROBOT_LOOP_PORT={control.get("port", 8080)}
ROBOT_DISCOVERY_SOURCE_ROOT=/opt/robot-application
ROBOT_USE_BACKEND=mock
OPENAI_API_KEY=
OPENAI_MODEL=
"""
        (root / "config" / "robot-loop.env.example").write_text(env_text, encoding="utf-8")
        (root / "systemd" / "robot-loop-agentd.service").write_text(
            _service_unit(
                description="Robot Loop agent daemon",
                service_user=service_user,
                install_root=install_root,
                config_root=config_root,
                artifact_root=artifact_root,
                command=(
                    f"agentd --robot ${{ROBOT_ID}} --host {agentd.get('host', '127.0.0.1')} "
                    f"--port {agentd.get('port', 8101)}"
                ),
                robot_profile=True,
                after_discovery=True,
            ),
            encoding="utf-8",
        )
        (root / "systemd" / "robot-loop-control-plane.service").write_text(
            _service_unit(
                description="Robot Loop control plane",
                service_user=service_user,
                install_root=install_root,
                config_root=config_root,
                artifact_root=artifact_root,
                command=(
                    f"serve --host {control.get('host', '127.0.0.1')} "
                    f"--port {control.get('port', 8080)}"
                ),
            ),
            encoding="utf-8",
        )
        (root / "systemd" / "robot-loop-discovery.service").write_text(
            _discovery_service_unit(
                service_user=service_user,
                install_root=install_root,
                config_root=config_root,
                artifact_root=artifact_root,
            ),
            encoding="utf-8",
        )
        (root / "install.sh").write_text(
            _installer(
                robot_ids=selected,
                target_arch=target_arch,
                service_user=service_user,
                install_root=install_root,
                config_root=config_root,
                artifact_root=artifact_root,
            ),
            encoding="utf-8",
            newline="\n",
        )
        (root / "README.md").write_text(
            _bundle_readme(
                robot_ids=selected,
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
            "product": "robot-loop",
            "version": __version__,
            "robot_profiles": list(selected),
            "target_arch": target_arch,
            "kernel_arch": ARCH_ALIASES[target_arch],
            "platform_baseline": platform_baseline,
            "supported_compute": supported_compute_ids,
            "dependency_mode": first_deployment.get("dependency_mode", "online_resolve"),
            "created_at": datetime.now(UTC).isoformat(),
            "source_revision": source_revision,
            "common_schema_digest": schema_digest,
            "application_wheel_sha256": sha256_file(root / "wheels" / wheel.name),
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
        robot_ids=selected,
        target_arch=target_arch,
        version=__version__,
        sha256=sha256_file(archive_path),
    )
