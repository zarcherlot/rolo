from __future__ import annotations

import typer

from rolo.commands.adapt_tools import register_adapt_query_commands
from rolo.commands.canonical import (
    application_app,
    hw_app,
    linux_app,
    middleware_app,
    ros_app,
    state_app,
    tool_app,
)
from rolo.commands.configuration import config_app
from rolo.commands.discovery import discover_app
from rolo.commands.lifecycle import (
    adapt_stage_app,
    register_lifecycle_commands,
)
from rolo.commands.runtime import register_runtime_commands
from rolo.commands.schema import schema_app
from rolo.commands.target_evidence import target_evidence_app

app = typer.Typer(help="Canonical local CLI for the rolo development harness.")

register_runtime_commands(app)
register_lifecycle_commands(app)
adapt_stage_app.add_typer(discover_app, name="discover")
register_adapt_query_commands(adapt_stage_app)
app.add_typer(schema_app, name="schema")
app.add_typer(tool_app, name="tool")
app.add_typer(hw_app, name="hw")
app.add_typer(linux_app, name="linux")
app.add_typer(middleware_app, name="middleware")
app.add_typer(ros_app, name="ros")
app.add_typer(application_app, name="app")
app.add_typer(state_app, name="state")
app.add_typer(target_evidence_app, name="target-evidence")
app.add_typer(config_app, name="config")


if __name__ == "__main__":
    app()
