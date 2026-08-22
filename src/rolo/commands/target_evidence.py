from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import typer

from rolo.commands.common import emit
from rolo.core.config import get_settings
from rolo.stages.adapt.target_evidence import (
    CollectorDescriptor,
    EvidenceDeploymentMode,
    TargetEvidenceBundle,
    TargetEvidenceRequest,
    collect_over_ssh,
    collect_target_evidence,
    configure_deployment,
    initialize_collector,
    load_collector_state,
    load_deployment,
    new_request,
    verify_evidence_bundle,
)

target_evidence_app = typer.Typer(
    help="Configure and collect target-bound, read-only Adapt evidence."
)


def deployment_path(robot_id: str) -> Path:
    return get_settings().rolo_config_dir / "target-evidence" / f"{robot_id}.json"


@target_evidence_app.command("collector-init")
def collector_init(
    robot_id: Annotated[str, typer.Option("--robot-id", "--robot")],
    config: Annotated[
        Path,
        typer.Option("--config", help="Target-local collector state path"),
    ] = Path(".rolo/config/target-evidence-collector.json"),
    secret_file: Annotated[
        Path,
        typer.Option("--secret-file", help="Target-local 0600 signing secret"),
    ] = Path(".rolo/config/target-evidence-collector.key"),
    descriptor_out: Annotated[
        Path | None,
        typer.Option("--descriptor-out", help="Non-secret descriptor for the controller"),
    ] = None,
) -> None:
    """Initialize the target-side collector and print its pinned identity."""
    try:
        descriptor = initialize_collector(
            robot_id=robot_id,
            state_path=config,
            secret_path=secret_file,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if descriptor_out is not None:
        descriptor_out.parent.mkdir(parents=True, exist_ok=True)
        descriptor_out.write_text(descriptor.model_dump_json(indent=2) + "\n", encoding="utf-8")
    emit(
        {
            "status": "COLLECTOR_READY",
            "descriptor": descriptor.model_dump(mode="json"),
            "descriptor_path": str(descriptor_out) if descriptor_out else None,
            "secret_path": str(secret_file.resolve()),
            "warning": "Provision the secret to the controller through a separate secure channel.",
            "access": "READ_ONLY",
        }
    )


@target_evidence_app.command("configure")
def configure(
    robot_id: Annotated[str, typer.Option("--robot-id", "--robot")],
    mode: Annotated[EvidenceDeploymentMode, typer.Option("--mode")],
    descriptor_path: Annotated[
        Path, typer.Option("--collector-descriptor", help="Pinned collector descriptor JSON")
    ],
    verification_secret: Annotated[
        Path,
        typer.Option("--verification-secret", help="Securely provisioned collector secret"),
    ],
    ssh_target: Annotated[str | None, typer.Option("--ssh-target")] = None,
    known_hosts: Annotated[
        Path | None,
        typer.Option("--known-hosts", help="Pinned SSH known_hosts file; required remotely"),
    ] = None,
    collector_config: Annotated[
        str,
        typer.Option("--collector-config", help="Collector state path on the target"),
    ] = ".rolo/config/target-evidence-collector.json",
    output: Annotated[Path | None, typer.Option("--output")] = None,
) -> None:
    """Select local or remote evidence mode for this Rolo installation."""
    try:
        descriptor = CollectorDescriptor.model_validate_json(
            descriptor_path.read_text(encoding="utf-8")
        )
        result = configure_deployment(
            robot_id=robot_id,
            mode=mode,
            descriptor=descriptor,
            verification_secret_path=verification_secret,
            output_path=output or deployment_path(robot_id),
            ssh_target=ssh_target,
            known_hosts_path=known_hosts,
            collector_config=collector_config,
            local_collector_state_path=(
                Path(collector_config) if mode == EvidenceDeploymentMode.LOCAL else None
            ),
        )
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(
        {
            "status": "TARGET_EVIDENCE_CONFIGURED",
            "deployment": result.model_dump(mode="json"),
            "next": f"robotctl target-evidence collect --robot {robot_id}",
        }
    )


@target_evidence_app.command("collector-run", hidden=True)
def collector_run(
    config: Annotated[Path, typer.Option("--config")],
) -> None:
    """Run one target-side, stdin/stdout, read-only evidence request."""
    try:
        raw = sys.stdin.buffer.read(64_001)
        if len(raw) > 64_000:
            raise ValueError("target evidence request exceeded its size limit")
        request = TargetEvidenceRequest.model_validate_json(raw)
        bundle = collect_target_evidence(request, load_collector_state(config))
    except (OSError, ValueError) as exc:
        typer.echo(json.dumps({"status": "REJECTED", "error": str(exc)}), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(bundle.model_dump_json())


@target_evidence_app.command("collect")
def collect(
    robot_id: Annotated[str, typer.Option("--robot-id", "--robot")],
    deployment_config: Annotated[Path | None, typer.Option("--deployment-config")] = None,
    collector_state: Annotated[
        Path | None,
        typer.Option("--collector-state", help="Required only for local mode"),
    ] = None,
    output: Annotated[Path | None, typer.Option("--output")] = None,
    timeout: Annotated[float, typer.Option("--timeout", min=1.0, max=300.0)] = 45.0,
) -> None:
    """Collect and verify one fresh target evidence bundle."""
    try:
        deployment = load_deployment(deployment_config or deployment_path(robot_id))
        request = new_request(robot_id)
        if deployment.mode == EvidenceDeploymentMode.LOCAL:
            state_path = collector_state or Path(deployment.local_collector_state_path or "")
            bundle = collect_target_evidence(request, load_collector_state(state_path))
        else:
            bundle = collect_over_ssh(deployment, request, timeout_s=timeout)
        verify_evidence_bundle(bundle, deployment=deployment, request=request)
        destination = output or (
            get_settings().rolo_artifact_dir
            / "target-evidence"
            / robot_id
            / f"{request.nonce}.json"
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(bundle.model_dump_json(indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit(
        {
            "status": "VERIFIED",
            "robot_id": robot_id,
            "mode": deployment.mode.value,
            "collector_id": bundle.collector_id,
            "target_host_fingerprint": bundle.target_host_fingerprint,
            "access": bundle.access,
            "bundle": str(destination),
            "next": (
                f"robotctl adapt discover run --robot {robot_id} "
                f"--target-evidence-bundle {destination}"
            ),
        }
    )


def load_verified_probes(
    *, robot_id: str, bundle_path: Path, deployment_config: Path | None = None
) -> dict[str, object]:
    deployment = load_deployment(deployment_config or deployment_path(robot_id))
    bundle = TargetEvidenceBundle.model_validate_json(bundle_path.read_text(encoding="utf-8"))
    return verify_evidence_bundle(bundle, deployment=deployment)
