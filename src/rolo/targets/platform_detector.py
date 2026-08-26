from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from rolo.targets.bootstrap import (
    BootstrapPlan,
    TargetPlatformFacts,
    build_bootstrap_plan,
    build_target_preflight,
)
from rolo.targets.credentials import CredentialPurpose, CredentialResolver
from rolo.targets.deployment_authorization import DeploymentAuthorizationKeyRegistry
from rolo.targets.executor import (
    LocalTargetExecutor,
    SshTargetExecutor,
    TargetExecutionErrorCode,
    TargetExecutionStatus,
    TargetExecutor,
    TargetInspectionRequest,
    TargetInspectionTool,
)
from rolo.targets.models import TargetProfile, TargetTransport
from rolo.targets.package_installer import (
    TargetPackageSignatureVerifier,
    load_target_package,
    verify_target_package,
)
from rolo.targets.registry import TargetProfileRegistry


class TargetCapabilityDetectionError(RuntimeError):
    """A secret-free, deterministic failure raised by runtime capability detection."""

    def __init__(self, error_code: TargetExecutionErrorCode) -> None:
        self.error_code = error_code
        super().__init__(f"target runtime capability detection failed: {error_code.value}")


class TargetRuntimeCapabilityDetector:
    def __init__(self, executor: TargetExecutor) -> None:
        self._executor = executor

    def detect(
        self,
        *,
        request_id: str,
        timeout_s: float = 20.0,
    ) -> TargetPlatformFacts:
        request = TargetInspectionRequest(
            request_id=request_id,
            tool=TargetInspectionTool.RUNTIME_CAPABILITIES,
            timeout_s=timeout_s,
            max_stdout_bytes=64 * 1024,
            max_stderr_bytes=16 * 1024,
        )
        result = self._executor.inspect(request)
        if result.status != TargetExecutionStatus.SUCCEEDED:
            raise TargetCapabilityDetectionError(
                result.error_code or TargetExecutionErrorCode.PROTOCOL_ERROR
            )
        try:
            return TargetPlatformFacts.model_validate_json(result.stdout)
        except (ValidationError, ValueError) as exc:
            raise TargetCapabilityDetectionError(
                TargetExecutionErrorCode.PROTOCOL_ERROR
            ) from exc


class TargetBootstrapPlanner:
    """Verify a package, inspect a target, and produce a non-mutating bootstrap plan."""

    def __init__(
        self,
        executor: TargetExecutor,
        verifier: TargetPackageSignatureVerifier,
        *,
        signing_public_key_sha256: str,
    ) -> None:
        self._detector = TargetRuntimeCapabilityDetector(executor)
        self._verifier = verifier
        self._signing_public_key_sha256 = signing_public_key_sha256

    def plan(
        self,
        *,
        target_id: str,
        package_root: Path,
        request_id: str,
        current_package_version: str | None = None,
        current_manifest_sha256: str | None = None,
        install_requires_sudo: bool = False,
    ) -> BootstrapPlan:
        root, manifest, signature = load_target_package(package_root)
        verify_target_package(root, manifest, signature, self._verifier)
        facts = self._detector.detect(request_id=request_id)
        preflight = build_target_preflight(manifest, facts)
        return build_bootstrap_plan(
            target_id=target_id,
            manifest=manifest,
            signature=signature,
            signing_public_key_sha256=self._signing_public_key_sha256,
            preflight=preflight,
            current_package_version=current_package_version,
            current_manifest_sha256=current_manifest_sha256,
            install_requires_sudo=install_requires_sudo,
        )


def target_executor_for_profile(
    profile: TargetProfile,
    *,
    registry: TargetProfileRegistry,
    credential_resolver: CredentialResolver,
    credential_purpose: CredentialPurpose = CredentialPurpose.SSH_BOOTSTRAP,
) -> TargetExecutor:
    if profile.transport == TargetTransport.LOCAL:
        return LocalTargetExecutor(
            enrollment_root=(
                registry.root
                / "local-state"
                / profile.target_id
                / "enrollment"
            ),
            deployment_authorization_registry=DeploymentAuthorizationKeyRegistry(
                registry.root
                / "local-state"
                / profile.target_id
                / "authorization-pins"
            ),
        )
    connection = registry.get_connection(profile.connection_profile_id or "")
    if connection.trust_level != profile.trust_level:
        raise ValueError("target and SSH connection trust levels must match")
    proxy = (
        registry.get_connection(connection.proxy_jump_profile_id)
        if connection.proxy_jump_profile_id is not None
        else None
    )
    return SshTargetExecutor(
        connection,
        credential_resolver,
        proxy_connection=proxy,
        credential_purpose=credential_purpose,
    )
