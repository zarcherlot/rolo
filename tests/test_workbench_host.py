from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from typer import BadParameter
from typer.testing import CliRunner

from rolo.cli import app as cli_app
from rolo.commands.runtime import runtime_server_application
from rolo.core.config import Settings
from rolo.workbench_host import (
    WorkbenchPluginError,
    create_workbench_app,
    load_workbench_plugin,
)

runner = CliRunner()


def _manifest(required_features: list[str] | None = None) -> dict[str, object]:
    return {
        "schema_version": "rolo-plugin/v2",
        "id": "rolo-vis",
        "name": "rolo Workbench",
        "version": "0.38.0",
        "kind": "web-workbench",
        "entry": "dist/client/index.html",
        "delivery": {
            "mode": "device-local",
            "mount_path": "/workbench/",
            "spa_fallback": "scoped",
        },
        "capabilities": ["robot.overview.read"],
        "api": {
            "base_path": "/rolo-api",
            "required_features": required_features or [],
            "required_endpoints": ["/health", "/v1/robots"],
        },
        "security": {
            "mode": "read-only",
            "remote_access": "loopback-or-trusted-reverse-proxy",
            "allows_arbitrary_commands": False,
            "allows_secret_payloads": False,
        },
        "integrity": {"algorithm": "sha256", "manifest": "SHA256SUMS"},
    }


def _package(
    root: Path,
    *,
    required_features: list[str] | None = None,
) -> Path:
    assets = root / "dist" / "client" / "assets"
    assets.mkdir(parents=True)
    (root / "rolo.plugin.json").write_text(
        json.dumps(_manifest(required_features), indent=2) + "\n",
        encoding="utf-8",
    )
    (root / "dist" / "client" / "index.html").write_text(
        "<!doctype html><title>rolo Workbench</title><div id='root'></div>",
        encoding="utf-8",
    )
    (assets / "index-ABC12345.js").write_text("console.log('workbench');\n", encoding="utf-8")
    covered = [
        root / "rolo.plugin.json",
        root / "dist" / "client" / "assets" / "index-ABC12345.js",
        root / "dist" / "client" / "index.html",
    ]
    lines = []
    for path in sorted(covered, key=lambda item: item.relative_to(root).as_posix()):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(root).as_posix()}")
    (root / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return root


def _api() -> FastAPI:
    api = FastAPI()

    @api.get("/health")
    def health() -> dict[str, object]:
        return {"status": "HEALTHY", "api_features": []}

    @api.get("/v1/ping")
    def ping() -> dict[str, bool]:
        return {"ok": True}

    return api


def test_valid_plugin_serves_scoped_spa_assets_and_api_alias(tmp_path: Path) -> None:
    host = create_workbench_app(_package(tmp_path / "plugin"), _api())
    assert host.diagnostic.status == "AVAILABLE"
    assert host.diagnostic.plugin_id == "rolo-vis"

    with TestClient(host) as client:
        redirect = client.get("/workbench?episode=ep-1", follow_redirects=False)
        index = client.get("/workbench/")
        deep_link = client.get("/workbench/review?episode=ep-1")
        asset = client.get("/workbench/assets/index-ABC12345.js")
        missing_asset = client.get("/workbench/assets/missing.js")
        aliased_health = client.get("/rolo-api/health")
        aliased_ping = client.get("/rolo-api/v1/ping")
        legacy_health = client.get("/health")

    assert redirect.status_code == 307
    assert redirect.headers["location"] == "/workbench/?episode=ep-1"
    assert index.status_code == 200
    assert index.headers["cache-control"] == "no-store"
    assert index.headers["x-content-type-options"] == "nosniff"
    assert deep_link.status_code == 200
    assert asset.status_code == 200
    assert asset.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert missing_asset.status_code == 404
    assert aliased_health.json()["status"] == "HEALTHY"
    assert aliased_ping.json() == {"ok": True}
    assert legacy_health.json()["status"] == "HEALTHY"


def test_plugin_failure_is_bounded_and_api_survives(tmp_path: Path) -> None:
    package = _package(tmp_path / "plugin")
    (package / "dist" / "client" / "index.html").write_text("changed", encoding="utf-8")

    host = create_workbench_app(package, _api())
    assert host.diagnostic.status == "REJECTED"
    assert host.diagnostic.reason_code == "CHECKSUM_MISMATCH"
    assert host.diagnostic.plugin_id is None

    with TestClient(host) as client:
        unavailable = client.get("/workbench/")
        health = client.get("/health")

    assert unavailable.status_code == 404
    assert unavailable.json() == {
        "detail": "Workbench plugin unavailable",
        "reason": "CHECKSUM_MISMATCH",
    }
    assert health.status_code == 200


def test_validated_plugin_fails_closed_if_a_served_file_changes(tmp_path: Path) -> None:
    package = _package(tmp_path / "plugin")
    host = create_workbench_app(package, _api())
    (package / "dist" / "client" / "index.html").write_text("changed later", encoding="utf-8")

    with TestClient(host) as client:
        response = client.get("/workbench/")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Workbench plugin unavailable",
        "reason": "PACKAGE_CHANGED",
    }


def test_validator_rejects_unknown_features_uncovered_files_and_links(tmp_path: Path) -> None:
    unsupported = _package(tmp_path / "unsupported", required_features=["unknown.feature/v1"])
    with pytest.raises(WorkbenchPluginError, match="INVALID_MANIFEST"):
        load_workbench_plugin(unsupported)

    unexpected = _package(tmp_path / "unexpected")
    (unexpected / "README.md").write_text("not part of package", encoding="utf-8")
    with pytest.raises(WorkbenchPluginError, match="UNEXPECTED_PACKAGE_FILE"):
        load_workbench_plugin(unexpected)

    linked = _package(tmp_path / "linked")
    try:
        (linked / "dist" / "client" / "assets" / "linked.js").symlink_to(
            linked / "dist" / "client" / "assets" / "index-ABC12345.js"
        )
    except OSError:
        return
    with pytest.raises(WorkbenchPluginError, match="PACKAGE_LINK_REJECTED"):
        load_workbench_plugin(linked)


def test_workbench_runtime_requires_loopback_and_preserves_api_only_mode(tmp_path: Path) -> None:
    api_only = Settings(_env_file=None, rolo_workbench_plugin_dir=None)
    hosted = Settings(_env_file=None, rolo_workbench_plugin_dir=tmp_path / "plugin")
    token_api = Settings(
        _env_file=None,
        rolo_api_token="test-token",
        rolo_workbench_plugin_dir=None,
    )

    assert runtime_server_application(api_only, "127.0.0.1") == "rolo.api:app"
    assert runtime_server_application(hosted, "127.0.0.1") == "rolo.workbench_host:app"
    assert runtime_server_application(token_api, "0.0.0.0") == "rolo.api:app"
    with pytest.raises(BadParameter, match="requires ROLO_API_TOKEN"):
        runtime_server_application(api_only, "0.0.0.0")
    with pytest.raises(BadParameter, match="trusted reverse proxy"):
        runtime_server_application(
            Settings(
                _env_file=None,
                rolo_api_token="test-token",
                rolo_workbench_plugin_dir=tmp_path / "plugin",
            ),
            "0.0.0.0",
        )


def test_runtime_serve_is_canonical_and_root_alias_remains_available() -> None:
    canonical = runner.invoke(cli_app, ["runtime", "serve", "--help"])
    compatibility = runner.invoke(cli_app, ["serve", "--help"])

    assert canonical.exit_code == 0, canonical.output
    assert "optional Workbench plugin" in canonical.output
    assert compatibility.exit_code == 0, compatibility.output
    assert "Compatibility alias" in compatibility.output
