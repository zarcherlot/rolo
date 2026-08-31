from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rolo.core.config import get_settings
from rolo.device_hardening_evidence import (
    DEVICE_HARDENING_SCENARIOS,
    DeviceHardeningEvidenceBundle,
    build_device_hardening_bundle,
    build_release_ledger,
)
from rolo.product_cli import app
from rolo.target_ref import LocalTargetRef
from rolo.targets.profiles import CredentialReference, TargetProfileStore


def _load_harness():
    path = Path(__file__).parents[1] / "scripts" / "rolo-live-harness.py"
    spec = importlib.util.spec_from_file_location("rolo_live_harness_for_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _profile(root: Path, target_id: str = "staging-target") -> None:
    workspace = root / "workspace"
    workspace.mkdir(parents=True)
    TargetProfileStore(root).create(
        robot_id=target_id,
        target=LocalTargetRef(workspace=workspace),
        credential=CredentialReference(kind="platform-keychain", reference="demo:target"),
    )


def test_default_export_keeps_all_external_scenarios_pending(tmp_path: Path) -> None:
    _profile(tmp_path)
    bundle = build_device_hardening_bundle(
        tmp_path,
        target_id="staging-target",
        release_line="0.1.x",
        rolo_revision="a" * 40,
    )
    assert bundle.target_kind == "local"
    assert [item.scenario_id for item in bundle.evidence] == list(DEVICE_HARDENING_SCENARIOS)
    assert {item.status for item in bundle.evidence} == {"PENDING_EXTERNAL"}
    ledger = build_release_ledger(bundle)
    assert all(entry.status == "PENDING_EXTERNAL" for entry in ledger.entries)


def test_live_harness_manifest_is_repeatable_and_explicitly_bounded(tmp_path: Path) -> None:
    harness = _load_harness()
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    harness._seed(first_root)
    harness._seed(second_root)
    first = harness._manifest(first_root)
    second = harness._manifest(second_root)
    assert first == second
    assert first["schema_version"] == "rolo-staging-harness-manifest/v1"
    assert set(first["failure_semantics"].values()) >= {"BLOCKED", "PENDING", "PENDING_EXTERNAL"}
    assert all(str(item).startswith("job_") for item in first["job_ids"])


def test_verified_export_requires_audited_bounded_input(tmp_path: Path) -> None:
    _profile(tmp_path)
    evidence = tmp_path / "audited.json"
    evidence.write_text(
        json.dumps(
            {
                "evidence": [
                    {
                        "scenario_id": "linux-x86_64",
                        "status": "VERIFIED",
                        "evidence": {
                            "os": "Linux",
                            "architecture": "x86_64",
                            "package_digest": "a1b2c3d4e5f60718",
                            "job_id": "job_external_1",
                            "gate_result": "PASS",
                            "observed_at": "2026-08-31T00:00:00Z",
                            "summary": "Signed package verified on the controlled target.",
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    bundle = build_device_hardening_bundle(
        tmp_path,
        target_id="staging-target",
        release_line="0.1.x",
        rolo_revision="a" * 40,
        evidence_input=evidence,
    )
    item = next(item for item in bundle.evidence if item.scenario_id == "linux-x86_64")
    assert item.status == "VERIFIED"
    assert item.evidence is not None
    assert build_release_ledger(bundle).entries[1].job_id == "job_external_1"

    unsafe = evidence.read_text(encoding="utf-8").replace("Signed package", "ssh://user@host")
    evidence.write_text(unsafe, encoding="utf-8")
    with pytest.raises(ValueError):
        build_device_hardening_bundle(
            tmp_path,
            target_id="staging-target",
            release_line="0.1.x",
            rolo_revision="a" * 40,
            evidence_input=evidence,
        )


def test_bundle_rejects_duplicate_or_unknown_scenarios(tmp_path: Path) -> None:
    _profile(tmp_path)
    base = build_device_hardening_bundle(
        tmp_path,
        target_id="staging-target",
        release_line="0.1.x",
        rolo_revision="a" * 40,
    ).model_dump(mode="json")
    base["evidence"] = [
        {"scenario_id": "linux-arm64", "status": "PENDING_EXTERNAL"},
        {"scenario_id": "linux-arm64", "status": "PENDING_EXTERNAL"},
    ]
    with pytest.raises(ValueError):
        DeviceHardeningEvidenceBundle.model_validate(base)
    unknown = tmp_path / "unknown.json"
    unknown.write_text(
        json.dumps({"evidence": [{"scenario_id": "unlisted-case", "status": "BLOCKED"}]}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unknown device hardening scenario"):
        build_device_hardening_bundle(
            tmp_path,
            target_id="staging-target",
            release_line="0.1.x",
            rolo_revision="a" * 40,
            evidence_input=unknown,
        )


def test_cli_exports_bundle_and_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _profile(tmp_path)
    monkeypatch.setenv("ROLO_CONFIG_DIR", str(tmp_path))
    get_settings.cache_clear()
    output = tmp_path / "handoff" / "device-hardening.json"
    ledger = tmp_path / "handoff" / "release-ledger.json"
    result = CliRunner().invoke(
        app,
        [
            "target",
            "export-device-hardening",
            "--target-id",
            "staging-target",
            "--release-line",
            "0.1.x",
            "--rolo-revision",
            "a" * 40,
            "--output",
            str(output),
            "--ledger-output",
            str(ledger),
        ],
    )
    get_settings.cache_clear()
    assert result.exit_code == 0, result.output
    assert output.is_file() and ledger.is_file()
    assert json.loads(output.read_text(encoding="utf-8"))["schema_version"] == (
        "rolo-vis-device-hardening-evidence/v1"
    )
    assert "PENDING_EXTERNAL" in result.output
