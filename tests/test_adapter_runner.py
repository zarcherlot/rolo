import json
import os
import sys
from pathlib import Path

import pytest

from rolo.adapter_runner import BoundedAdapterRunner
from rolo.runtime_context import AdapterRuntimeContext, admitted_runtime_environment


def test_runner_fails_closed_without_os_sandbox(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ROLO_ADAPTER_UNSANDBOXED_DEV", raising=False)
    monkeypatch.delenv("ROLO_ADAPTER_SANDBOX_LAUNCHER", raising=False)
    runner = BoundedAdapterRunner()
    runner.sandbox_launcher = None
    runner.allow_unsandboxed_development = False

    with pytest.raises(RuntimeError, match="requires ROLO_ADAPTER_SANDBOX_LAUNCHER"):
        runner.run(
            [sys.executable, "-c", "print('must not execute')"],
            cwd=tmp_path,
            timeout_s=5,
        )


def test_runner_wraps_adapter_argv_with_protected_launcher(tmp_path: Path) -> None:
    launcher = tmp_path / "sandbox-launcher"
    launcher.write_text("#!/bin/sh\n", encoding="utf-8")
    launcher.chmod(0o700)
    runner = BoundedAdapterRunner(
        sandbox_launcher=launcher,
        allow_unsandboxed_development=False,
    )

    command = runner._sandbox_command(["adapter", "describe"], tmp_path.resolve())

    assert command == [
        str(launcher),
        "--cwd",
        str(tmp_path.resolve()),
        "--",
        "adapter",
        "describe",
    ]


def test_runner_sanitizes_environment_and_private_home(
    tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("ROLO_TEST_SECRET_TOKEN", "must-not-leak")
    runner = BoundedAdapterRunner()
    runner.sandbox_launcher = None
    runner.allow_unsandboxed_development = True
    result = runner.run(
        [
            sys.executable,
            "-c",
            (
                "import json,os; "
                "print(json.dumps({'secret': os.getenv('ROLO_TEST_SECRET_TOKEN'), "
                "'home': os.getenv('HOME'), 'cwd': os.getcwd()}))"
            ),
        ],
        cwd=tmp_path,
        timeout_s=5,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["secret"] is None
    assert Path(payload["home"]).name.startswith("rolo-adapter-home-")
    assert Path(payload["cwd"]) == tmp_path
    assert "must-not-leak" not in result.stdout + result.stderr


def test_runner_rejects_unbounded_output(tmp_path: Path) -> None:
    result = BoundedAdapterRunner().run(
        [sys.executable, "-c", "import sys; sys.stdout.write('x' * 1000000)"],
        cwd=tmp_path,
        timeout_s=5,
        max_stdout_bytes=1024,
    )
    assert result.output_limited is True
    assert len(result.stdout.encode("utf-8")) == 1024


def test_runner_terminates_on_timeout(tmp_path: Path) -> None:
    result = BoundedAdapterRunner().run(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        cwd=tmp_path,
        timeout_s=0.1,
    )
    assert result.timed_out is True
    assert result.returncode != 0


def test_runner_never_inherits_openai_or_codex_credentials(
    tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("OPENAI_API_KEY", "openai-secret")
    monkeypatch.setenv("CODEX_API_KEY", "codex-secret")
    result = BoundedAdapterRunner().run(
        [
            sys.executable,
            "-c",
            (
                "import json,os; print(json.dumps({key: os.getenv(key) for key in "
                "['OPENAI_API_KEY','CODEX_API_KEY']}))"
            ),
        ],
        cwd=tmp_path,
        timeout_s=5,
    )
    assert json.loads(result.stdout) == {"OPENAI_API_KEY": None, "CODEX_API_KEY": None}
    assert "openai-secret" not in result.stdout + result.stderr
    assert "codex-secret" not in result.stdout + result.stderr


def test_runner_passes_only_admitted_robot_runtime_context(tmp_path: Path) -> None:
    overlay = tmp_path / "overlay"
    overlay.mkdir()
    runtime = admitted_runtime_environment(
        {
            "ROS_DOMAIN_ID": "42",
            "RMW_IMPLEMENTATION": "rmw_cyclonedds_cpp",
            "AMENT_PREFIX_PATH": str(overlay),
            "OPENAI_API_KEY": "must-not-be-admitted",
        }
    )

    result = BoundedAdapterRunner().run(
        [
            sys.executable,
            "-c",
            (
                "import json,os; print(json.dumps({key: os.getenv(key) for key in "
                "['ROS_DOMAIN_ID','RMW_IMPLEMENTATION','AMENT_PREFIX_PATH',"
                "'OPENAI_API_KEY']}))"
            ),
        ],
        cwd=tmp_path,
        timeout_s=5,
        runtime_environment=runtime,
    )

    assert result.returncode == 0
    assert json.loads(result.stdout) == {
        "ROS_DOMAIN_ID": "42",
        "RMW_IMPLEMENTATION": "rmw_cyclonedds_cpp",
        "AMENT_PREFIX_PATH": str(overlay.resolve()),
        "OPENAI_API_KEY": None,
    }


def test_runtime_context_drops_missing_and_relative_overlay_paths(tmp_path: Path) -> None:
    runtime = admitted_runtime_environment(
        {
            "AMENT_PREFIX_PATH": os.pathsep.join(
                ["relative-overlay", str(tmp_path / "missing-overlay")]
            )
        }
    )

    assert runtime == {}


def test_runtime_context_admits_only_available_absolute_executable_paths(
    tmp_path: Path,
) -> None:
    target_bin = tmp_path / "target-venv/bin"
    target_bin.mkdir(parents=True)

    runtime = admitted_runtime_environment(
        {
            "PATH": os.pathsep.join(
                ["relative-bin", str(tmp_path / "missing-bin"), str(target_bin)]
            )
        }
    )

    assert runtime == {"PATH": str(target_bin.resolve())}


def test_runtime_context_canonicalizes_fastdds_profile_file(tmp_path: Path) -> None:
    profile = tmp_path / "fastdds.xml"
    profile.write_text("<profiles/>", encoding="utf-8")

    runtime = admitted_runtime_environment(
        {"FASTRTPS_DEFAULT_PROFILES_FILE": str(profile)}
    )

    assert runtime == {"FASTRTPS_DEFAULT_PROFILES_FILE": str(profile.resolve())}


def test_runtime_context_contract_rejects_unknown_fields() -> None:
    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        AdapterRuntimeContext.model_validate({"OPENAI_API_KEY": "secret"})


def test_runtime_context_release_validation_rejects_unavailable_paths(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="available absolute path"):
        AdapterRuntimeContext.model_validate(
            {"AMENT_PREFIX_PATH": str(tmp_path / "missing")}
        )
