from __future__ import annotations

import hashlib
import os
import shlex
import subprocess
import threading
import time
from pathlib import Path

import pytest

from rolo.core.persistence import interprocess_lock
from rolo.stages.verify.ssh_target_provider import SshTargetHealthProvider
from rolo.target_ref import SshTargetRef


class _Result:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class _Runner:
    def __init__(self, mapping: dict[tuple[str, ...], _Result]) -> None:
        self.mapping = mapping

    def run(self, argv: list[str], *, timeout_s: float) -> _Result:
        del timeout_s
        marker = argv.index("--")
        remote_argv = tuple(shlex.split(" ".join(argv[marker + 2 :])))
        for key, result in self.mapping.items():
            if remote_argv == key:
                return result
        return _Result(1, stderr="unexpected command")


def _mapping() -> dict[tuple[str, ...], _Result]:
    return {
        ("stat", "-c", "%d %i %Z", "/opt/rolo"): _Result(0, "8 12345 1700000000"),
        ("cat", "/etc/machine-id"): _Result(0, "machine-abc\n"),
        ("id", "-un"): _Result(0, "robot\n"),
        ("id", "-u"): _Result(0, "1001\n"),
        ("printenv", "ROS_DOMAIN_ID"): _Result(0, "50\n"),
        ("printenv", "RMW_IMPLEMENTATION"): _Result(0, "rmw_fastrtps_cpp\n"),
        ("uname", "-s"): _Result(0, "Linux\n"),
        ("test", "-d", "/opt/rolo"): _Result(0),
        ("rolo-target", "--version"): _Result(0, "rolo-target 0.1.0\n"),
    }


def _provider(tmp_path: Path, runner: _Runner) -> SshTargetHealthProvider:
    known_hosts = tmp_path / "known_hosts"
    known_hosts.write_text("pinned-host-key\n", encoding="utf-8")
    return SshTargetHealthProvider(
        SshTargetRef(host="robot.example", user="robot", workspace="/opt/rolo"),
        known_hosts=known_hosts,
        profile_sha256="a" * 64,
        package_id="rolo-target",
        package_version="0.1.0",
        runner=runner,
    )


def test_provider_timeout_is_materialized_as_failed_evidence(tmp_path: Path) -> None:
    mapping = _mapping()
    mapping[("rolo-target", "--version")] = _Result(0)

    class _TimeoutRunner(_Runner):
        def run(self, argv: list[str], *, timeout_s: float) -> _Result:
            marker = argv.index("--")
            remote_argv = tuple(shlex.split(" ".join(argv[marker + 2 :])))
            if remote_argv == ("rolo-target", "--version"):
                raise subprocess.TimeoutExpired(argv, timeout_s)
            return super().run(argv, timeout_s=timeout_s)

    report = _provider(tmp_path, _TimeoutRunner(mapping)).run(
        tmp_path, robot_id="robot-1", run_id="timeout-1"
    )
    assert report.status == "FAIL"
    assert any(item.status == "TIMEOUT" for item in report.case_results)
    assert (tmp_path / report.evidence_ref.removeprefix("artifact://")).is_file()


def test_provider_cancel_between_cases_is_materialized(tmp_path: Path) -> None:
    cancel = threading.Event()

    class _CancelRunner(_Runner):
        def run(self, argv: list[str], *, timeout_s: float) -> _Result:
            result = super().run(argv, timeout_s=timeout_s)
            marker = argv.index("--")
            remote_argv = tuple(shlex.split(" ".join(argv[marker + 2 :])))
            if remote_argv == ("uname", "-s"):
                cancel.set()
            return result

    report = _provider(tmp_path, _CancelRunner(_mapping())).run(
        tmp_path, robot_id="robot-1", run_id="cancel-1", cancel_event=cancel
    )
    assert report.status == "CANCELLED"
    assert any(item.status == "CANCELLED" for item in report.case_results)


def test_provider_rejects_concurrent_run(tmp_path: Path) -> None:
    provider = _provider(tmp_path, _Runner(_mapping()))
    lock_target = tmp_path / "verify" / "robot-1" / "ssh-target-provider.active"
    with interprocess_lock(lock_target):
        with pytest.raises(ValueError, match="already active"):
            provider.run(tmp_path, robot_id="robot-1", run_id="busy-1")


def test_provider_recovers_stale_lock(tmp_path: Path) -> None:
    lock_target = tmp_path / "verify" / "robot-1" / "ssh-target-provider.active"
    lock_target.parent.mkdir(parents=True)
    lock_path = lock_target.with_name(
        ".l" + hashlib.sha256(lock_target.name.encode("utf-8")).hexdigest()[:8]
    )
    lock_path.write_text("stale\n", encoding="utf-8")
    old = time.time() - 601
    os.utime(lock_path, (old, old))

    report = _provider(tmp_path, _Runner(_mapping())).run(
        tmp_path, robot_id="robot-1", run_id="recover-1"
    )
    assert report.status == "PASS"
    assert not lock_path.exists()
