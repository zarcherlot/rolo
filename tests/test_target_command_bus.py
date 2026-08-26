from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from rolo.cli import app
from rolo.commands import lifecycle
from rolo.core.config import Settings, get_settings
from rolo.stages.adapt.journey import ProjectEvidence
from rolo.targets import (
    AdaptStartParameters,
    ApplicationCommandBus,
    CommandEnvelope,
    CredentialPurpose,
    CredentialResolver,
    FileCredentialProvider,
    InteractionSurface,
    OrchestratorPlacement,
    ResolvedCredential,
    TargetConnectionProfile,
    TargetProfile,
    TargetProfileRegistry,
    TargetTransport,
    TargetTrustLevel,
    build_adapt_start_envelope,
    file_credential_reference,
    render_adapt_start_cli,
)


def _parameters(tmp_path: Path) -> AdaptStartParameters:
    project = tmp_path / "project"
    project.mkdir(exist_ok=True)
    return AdaptStartParameters(
        project_root=str(project.resolve()),
        timeout_s=15,
        evidence_mode="local",
    )


def test_target_registry_persists_strict_secret_free_profiles(tmp_path: Path) -> None:
    registry = TargetProfileRegistry(tmp_path / "profiles")
    connection = TargetConnectionProfile(
        connection_profile_id="conn-rover",
        host="rover.example",
        user="rolo-runtime",
        credential_ref="credential://ssh/rover-runtime",
        known_hosts_path=str((tmp_path / "known_hosts").resolve()),
        expected_host_key_sha256="SHA256:" + "A" * 43,
    )
    target = TargetProfile(
        target_id="rover",
        orchestrator_placement=OrchestratorPlacement.CONTROLLER,
        transport=TargetTransport.SSH,
        connection_profile_id=connection.connection_profile_id,
        workspace_root="/opt/robot/ws",
        desired_rolo_version="v0.2.0",
    )

    connection_path = registry.save_connection(connection)
    target_path = registry.save_target(target)

    assert registry.get_connection("conn-rover") == connection
    assert registry.get_target("rover") == target
    assert registry.list_connections() == [connection]
    assert registry.list_targets() == [target]
    persisted = f"{connection_path.read_text()}\n{target_path.read_text()}".casefold()
    assert "private_key" not in persisted
    assert "password" not in persisted
    assert "key_material" not in persisted
    assert not list(registry.root.rglob(".t*"))
    assert not list(registry.root.rglob(".l*"))


def test_target_registry_fails_closed_on_references_tampering_and_paths(
    tmp_path: Path,
) -> None:
    registry = TargetProfileRegistry(tmp_path / "profiles")
    local = TargetProfile(
        target_id="local",
        orchestrator_placement=OrchestratorPlacement.TARGET_LOCAL,
        transport=TargetTransport.LOCAL,
        workspace_root="/opt/robot/ws",
        desired_rolo_version="v0.2.0",
    )
    registry.save_target(local)
    payload = json.loads((registry.targets_dir / "local.json").read_text(encoding="utf-8"))
    payload["password"] = "must-not-load"
    (registry.targets_dir / "local.json").write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="secret-bearing field"):
        registry.get_target("local")
    with pytest.raises(ValueError, match="invalid target_id"):
        registry.get_target("../escape")
    with pytest.raises(FileNotFoundError):
        registry.save_target(
            TargetProfile(
                target_id="missing-connection",
                orchestrator_placement=OrchestratorPlacement.CONTROLLER,
                transport=TargetTransport.SSH,
                connection_profile_id="unknown",
                workspace_root="/opt/robot/ws",
                desired_rolo_version="v0.2.0",
            )
        )


def test_credential_spi_routes_refs_without_serializing_material(tmp_path: Path) -> None:
    secret = tmp_path / "collector.key"
    secret.write_text("super-secret-value", encoding="utf-8")
    reference = file_credential_reference(secret)
    resolver = CredentialResolver((FileCredentialProvider(),))

    credential = resolver.resolve(
        reference,
        purpose=CredentialPurpose.LEGACY_COLLECTOR_VERIFICATION,
    )

    assert credential.secret_path == secret.resolve()
    assert "super-secret-value" not in repr(credential)
    assert "super-secret-value" not in str(credential)
    assert "<redacted>" in repr(credential)
    with pytest.raises(ValueError, match="no credential provider"):
        CredentialResolver().resolve(
            "credential://ssh/rover",
            purpose=CredentialPurpose.SSH_RUNTIME,
        )


def test_credential_resolver_rejects_provider_confusion() -> None:
    class ConfusedProvider:
        schemes = frozenset({"credential"})

        def resolve(self, reference: str, *, purpose: CredentialPurpose) -> ResolvedCredential:
            return ResolvedCredential(
                reference="credential://ssh/different",
                purpose=purpose,
                secret_text="not-visible",
            )

    with pytest.raises(ValueError, match="different reference"):
        CredentialResolver((ConfusedProvider(),)).resolve(
            "credential://ssh/rover",
            purpose=CredentialPurpose.SSH_RUNTIME,
        )


def test_command_envelope_binds_parameters_and_renders_canonical_cli(tmp_path: Path) -> None:
    parameters = _parameters(tmp_path)
    envelope = build_adapt_start_envelope(
        target_id="rover",
        parameters=parameters,
        active_probe="none",
        run_adapter_agent=False,
    )
    bus = ApplicationCommandBus()
    bus.register(
        envelope.command.command,
        lambda item: item.command.canonical_sha256(),
        renderer=render_adapt_start_cli,
    )

    execution = bus.dispatch(envelope)

    assert execution.result == execution.command_sha256
    assert execution.canonical_cli.startswith("robotctl adapt start ")
    assert "--discover-only" in execution.canonical_cli
    assert parameters.project_root in execution.canonical_cli

    changed = parameters.model_copy(update={"timeout_s": 16})
    with pytest.raises(ValueError, match="parameter digest mismatch"):
        bus.dispatch(CommandEnvelope(command=envelope.command, parameters=changed))


def test_cli_and_direct_service_produce_the_same_command_digest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parameters = _parameters(tmp_path)
    settings = Settings(_env_file=None, coding_agent_timeout_s=15)
    monkeypatch.setattr(
        lifecycle,
        "_run_adapt_start",
        lambda envelope, *, settings: {"status": "DISCOVERY_COMPLETE"},
    )
    captured = []
    original_dispatch = ApplicationCommandBus.dispatch

    def record_dispatch(self, envelope):  # type: ignore[no-untyped-def]
        execution = original_dispatch(self, envelope)
        captured.append(execution)
        return execution

    monkeypatch.setattr(ApplicationCommandBus, "dispatch", record_dispatch)
    direct = lifecycle.execute_adapt_start_command(
        target_id="rover",
        parameters=parameters,
        active_probe=lifecycle.ActiveProbeMode.NONE,
        run_adapter_agent=False,
        interaction_surface=InteractionSurface.GUI,
        settings=settings,
    )
    get_settings.cache_clear()
    cli = CliRunner().invoke(
        app,
        [
            "adapt",
            "start",
            "--robot-id",
            "rover",
            "--project-root",
            parameters.project_root,
            "--active-probe",
            "none",
            "--discover-only",
            "--timeout",
            "15",
        ],
    )
    get_settings.cache_clear()

    assert cli.exit_code == 0, cli.output
    cli_execution = captured[-1]
    assert direct.command.interaction_surface == InteractionSurface.GUI
    assert cli_execution.command.interaction_surface == InteractionSurface.CLI
    assert direct.command_sha256 == cli_execution.command_sha256
    assert direct.command.idempotency_key == cli_execution.command.idempotency_key


def test_unknown_fields_inline_secrets_and_illegal_paths_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        AdaptStartParameters.model_validate(
            {
                "project_root": str(tmp_path.resolve()),
                "timeout_s": 15,
                "password": "forbidden",
            }
        )
    with pytest.raises(ValidationError, match="absolute controller path"):
        AdaptStartParameters(project_root="relative/project", timeout_s=15)
    with pytest.raises(ValidationError, match="cannot contain URI userinfo"):
        TargetConnectionProfile(
            connection_profile_id="bad-ref",
            host="rover.example",
            user="rolo",
            credential_ref="credential://user:password@ssh/rover",
            known_hosts_path=str((tmp_path / "known_hosts").resolve()),
            trust_level=TargetTrustLevel.STRICT,
            expected_host_key_sha256="SHA256:" + "A" * 43,
        )


def test_adapt_parameters_preserve_target_paths_without_controller_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_resolve(self):  # type: ignore[no-untyped-def]
        raise AssertionError(f"controller resolve must not inspect target path: {self}")

    monkeypatch.setattr(Path, "resolve", unexpected_resolve)

    parameters = AdaptStartParameters(
        project_root_location="TARGET",
        project_root="/home/robot/ws",
        timeout_s=60,
        evidence_mode="remote",
    )

    assert parameters.schema_version == "rolo-adapt-start-parameters/v2"
    assert parameters.project_root == "/home/robot/ws"
    with pytest.raises(ValidationError, match="normalized absolute target path"):
        AdaptStartParameters(
            project_root_location="TARGET",
            project_root="../controller/path",
            timeout_s=60,
            evidence_mode="remote",
        )


def test_lifecycle_uses_bound_target_metadata_without_local_workspace_scan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parameters = AdaptStartParameters(
        project_root_location="TARGET",
        project_root="/home/robot/ws",
        timeout_s=60,
        evidence_mode="remote",
    )
    envelope = build_adapt_start_envelope(
        target_id="remote-arm",
        parameters=parameters,
        active_probe="none",
        run_adapter_agent=False,
    )
    project_evidence = ProjectEvidence(
        project_root=Path("/home/robot/ws"),
        observation_mode="TARGET_METADATA",
        target_workspace_manifest_sha256="a" * 64,
        target_observed_paths=["README.md"],
        target_project_root="/home/robot/ws",
    )
    captured: dict[str, object] = {}

    class _Journey:
        def start(self, **kwargs):  # type: ignore[no-untyped-def]
            captured.update(kwargs)
            return {"status": "DISCOVERY_COMPLETE"}

    def unexpected_scan(_path: Path) -> object:
        raise AssertionError("controller must not scan the target workspace")

    monkeypatch.setattr(lifecycle, "detect_project_evidence", unexpected_scan)
    monkeypatch.setattr(lifecycle, "prepare_runtime_directories", lambda _settings: None)
    monkeypatch.setattr(lifecycle, "configured_discovery_service", lambda *_args: object())
    monkeypatch.setattr(lifecycle, "AdaptJourneyService", lambda *_args: _Journey())
    settings = Settings(
        _env_file=None,
        rolo_config_dir=tmp_path / "config",
        rolo_artifact_dir=tmp_path / "artifacts",
    )

    result = lifecycle.run_adapt_start_parameters(
        command=envelope.command,
        parameters=parameters,
        settings=settings,
        project_evidence=project_evidence,
    )

    assert result == {"status": "DISCOVERY_COMPLETE"}
    assert captured["evidence"] == project_evidence
    inputs = project_evidence.active_inputs(lifecycle.ActiveProbeMode.NONE)
    assert inputs.source_roots == []
    assert inputs.target_workspace_manifest_sha256 == "a" * 64


def test_real_discovery_journey_records_low_confidence_target_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_root = tmp_path / "config"
    (config_root / "robots").mkdir(parents=True)
    shutil.copy2(
        Path("tests/fixtures/robots/demo_diff.yaml"),
        config_root / "robots" / "demo_diff.yaml",
    )
    artifact_root = tmp_path / "artifacts"
    parameters = AdaptStartParameters(
        project_root_location="TARGET",
        project_root="/home/robot/ws",
        timeout_s=60,
        evidence_mode="remote",
    )
    envelope = build_adapt_start_envelope(
        target_id="demo_diff",
        parameters=parameters,
        active_probe="none",
        run_adapter_agent=False,
    )
    project_evidence = ProjectEvidence(
        project_root=Path("/home/robot/ws"),
        observation_mode="TARGET_METADATA",
        target_workspace_manifest_sha256="b" * 64,
        target_observed_paths=["README.md"],
        target_project_root="/home/robot/ws",
    )

    def unexpected_scan(_path: Path) -> object:
        raise AssertionError("controller must not scan the target workspace")

    monkeypatch.setattr(lifecycle, "detect_project_evidence", unexpected_scan)
    result = lifecycle.run_adapt_start_parameters(
        command=envelope.command,
        parameters=parameters,
        settings=Settings(
            _env_file=None,
            rolo_config_dir=config_root,
            rolo_artifact_dir=artifact_root,
        ),
        project_evidence=project_evidence,
    )
    active_paths = list(
        (artifact_root / "discovery" / "demo_diff" / "runs").glob(
            "*/active_discovery_report.json"
        )
    )
    active = json.loads(active_paths[0].read_text(encoding="utf-8"))

    assert result.status == "DISCOVERY_COMPLETE"
    assert result.evidence.observation_mode == "TARGET_METADATA"
    assert active["discovery_mode"]["level"] == "TARGET_METADATA"
    assert active["inputs"]["source_roots"] == []
