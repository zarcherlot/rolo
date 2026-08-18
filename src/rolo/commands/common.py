from __future__ import annotations

import json

import typer


def emit(value: object) -> None:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")  # type: ignore[union-attr]
    typer.echo(json.dumps(value, ensure_ascii=False, indent=2, default=str))
