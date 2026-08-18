from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from rolo.commands.common import emit
from rolo.schema_export import export_canonical_schemas

schema_app = typer.Typer(help="Export and inspect canonical JSON schemas.")


@schema_app.command("export")
def export_schemas(
    output: Annotated[Path, typer.Option(help="Schema output directory")] = Path("schemas"),
) -> None:
    """Export the canonical JSON schemas."""
    written = export_canonical_schemas(output)
    emit({"status": "SUCCEEDED", "written": [str(path) for path in written]})
