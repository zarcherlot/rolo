"""Small bounded helpers shared by target Probe evidence collection.

The v2 Agent does its own planning. This module deliberately contains only the
safe executable-help probe and the Probe mode marker; source discovery and
heuristic operation mapping were removed from the product path.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import time
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

MAX_HELP_BYTES = 250_000
MAX_HELP_SECONDS = 10.0


class ActiveProbeMode(str, Enum):
    NONE = "none"
    HELP = "help"
    RUNTIME_READONLY = "runtime-readonly"


class HelpProbeStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    UNAVAILABLE = "UNAVAILABLE"


class HelpProbeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: HelpProbeStatus
    returncode: int | None = None
    duration_ms: float = Field(default=0.0, ge=0)
    output_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    output_bytes: int = Field(default=0, ge=0, le=MAX_HELP_BYTES)
    error: str | None = None


def run_bounded_help(executable: Path, output_path: Path) -> HelpProbeResult:
    """Run a bounded self-description probe without shell interpolation.

    ``--help`` is preferred. When a CLI does not implement it, a fixed
    ``--version`` fallback is attempted; arbitrary arguments are never inferred.
    """

    if not executable.is_file():
        return HelpProbeResult(status=HelpProbeStatus.UNAVAILABLE, error="executable is missing")
    started = time.monotonic()
    completed = None
    output = b""
    last_error: str | None = None
    for argument in ("--help", "--version"):
        try:
            completed = subprocess.run(
                [str(executable), argument],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                check=False,
                timeout=MAX_HELP_SECONDS,
                env={"PATH": os.environ.get("PATH", "")},
            )
        except subprocess.TimeoutExpired:
            return HelpProbeResult(
                status=HelpProbeStatus.TIMEOUT,
                duration_ms=round((time.monotonic() - started) * 1000, 3),
                error=f"{argument} probe timed out",
            )
        except OSError as exc:
            last_error = str(exc)
            continue
        output = (completed.stdout or b"") + (completed.stderr or b"")
        if completed.returncode == 0 and output.strip():
            break
        last_error = f"{argument} returned a non-zero or empty response"
    if completed is None:
        return HelpProbeResult(
            status=HelpProbeStatus.FAILED,
            duration_ms=round((time.monotonic() - started) * 1000, 3),
            error=last_error or "self-description probe failed",
        )
    output = output[:MAX_HELP_BYTES]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(output)
    return HelpProbeResult(
        status=(
            HelpProbeStatus.SUCCEEDED
            if completed.returncode == 0 and output
            else HelpProbeStatus.FAILED
        ),
        returncode=completed.returncode,
        duration_ms=round((time.monotonic() - started) * 1000, 3),
        output_sha256=hashlib.sha256(output).hexdigest(),
        output_bytes=len(output),
        error=None if completed.returncode == 0 and output else last_error,
    )


def _extract_help_summary(text: str) -> tuple[list[str], list[str], list[str]]:
    """Extract conservative, non-semantic help hints for signed evidence."""

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    usage = [line for line in lines if line.lower().startswith(("usage:", "synopsis:"))][:8]
    subcommands: list[str] = []
    parameters: list[str] = []
    for line in lines[:512]:
        token = line.split()[0] if line.split() else ""
        if token.startswith("-"):
            parameters.append(token[:128])
        elif len(line.split()) == 1 and token.isidentifier():
            subcommands.append(token[:128])
    return sorted(set(usage)), sorted(set(parameters)), sorted(set(subcommands))


# Kept as a small data marker for callers that need to describe an optional
# source probe. It is not an operation registry or an Agent planning model.
class ActiveDiscoveryInputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active_probe: ActiveProbeMode = ActiveProbeMode.RUNTIME_READONLY
