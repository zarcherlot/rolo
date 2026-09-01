from __future__ import annotations

import json
from pathlib import Path

from rolo.core.artifacts import ArtifactStore
from rolo.core.config import Settings
from rolo.core.hashing import canonical_json_sha256, sha256_file
from rolo.stages.agent_runner import StageAgentTask
from rolo.stages.artifact_paths import ArtifactLayout
from rolo.stages.diagnose.episode import EpisodePhase, validate_published_episode
from rolo.stages.real_target import LocalTargetStageExecutor
from rolo.target_ref import SshTargetRef
from rolo.targets.executor import CommandResult
from rolo.targets.profiles import CredentialReference, TargetProfileStore


class _Transport:
    def __init__(self, target: SshTargetRef) -> None:
        self.target = target

    def execute(self, remote_argv: list[str], *, timeout_s: float) -> CommandResult:
        del timeout_s
        key = tuple(remote_argv)
        outputs = {
            ("stat", "-c", "%d %i %Z", "/opt/rolo"): "8 12345 1700000000",
            ("cat", "/etc/machine-id"): "machine-abc\n",
            ("id", "-un"): "robot\n",
            ("id", "-u"): "1001\n",
            ("printenv", "ROS_DOMAIN_ID"): "50\n",
            ("printenv", "RMW_IMPLEMENTATION"): "rmw_fastrtps_cpp\n",
        }
        if key[:1] == ("uname",):
            value = "Linux ready\n"
        elif key[:2] == ("ros2", "doctor"):
            value = "doctor ready\n"
        else:
            value = outputs.get(key, "ready\n")
        return CommandResult(argv=tuple(remote_argv), returncode=0, stdout=value)


def test_ssh_profile_runs_diagnose_after_authorization(monkeypatch, tmp_path: Path) -> None:
    config = tmp_path / "config"
    known_hosts = tmp_path / "known_hosts"
    known_hosts.write_text("robot.example ssh-ed25519 AAAA\n", encoding="utf-8")
    target = SshTargetRef(host="robot.example", user="robot", workspace="/opt/rolo")
    store = TargetProfileStore(config)
    profile = store.create(
        robot_id="robot-1",
        target=target,
        credential=CredentialReference(kind="ssh-agent", reference="ssh-agent:default"),
        known_hosts=known_hosts,
    )
    profile = profile.model_copy(
        update={
            "host_key": profile.host_key.model_copy(
                update={
                    "status": "APPROVED",
                    "fingerprint": "SHA256:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                    "decided_by": "operator",
                }
            )
        }
    )
    store.save(profile)
    artifacts = ArtifactStore(tmp_path / "artifacts")
    adapter = artifacts.write_json("adapt/robot-1/runs/adapt-1/handoff.json", {})
    monkeypatch.setattr(
        "rolo.stages.adapt.conformance.latest_adapter_handoff_path", lambda *_: adapter
    )
    monkeypatch.setattr(
        "rolo.stages.adapt.conformance.validate_adapter_handoff", lambda *_: None
    )
    profile_path = artifacts.write_json(
        "targets/robot-1/profiles/robot-1.json",
        {
            "profile_id": profile.profile_id,
            "profile_sha256": canonical_json_sha256(profile.model_dump(mode="json")),
        },
    )
    profile_ref = ArtifactLayout(artifacts.root).ref(profile_path)
    task = StageAgentTask(
        stage="diagnose",
        robot_id="robot-1",
        task="ssh diagnosis",
        input_refs={"target_profile": profile_ref},
        input_sha256={"target_profile": sha256_file(profile_path)},
        output_contract="robot-diagnosis-handoff/v1",
        provider="local-target",
        executor="local-target",
        plan_sha256="a" * 64,
    )
    fake_transport = _Transport(target)
    monkeypatch.setattr(
        "rolo.stages.real_target.SubprocessBootstrapTransport",
        lambda target, *, known_hosts: fake_transport,
    )
    executor = LocalTargetStageExecutor(
        artifacts=artifacts,
        settings=Settings(_env_file=None, rolo_config_dir=config, rolo_artifact_dir=artifacts.root),
        stage="diagnose",
    )
    outputs = executor.execute_stage(task, workspace=tmp_path, run_id="ssh-diagnose-1")
    episode = validate_published_episode(artifacts.root, outputs["episode"], robot_id="robot-1")
    assert [item.phase for item in episode.observations] == list(EpisodePhase)
    assert all(item.provenance.source == "ssh-target" for item in episode.observations)
    assert json.loads(
        (artifacts.root / outputs["handoff"].removeprefix("artifact://")).read_text()
    )["robot_id"] == "robot-1"
