from __future__ import annotations

import json
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
        "'host_secret_visible': visible}))\n",
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
