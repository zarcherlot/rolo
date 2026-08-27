"""Minimal release smoke checks for the product entrypoints."""

from __future__ import annotations

import importlib
from pathlib import Path

try:  # Python 3.10 uses the declared tomli compatibility dependency.
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python 3.10 only
    import tomli as tomllib

from pydantic import BaseModel, Field


class ReleaseCheckResult(BaseModel):
    schema_version: str = "rolo-release-check/v1"
    status: str
    checks: list[str] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)


def run_release_check(pyproject_path: Path | None = None) -> ReleaseCheckResult:
    checks: list[str] = []
    failures: list[str] = []
    for module in (
        "rolo.product_cli",
        "rolo.api",
        "rolo.natural_service",
        "rolo.query_adapter",
    ):
        try:
            importlib.import_module(module)
            checks.append(f"import:{module}")
        except Exception as exc:  # pragma: no cover - defensive release boundary
            failures.append(f"import:{module}: {exc}")
    try:
        api = importlib.import_module("rolo.api").app
        route_paths = {route.path for route in api.routes}
        for path in ("/v1/jobs", "/v1/jobs/{job_id}", "/v1/jobs/{job_id}/events"):
            if path not in route_paths:
                failures.append(f"missing API route: {path}")
            else:
                checks.append(f"api-route:{path}")
    except Exception as exc:  # pragma: no cover - defensive release boundary
        failures.append(f"api-routes: {exc}")
    path = pyproject_path or Path(__file__).resolve().parents[2] / "pyproject.toml"
    if path.is_file():
        try:
            scripts = tomllib.loads(path.read_text(encoding="utf-8"))["project"]["scripts"]
            for name in ("rolo", "robotctl"):
                if name not in scripts:
                    failures.append(f"missing console script: {name}")
                else:
                    checks.append(f"console-script:{name}")
        except (OSError, KeyError, TypeError, tomllib.TOMLDecodeError) as exc:
            failures.append(f"pyproject: {exc}")
    else:
        failures.append(f"missing pyproject: {path}")
    return ReleaseCheckResult(
        status="PASS" if not failures else "FAIL",
        checks=checks,
        failures=failures,
    )
