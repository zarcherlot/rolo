from __future__ import annotations

import ipaddress
import time
from pathlib import Path
from typing import Annotated

import httpx
import typer

from rolo import __version__
from rolo.commands.common import emit
from rolo.core.config import get_settings
from rolo.doctor import build_doctor_report
from rolo.runtime import create_runtime
from rolo.stages.adapt.enrollment import EnrollmentService
from rolo.stages.adapt.target_evidence import (
    CollectorDescriptor,
    EvidenceDeploymentMode,
    configure_deployment,
    ensure_local_deployment,
)

runtime_app = typer.Typer(help="Inspect the local Rolo runtime without starting services.")


@runtime_app.command("health")
def runtime_health() -> None:
    """Read local runtime readiness and registered robot count."""
    try:
        runtime = create_runtime()
        emit(
            {
                "status": "HEALTHY",
                "version": __version__,
                "registered_robots": len(runtime.registry),
                "artifact_root": str(runtime.artifacts.root),
            }
        )
    except (OSError, ValueError) as exc:
        emit({"status": "UNAVAILABLE", "version": __version__, "error": str(exc)})
        raise typer.Exit(code=1) from exc


@runtime_app.command("version")
def runtime_version() -> None:
    """Read the installed Rolo product and contract protocol versions."""
    emit(
        {
            "status": "SUCCEEDED",
            "version": __version__,
            "operation_contract_schema": "robot-operation-contract/v1",
            "adapter_protocol": "robot-adapter-rpc/v1",
            "tool_catalog_schema": "robot-tool-catalog/v1",
        }
    )


def register_runtime_commands(root: typer.Typer) -> None:
    root.add_typer(runtime_app, name="runtime")
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
        evidence_mode: Annotated[
            EvidenceDeploymentMode,
            typer.Option(
                "--evidence-mode",
                help="local runs probes on this target; remote uses a pinned target collector",
            ),
        ] = EvidenceDeploymentMode.LOCAL,
        collector_descriptor: Annotated[
            Path | None,
            typer.Option(
                "--collector-descriptor", help="Remote collector descriptor from collector-init"
            ),
        ] = None,
        verification_secret: Annotated[
            Path | None,
            typer.Option(
                "--verification-secret", help="Collector secret provisioned separately"
            ),
        ] = None,
        ssh_target: Annotated[str | None, typer.Option("--ssh-target")] = None,
        known_hosts: Annotated[
            Path | None,
            typer.Option("--known-hosts", help="Pinned known_hosts file for remote mode"),
        ] = None,
        ssh_port: Annotated[int | None, typer.Option("--ssh-port", min=1, max=65535)] = None,
        ssh_identity_file: Annotated[
            Path | None,
            typer.Option("--ssh-identity-file", help="Pinned controller-side SSH private key"),
        ] = None,
        collector_config: Annotated[
            str,
            typer.Option("--collector-config", help="Collector state path on the target"),
        ] = ".rolo/config/target-evidence-collector.json",
        collector_executable: Annotated[
            str | None,
            typer.Option(
                "--collector-executable",
                help="Pinned robotctl executable name or absolute path on the remote target",
            ),
        ] = None,
    ) -> None:
        """Register identity and validate the installed runtime environment."""
        settings = get_settings()
        deployment_root = settings.rolo_config_dir / "target-evidence"
        deployment_path = deployment_root / f"{robot_id}.json"
        try:
            if evidence_mode == EvidenceDeploymentMode.LOCAL:
                if any(
                    value is not None
                    for value in (
                        collector_descriptor,
                        verification_secret,
                        ssh_target,
                        known_hosts,
                        ssh_port,
                        ssh_identity_file,
                        collector_executable,
                    )
                ):
                    raise ValueError("local evidence mode does not accept remote collector options")
                deployment, _ = ensure_local_deployment(
                    robot_id=robot_id,
                    config_root=settings.rolo_config_dir,
                )
            else:
                if not all(
                    value is not None
                    for value in (
                        collector_descriptor,
                        verification_secret,
                        ssh_target,
                        known_hosts,
                    )
                ):
                    raise ValueError(
                        "remote evidence mode requires --collector-descriptor, "
                        "--verification-secret, --ssh-target, and --known-hosts"
                    )
                descriptor = CollectorDescriptor.model_validate_json(
                    collector_descriptor.read_text(encoding="utf-8")
                )
                deployment = configure_deployment(
                    robot_id=robot_id,
                    mode=evidence_mode,
                    descriptor=descriptor,
                    verification_secret_path=verification_secret,
                    output_path=deployment_path,
                    ssh_target=ssh_target,
                    known_hosts_path=known_hosts,
                    ssh_port=ssh_port,
                    ssh_identity_file=ssh_identity_file,
                    collector_config=collector_config,
                    collector_executable=collector_executable or "robotctl",
                )
            enrollment = EnrollmentService(config_root=settings.rolo_config_dir).enroll(
                robot_id=robot_id,
            )
        except (OSError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        doctor_result = build_doctor_report(settings)
        try:
            registered_robots = [
                robot.model_dump(mode="json") for robot in create_runtime(settings).registry.list()
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
                "target_evidence": deployment.model_dump(mode="json"),
                "doctor": doctor_result,
                "robots": registered_robots,
                "next_step": (
                    f'robotctl target-evidence collect --robot "{robot_id}"'
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
        bind_host = host or settings.rolo_host
        try:
            loopback = bind_host.casefold() == "localhost" or ipaddress.ip_address(
                bind_host
            ).is_loopback
        except ValueError:
            loopback = False
        if not loopback and not settings.rolo_api_token:
            raise typer.BadParameter(
                "non-loopback API binding requires ROLO_API_TOKEN"
            )
        uvicorn.run(
            "rolo.api:app",
            host=bind_host,
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
