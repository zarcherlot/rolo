from __future__ import annotations

import typer

from rolo.commands.canonical import (
    application_app,
    hw_app,
    linux_app,
    middleware_app,
    ros_app,
    tool_app,
)
from rolo.commands.discovery import discover_app
from rolo.commands.lifecycle import (
    adapt_stage_app,
    diagnose_stage_app,
    register_lifecycle_commands,
)
from rolo.commands.robot_use import robot_use_app
from rolo.commands.runtime import register_runtime_commands
from rolo.commands.schema import schema_app

app = typer.Typer(help="Canonical local CLI for the rolo development harness.")

register_runtime_commands(app)
register_lifecycle_commands(app)
adapt_stage_app.add_typer(discover_app, name="discover")
diagnose_stage_app.add_typer(robot_use_app, name="robot-use")
app.add_typer(schema_app, name="schema")
app.add_typer(tool_app, name="tool")
app.add_typer(hw_app, name="hw")
app.add_typer(linux_app, name="linux")
app.add_typer(middleware_app, name="middleware")
app.add_typer(ros_app, name="ros")
app.add_typer(application_app, name="app")


if __name__ == "__main__":
    app()
