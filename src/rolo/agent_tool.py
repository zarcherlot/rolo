from __future__ import annotations

import typer

from rolo.commands.adapt_tools import register_adapt_query_commands

app = typer.Typer(help="Read-only, discovery-pinned knowledge tools for an Adapter Agent.")
adapt_app = typer.Typer(help="Read-only Adapt knowledge queries.")
register_adapt_query_commands(adapt_app)
app.add_typer(adapt_app, name="adapt")


if __name__ == "__main__":
    app()
