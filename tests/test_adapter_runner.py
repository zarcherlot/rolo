import json
import sys
from pathlib import Path

from rolo.adapter_runner import BoundedAdapterRunner


def test_runner_sanitizes_environment_and_private_home(
    tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("ROLO_TEST_SECRET_TOKEN", "must-not-leak")
    result = BoundedAdapterRunner().run(
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
