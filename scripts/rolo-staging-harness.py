"""Run the local staging-style bootstrap acceptance matrix.

This harness is deliberately offline: the tests use a deterministic fake transport,
so it exercises authority, signing, idempotency, cleanup and rollback without a host.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=Path("reports/staging-bootstrap.xml"))
    parser.add_argument("--basetemp", type=Path, default=Path(".staging-tmp"))
    args = parser.parse_args()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "tests/test_bootstrap_execution.py",
        "tests/test_jobs.py",
        "tests/test_companion_package.py",
        f"--basetemp={args.basetemp}",
        f"--junitxml={args.report}",
    ]
    environment = os.environ.copy()
    source = str(Path(__file__).resolve().parents[1] / "src")
    environment["PYTHONPATH"] = os.pathsep.join(
        item for item in (source, environment.get("PYTHONPATH")) if item
    )
    completed = subprocess.run(command, check=False, env=environment)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
