from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

from rolo.adapter_runner import BoundedAdapterRunner

pytestmark = pytest.mark.skipif(
    sys.platform != "linux" or shutil.which("bwrap") is None,
    reason="the bundled production sandbox requires Linux and bubblewrap",
)


def test_bundled_production_sandbox_runs_describe_without_host_file_access(
    tmp_path: Path,
) -> None:
    release = tmp_path / "release"
    release.mkdir()
    secret = tmp_path / "controller-secret.txt"
    secret.write_text("must-not-be-visible", encoding="utf-8")
    package = release / "adapter.py"
    package.write_text(
        "import json, os, pathlib, sys\n"
        f"secret = pathlib.Path({str(secret)!r})\n"
        "visible = secret.exists()\n"
        "home = pathlib.Path(os.environ['HOME'])\n"
        "(home / 'sandbox-write.txt').write_text('ok', encoding='utf-8')\n"
        "if sys.argv[1] == 'describe':\n"
        "    print(json.dumps({'operations': {'app.demo': 'adapter.py'}, "
        "'host_secret_visible': visible, 'sandbox_home': str(home)}))\n",
        encoding="utf-8",
    )
    launcher = Path(__file__).resolve().parents[1] / "scripts" / "rolo-adapter-sandbox"

    completed = BoundedAdapterRunner(
        sandbox_launcher=launcher,
        allow_unsandboxed_development=False,
    ).run(
        [sys.executable, str(package), "describe"],
        cwd=release,
        timeout_s=10,
    )

    assert completed.returncode == 0, completed.stderr
    described = json.loads(completed.stdout)
    assert described["operations"] == {"app.demo": "adapter.py"}
    assert described["host_secret_visible"] is False
    assert described["sandbox_home"] == "/home/rolo"


def test_bundled_production_sandbox_mounts_only_observed_path_directories(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release = tmp_path / "release"
    release.mkdir()
    target_bin = tmp_path / "target-venv/bin"
    target_bin.mkdir(parents=True)
    (target_bin.parent / "pyvenv.cfg").write_text(
        f"home = {Path(sys.base_prefix) / 'bin'}\n"
        "include-system-site-packages = false\n"
        f"version = {sys.version_info.major}.{sys.version_info.minor}\n",
        encoding="utf-8",
    )
    (target_bin / "python").symlink_to(Path(sys.executable).resolve())
    editable_source = tmp_path / "editable-source"
    editable_source.mkdir()
    (editable_source / "observed_module.py").write_text(
        "VALUE = 'observed-target'\n", encoding="utf-8"
    )
    site_packages = (
        target_bin.parent
        / f"lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages"
    )
    site_packages.mkdir(parents=True)
    (site_packages / "observed-editable.pth").write_text(
        str(editable_source), encoding="utf-8"
    )
    target = target_bin / "observed-cli"
    target.write_text(
        f"#!{target_bin / 'python'}\n"
        "from observed_module import VALUE\n"
        "print(VALUE, end='')\n",
        encoding="utf-8",
    )
    target.chmod(0o755)
    secret = tmp_path / "controller-secret.txt"
    secret.write_text("must-not-be-visible", encoding="utf-8")
    package = release / "adapter.py"
    package.write_text(
        "import json, pathlib, subprocess\n"
        f"secret = pathlib.Path({str(secret)!r})\n"
        "completed = subprocess.run(['observed-cli'], capture_output=True, text=True, check=True)\n"
        "print(json.dumps({'stdout': completed.stdout, 'host_secret_visible': secret.exists()}))\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(
        "PATH",
        os.pathsep.join([str(target_bin), "/usr/local/bin", "/usr/bin", "/bin"]),
    )
    launcher = Path(__file__).resolve().parents[1] / "scripts" / "rolo-adapter-sandbox"

    completed = BoundedAdapterRunner(
        sandbox_launcher=launcher,
        allow_unsandboxed_development=False,
    ).run(
        [sys.executable, str(package)],
        cwd=release,
        timeout_s=10,
        runtime_environment={
            "PATH": str(target_bin),
            "PYTHONPATH": str(editable_source),
        },
    )

    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result == {"stdout": "observed-target", "host_secret_visible": False}


def test_bundled_production_sandbox_runs_selected_virtualenv_cli_directly(
    tmp_path: Path,
) -> None:
    release = tmp_path / "release"
    release.mkdir()
    base_python_bin = tmp_path / "managed-python/bin"
    base_python_bin.mkdir(parents=True)
    (base_python_bin / "python").symlink_to(Path(sys.executable).resolve())
    target_bin = tmp_path / "target-venv/bin"
    target_bin.mkdir(parents=True)
    (target_bin.parent / "pyvenv.cfg").write_text(
        f"home = {base_python_bin}\n"
        "include-system-site-packages = false\n"
        f"version = {sys.version_info.major}.{sys.version_info.minor}\n",
        encoding="utf-8",
    )
    (target_bin / "python").symlink_to(base_python_bin / "python")
    target = target_bin / "observed-cli"
    target.write_text(
        f"#!{target_bin / 'python'}\n"
        "print('direct-observed-target', end='')\n",
        encoding="utf-8",
    )
    target.chmod(0o755)
    launcher = Path(__file__).resolve().parents[1] / "scripts" / "rolo-adapter-sandbox"

    completed = BoundedAdapterRunner(
        sandbox_launcher=launcher,
        allow_unsandboxed_development=False,
    ).run(
        [str(target), "--help"],
        cwd=release,
        timeout_s=10,
        runtime_environment={"PATH": str(target_bin)},
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == "direct-observed-target"
