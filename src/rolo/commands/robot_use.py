from __future__ import annotations

import asyncio
import base64
import mimetypes
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated

import typer

from rolo.commands.common import emit
from rolo.core.models import ImageFrame, RobotUseRequest
from rolo.runtime import create_runtime

robot_use_app = typer.Typer(help="Run robot_use semantic visual supervision.")


def image_to_data_url(path: Path) -> str:
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


@robot_use_app.command("poll")
def robot_use_poll(
    robot: Annotated[str, typer.Option("--robot")],
    image: Annotated[list[Path], typer.Option("--image", exists=True, dir_okay=False)],
    execution_id: Annotated[str, typer.Option()] = "local-execution",
    task: Annotated[str, typer.Option()] = "Observe whether robot behavior matches the task",
    commanded_speed_mps: Annotated[float, typer.Option()] = 0.0,
    progress_delta: Annotated[float, typer.Option()] = 1.0,
) -> None:
    """Submit a timestamped storyboard to the configured robot_use backend."""
    if not image:
        raise typer.BadParameter("At least one --image is required")
    runtime = create_runtime()
    now = datetime.now(timezone.utc)
    request = RobotUseRequest(
        request_id=f"local-{int(now.timestamp() * 1000)}",
        robot_id=robot,
        execution_id=execution_id,
        window_start=now - timedelta(seconds=max(len(image) - 1, 1)),
        window_end=now,
        frames=[
            ImageFrame(
                timestamp=now - timedelta(seconds=len(image) - index - 1),
                image_url=image_to_data_url(path),
            )
            for index, path in enumerate(image)
        ],
        task_contract={"intent": task},
        telemetry_summary={
            "commanded_speed_mps": commanded_speed_mps,
            "progress_delta": progress_delta,
        },
    )
    result = asyncio.run(runtime.robot_use.poll(request))
    emit(result)
