from __future__ import annotations

import time
from typing import Annotated

import httpx
import typer

from rolo.commands.common import emit
from rolo.core.config import get_settings
from rolo.doctor import build_doctor_report
from rolo.runtime import create_runtime
from rolo.stages.adapt.enrollment import EnrollmentService


def register_runtime_commands(root: typer.Typer) -> None:
    @root.command()
    def doctor() -> None:
        """Check local prerequisites and canonical configuration."""
        report = build_doctor_report()
        emit(report)
        if report["status"] != "READY":
            raise typer.Exit(code=1)

    @root.command("init")
    def initialize(
        robot_id: Annotated[str, typer.Option("--robot-id", help="User-assigned robot identity")],
    ) -> None:
        """Register identity and validate the installed runtime environment."""
        settings = get_settings()
        try:
            enrollment = EnrollmentService(config_root=settings.rolo_config_dir).enroll(
                robot_id=robot_id,
            )
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc

        doctor_result = build_doctor_report(settings)
        try:
            registered_robots = [
                robot.model_dump(mode="json")
                for robot in create_runtime(settings).registry.list()
            ]
        except Exception as exc:
            registered_robots = []
            doctor_result["status"] = "NOT_READY"
            doctor_result.setdefault("errors", []).append(str(exc))  # type: ignore[union-attr]
        ready = bool(
            doctor_result["status"] == "READY"
            and len(registered_robots) == 1
            and registered_robots[0]["robot_id"] == robot_id
        )
        emit(
            {
                "status": "READY_FOR_DISCOVERY" if ready else "NOT_READY",
                "robot_id": robot_id,
                "registration": {
                    "status": enrollment.status,
                    "capability_path": str(enrollment.capability_path),
                },
                "doctor": doctor_result,
                "robots": registered_robots,
                "next_step": (
                    f'uv run robotctl adapt discover run --robot "{robot_id}" '
                    "--urdf /path/to/your_robot.urdf "
                    "--source-root /path/to/robot-application"
                ),
                "motion_safety_status": "UNAPPROVED",
            }
        )
        if not ready:
            raise typer.Exit(code=1)

    @root.command()
    def serve(
        host: Annotated[str | None, typer.Option(help="Bind host")] = None,
        port: Annotated[int | None, typer.Option(help="Bind port")] = None,
        reload: Annotated[bool, typer.Option(help="Enable development reload")] = False,
    ) -> None:
        """Start the local control-plane API."""
        import uvicorn

        settings = get_settings()
        uvicorn.run(
            "rolo.api:app",
            host=host or settings.rolo_host,
            port=port or settings.rolo_port,
            reload=reload,
        )

    @root.command()
    def bootstrap_agentd(
        robot: Annotated[str, typer.Option("--robot")],
        host: Annotated[str, typer.Option(help="Bind host")] = "127.0.0.1",
        port: Annotated[int, typer.Option(help="Bind port")] = 8100,
    ) -> None:
        """Start the minimal non-motion daemon required before discovery."""
        import uvicorn

        from rolo.agentd import create_bootstrap_agentd_app

        uvicorn.run(create_bootstrap_agentd_app(robot), host=host, port=port)

    @root.command()
    def bootstrap_wait(
        robot: Annotated[str, typer.Option("--robot")],
        url: Annotated[str, typer.Option(help="Bootstrap agentd base URL")],
        timeout: Annotated[float, typer.Option(min=0.1, help="Maximum wait in seconds")] = 15.0,
    ) -> None:
        """Wait until the expected robot's bootstrap daemon is ready for discovery."""
        deadline = time.monotonic() + timeout
        health_url = f"{url.rstrip('/')}/health"
        last_error = "bootstrap agentd did not respond"
        while time.monotonic() < deadline:
            try:
                response = httpx.get(health_url, timeout=min(1.0, timeout))
                payload = response.json()
                if (
                    response.status_code == 200
                    and payload.get("robot_id") == robot
                    and payload.get("phase") == "BOOTSTRAP_READY"
                ):
                    emit({"status": "READY", "robot_id": robot, "url": url})
                    return
                last_error = (
                    f"unexpected bootstrap health response: {response.status_code} {payload}"
                )
            except (httpx.HTTPError, ValueError) as exc:
                last_error = str(exc)
            time.sleep(0.2)
        emit({"status": "NOT_READY", "robot_id": robot, "url": url, "error": last_error})
        raise typer.Exit(code=1)

    @root.command()
    def agentd(
        robot: Annotated[str, typer.Option("--robot")],
        host: Annotated[str, typer.Option(help="Bind host")] = "127.0.0.1",
        port: Annotated[int, typer.Option(help="Bind port")] = 8101,
    ) -> None:
        """Start the full robot-agentd after discovery has completed."""
        import uvicorn

        from rolo.agentd import create_agentd_app

        uvicorn.run(create_agentd_app(robot), host=host, port=port)
