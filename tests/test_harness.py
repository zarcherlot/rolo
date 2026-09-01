from __future__ import annotations

import io
from pathlib import Path

import pytest

from rolo.harness import (
    CodexHarness,
    HarnessError,
    HarnessRequest,
    ModelHarness,
    available_harnesses,
    create_harness,
    register_harness,
)


def test_harness_registration_and_codex_command_validation(tmp_path: Path) -> None:
    class FakeHarness(ModelHarness):
        def run(self, request, *, on_output=None):
            return request.prompt, "", 0

    name = "unit-harness"
    register_harness(name, lambda **kwargs: FakeHarness())
    assert name in available_harnesses()
    assert create_harness(name, settings=object()).run(HarnessRequest("p", tmp_path))[0] == "p"
    with pytest.raises(ValueError, match="non-empty token"):
        register_harness("bad name", lambda **kwargs: FakeHarness())
    with pytest.raises(ValueError, match="already registered"):
        register_harness(name, lambda **kwargs: FakeHarness())
    with pytest.raises(HarnessError, match="unsupported model harness"):
        create_harness("missing", settings=object())
    register_harness("not-a-harness", lambda **kwargs: object())
    with pytest.raises(HarnessError, match="does not implement"):
        create_harness("not-a-harness", settings=object())

    command = CodexHarness(executable="codex", model="m")._command()
    assert command[-1] == "-"
    with pytest.raises(HarnessError, match="requires a base URL"):
        CodexHarness(provider="custom")._command()
    with pytest.raises(HarnessError, match="absolute HTTP"):
        CodexHarness(base_url="not-a-url")._command()
    configured = CodexHarness(
        provider="custom", base_url="https://api.example/v1", api_key="key"
    )._command()
    assert "CODEX_API_KEY" in " ".join(configured)


class _FakeProcess:
    def __init__(self, *, returncode: int = 0, wait_error: BaseException | None = None) -> None:
        class Input(io.StringIO):
            def close(self):
                self.closed_for_test = True

        self.stdin = Input()
        self.stdout = io.StringIO("out\n")
        self.stderr = io.StringIO("err\n")
        self.returncode = returncode
        self.wait_error = wait_error
        self.killed = False

    def wait(self, timeout=None):
        del timeout
        if self.wait_error:
            error, self.wait_error = self.wait_error, None
            raise error
        return self.returncode

    def kill(self):
        self.killed = True


def test_codex_harness_run_streams_and_sanitizes_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    process = _FakeProcess(returncode=3)
    captured: dict[str, object] = {}

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["env"] = kwargs["env"]
        return process

    monkeypatch.setattr("rolo.harness.subprocess.Popen", fake_popen)
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-forward")
    output: list[tuple[str, str]] = []
    stdout, stderr, code = CodexHarness(api_key="codex-key").run(
        HarnessRequest("hello", tmp_path),
        on_output=lambda stream, line: output.append((stream, line)),
    )
    assert (stdout, stderr, code) == ("out\n", "err\n", 3)
    assert output == [("stdout", "out"), ("stderr", "err")]
    assert captured["env"]["CODEX_API_KEY"] == "codex-key"
    assert "OPENAI_API_KEY" not in captured["env"]
    assert (tmp_path / "AGENTS.md").is_file()
    assert process.stdin.getvalue() == "hello"

    with pytest.raises(ValueError, match="at least one second"):
        CodexHarness().run(HarnessRequest("x", tmp_path, timeout_s=0))


def test_codex_harness_run_maps_start_and_timeout_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def start_error(*args, **kwargs):
        del args, kwargs
        raise OSError("not found")

    monkeypatch.setattr("rolo.harness.subprocess.Popen", start_error)
    with pytest.raises(HarnessError, match="could not start Codex"):
        CodexHarness().run(HarnessRequest("x", tmp_path))

    process = _FakeProcess(wait_error=__import__("subprocess").TimeoutExpired("codex", 1))
    monkeypatch.setattr("rolo.harness.subprocess.Popen", lambda *args, **kwargs: process)
    with pytest.raises(HarnessError, match="exceeded the"):
        CodexHarness().run(HarnessRequest("x", tmp_path, timeout_s=1))
    assert process.killed is True
