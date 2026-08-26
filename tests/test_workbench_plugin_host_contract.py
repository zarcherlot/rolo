from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parents[1]


def _design() -> dict[str, object]:
    path = ROOT / "schemas" / "rolo-workbench-plugin-host-contract-design-v1.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _contract() -> str:
    return (ROOT / "docs" / "WORKBENCH_PLUGIN_HOST_CONTRACT.md").read_text(
        encoding="utf-8"
    )


def test_e23a_freezes_robot_owned_same_origin_routes_without_replacing_root_api() -> None:
    design = _design()
    assert design["schema_version"] == "rolo-workbench-plugin-host-contract-design/v1"
    assert design["status"] == "e23a-review-candidate"
    assert design["plugin_schema"] == "rolo-plugin/v2"
    assert design["routes"] == {
        "workbench_mount": "/workbench/",
        "api_base": "/rolo-api",
        "legacy_api_compatibility": ["/health", "/v1/*"],
        "spa_fallback_scope": "/workbench/*",
        "asset_miss_status": 404,
    }


def test_e23a_uses_one_process_without_http_self_proxy_or_duplicate_endpoints() -> None:
    runtime = _design()["runtime"]
    assert runtime == {
        "command": "robotctl runtime serve",
        "listener_count": 1,
        "http_self_proxy": False,
        "duplicate_api_routes": False,
        "plugin_optional": True,
        "api_survives_plugin_failure": True,
    }
    source = (ROOT / "src" / "rolo" / "commands" / "runtime.py").read_text(
        encoding="utf-8"
    )
    assert '"rolo.api:app"' in source
    assert "StaticFiles" not in (ROOT / "src" / "rolo" / "api.py").read_text(
        encoding="utf-8"
    )


def test_e23a_restricts_workbench_network_modes_and_browser_secrets() -> None:
    design = _design()
    assert design["network_modes"] == [
        "ROBOT_LOOPBACK",
        "TRUSTED_REVERSE_PROXY_TO_LOOPBACK",
    ]
    assert design["direct_non_loopback_workbench"] is False
    forbidden = set(design["forbidden_capabilities"])
    assert {
        "public_site",
        "cloud_runtime",
        "cross_origin_api",
        "browser_bearer_secret",
        "teleoperation",
        "arbitrary_command",
        "verification_influence",
    } <= forbidden


def test_e23a_requires_bounded_v2_package_integrity_and_feature_compatibility() -> None:
    design = _design()
    assert design["package"] == {
        "manifest": "rolo.plugin.json",
        "checksums": "SHA256SUMS",
        "entry": "dist/client/index.html",
        "checksum_algorithm": "sha256",
        "delivery_mode": "device-local",
    }
    assert set(design["required_manifest_sections"]) == {
        "delivery",
        "api",
        "security",
        "integrity",
    }
    assert design["compatibility_authority"] == "health-advertised-api-features"
    forbidden = set(design["forbidden_capabilities"])
    assert {
        "directory_scan",
        "directory_listing",
        "arbitrary_file_serving",
        "path_traversal",
        "symlink_escape",
    } <= forbidden


def test_e23a_defers_runtime_and_public_deployment() -> None:
    design = _design()
    assert design["implementation"] == {
        "contract": "candidate-e23a",
        "rolo_host": "deferred-e23b",
        "rolo_vis_package": "deferred-e23c",
        "real_device_validation": "deferred-e23d",
        "public_deployment": False,
    }
    contract = _contract()
    assert "not a separately hosted public application" in contract
    assert "add no runtime host, route advertisement, package, or public deployment" in contract
    assert "`v0.37.0` remains immutable" in contract
