from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from rolo.doctor import _probe_adapter_sandbox


def test_adapter_sandbox_probe_requires_successful_self_test(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    launcher = tmp_path / "sandbox"
    launcher.write_text("launcher", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="namespace denied")

    monkeypatch.setattr("rolo.doctor.sys.platform", "linux")
    monkeypatch.setattr("rolo.doctor.subprocess.run", fake_run)

    with pytest.raises(ValueError, match="sandbox self-test failed: namespace denied"):
        _probe_adapter_sandbox(launcher)

    assert captured["command"] == [str(launcher), "--self-test"]
    assert captured["kwargs"]["timeout"] == 10
