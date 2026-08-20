import json
from pathlib import Path

from rolo.core.artifacts import ArtifactStore
from rolo.core.registry import RobotRegistry
from rolo.stages.adapt.active_discovery import ActiveDiscoveryInputs
from rolo.stages.adapt.discovery import DiscoveryService
from rolo.stages.adapt.target_fingerprint import target_fingerprint_sha256
from rolo.stages.artifact_paths import resolve_artifact_ref


def test_target_fingerprint_binds_primary_executable_digest(tmp_path: Path) -> None:
    executable = tmp_path / "robot-driver.bin"
    executable.write_bytes(b"deployed-driver-v1")
    registry = RobotRegistry(Path("tests/fixtures/robots"))
    registry.load()
    artifact_root = tmp_path / "artifacts"
    report, _ = DiscoveryService(ArtifactStore(artifact_root)).run(
        robot=registry.get("demo_diff"),
        active_inputs=ActiveDiscoveryInputs(executables=[executable]),
    )
    before = target_fingerprint_sha256(report, artifact_root)
    active_path = resolve_artifact_ref(artifact_root, report.active_discovery_report_ref)
    active = json.loads(active_path.read_text(encoding="utf-8"))
    active["executables"][0]["sha256"] = "f" * 64
    active_path.write_text(json.dumps(active), encoding="utf-8")

    after = target_fingerprint_sha256(report, artifact_root)

    assert after != before
