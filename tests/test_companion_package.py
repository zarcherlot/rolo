import json

import pytest
from typer.testing import CliRunner

from rolo.product_cli import app
from rolo.targets.package import build_companion_package
from rolo.targets.signing import CompanionReleasePolicy, verify_companion_manifest


def test_companion_builder_emits_executable_and_verified_manifest(tmp_path):
    package, manifest, _ = build_companion_package(
        tmp_path,
        package_version="1.2.3",
        architecture="x86_64",
        publisher_id="rolo",
        verification_key=b"test-key",
    )
    assert package.read_text(encoding="utf-8").startswith("#!/bin/sh")
    assert verify_companion_manifest(manifest, package, verification_key=b"test-key").verified


def test_companion_build_cli_reports_artifacts(tmp_path):
    key = tmp_path / "key"
    key.write_bytes(b"test-key")
    result = CliRunner().invoke(
        app,
        [
            "target",
            "companion-build",
            "--output-dir",
            str(tmp_path / "out"),
            "--version",
            "1.2.3",
            "--architecture",
            "aarch64",
            "--publisher",
            "rolo",
            "--verification-key-file",
            str(key),
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "COMPANION_BUILT"
    assert payload["verification"]["verified"] is True


def test_release_policy_rejects_revoked_version_and_untrusted_publisher(tmp_path):
    package, manifest, _ = build_companion_package(
        tmp_path,
        package_version="1.2.3",
        architecture="x86_64",
        publisher_id="rolo",
        verification_key=b"test-key",
    )
    revoked = CompanionReleasePolicy(publisher_id="rolo", revoked_versions=["1.2.3"])
    with pytest.raises(ValueError, match="version has been revoked"):
        verify_companion_manifest(
            manifest, package, verification_key=b"test-key", release_policy=revoked
        )


def test_release_policy_rejects_package_outside_compatibility_window(tmp_path):
    package, manifest, _ = build_companion_package(
        tmp_path,
        package_id="rolo-target",
        package_version="1.2.3",
        architecture="x86_64",
        publisher_id="rolo",
        verification_key=b"test-key",
    )
    policy = CompanionReleasePolicy(publisher_id="rolo", minimum_version="1.3.0")

    with pytest.raises(ValueError, match="below the supported minimum"):
        verify_companion_manifest(
            manifest, package, verification_key=b"test-key", release_policy=policy
        )
