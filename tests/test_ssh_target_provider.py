from __future__ import annotations

import shlex
from pathlib import Path

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
        self.calls: list[tuple[str, ...]] = []

    def run(self, argv: list[str], *, timeout_s: float) -> _Result:
        del timeout_s
        self.calls.append(tuple(argv))
        # OpenSSH joins the post-destination arguments into a remote shell
        # command. Decode that transport boundary before matching the logical
        # argv used by the provider.
        marker = argv.index("--")
        remote_argv = tuple(shlex.split(" ".join(argv[marker + 2 :])))
        for key, result in self.mapping.items():
            if remote_argv == key:
                return result
        return _Result(1, stderr="unexpected command")


def _provider(tmp_path: Path, runner: _Runner) -> SshTargetHealthProvider:
    known_hosts = tmp_path / "known_hosts"
    known_hosts.write_text("github-placeholder\n", encoding="utf-8")
    return SshTargetHealthProvider(
        SshTargetRef(host="robot.example", user="robot", workspace="/opt/rolo"),
        known_hosts=known_hosts,
        profile_sha256="a" * 64,
        package_id="rolo-target",
        package_version="0.1.0",
        runner=runner,
    )


def test_ssh_provider_plan_declares_only_fixed_read_only_operations(tmp_path: Path) -> None:
    provider = _provider(tmp_path, _Runner({}))

    plan = provider.plan("robot-1")

    assert provider.provider_id == "target-health"
    assert provider.provider_version == "2.0.0"
    assert {case.operation for case in plan.cases} == provider.read_only_operations
    assert all(case.timeout_s <= 60.0 for case in plan.cases)
    assert all(
        case.payload in (
            {"mode": "system"},
            {"mode": "directory"},
            {"mode": "version"},
        )
        for case in plan.cases
    )


def test_ssh_provider_materializes_main_v2_evidence(tmp_path: Path) -> None:
    runner = _Runner(
        {
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
    )
    report = _provider(tmp_path, runner).run(
        tmp_path, robot_id="robot-1", run_id="run-1"
    )

    assert report.status == "PASS"
    assert report.evidence_ref.endswith("adapted-evidence-v2.json")
    evidence = tmp_path / report.evidence_ref.removeprefix("artifact://")
    assert evidence.is_file()
    assert (
        '"schema_version": "rolo-verification-evidence/v2"'
        in evidence.read_text(encoding="utf-8")
    )
    assert (tmp_path / "verify/robot-1/runs/run-1/legacy-provider-evidence.json").is_file()


def test_ssh_provider_cancellation_is_fail_closed(tmp_path: Path) -> None:
    import threading

    runner = _Runner({})
    cancel = threading.Event()
    cancel.set()
    try:
        _provider(tmp_path, runner).run(tmp_path, robot_id="robot-1", cancel_event=cancel)
    except ValueError as exc:
        assert "cancelled" in str(exc)
    else:
        raise AssertionError("cancelled provider must stop before collection")
