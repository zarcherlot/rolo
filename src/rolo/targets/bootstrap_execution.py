from __future__ import annotations

import hashlib
import json
import re
import threading
from base64 import b64decode
from base64 import b64encode as encode_base64
from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from rolo.core.persistence import interprocess_lock
from rolo.targets.bootstrap import (
    BootstrapInstallStatus,
    TargetBootstrapInstallResult,
    TargetInstallIndex,
    TargetPlatformFacts,
    build_target_preflight,
)
from rolo.targets.deployment_authorization import (
    DeploymentAuthorizationKeyConflict,
    DeploymentAuthorizationKeyPin,
    DeploymentAuthorizationKeyRegistry,
    DeploymentAuthorizationProof,
    validate_deployment_request_authorization_binding,
)
from rolo.targets.executor import (
    BoundedProcessRunner,
    LocalTargetExecutor,
    TargetExecutionErrorCode,
    TargetExecutionStatus,
    TargetExecutor,
    TargetExecutorKind,
    TargetInspectionRequest,
    TargetInspectionResult,
    TargetInspectionTool,
    _ProcessSpec,
    _safe_process_environment,
)
from rolo.targets.package_installer import (
    TargetPackageActiveUnavailable,
    TargetPackageInstaller,
    TargetPackageInstallStateConflict,
    TargetPackageRollbackUnavailable,
    TargetRuntimeHealthChecker,
    load_target_package,
    verify_target_package,
)
from rolo.targets.package_signing import (
    Ed25519TargetPackageVerifier,
    ed25519_public_key_sha256,
)
from rolo.targets.package_transfer import (
    TargetPackageUploader,
    TargetPackageUploadResult,
)
from rolo.targets.platform_detector import (
    TargetCapabilityDetectionError,
    TargetRuntimeCapabilityDetector,
)

_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$"
_SHA256_PATTERN = r"^[0-9a-f]{64}$"

_PREINSTALL_BOOTSTRAP_LAUNCHER_SCRIPT = r"""import hashlib,json,os,re,sys,tempfile
EXPECTED={'schema_version','request_id','operation','target_id','package_id','manifest_sha256','signing_key_id','signing_public_key_base64','signing_public_key_sha256','approval_id','authorization','expect_current_present','expected_current_manifest_sha256','authorization_key_pin','expected_authorization_key_sha256','timeout_s'}
IDENTIFIER=re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$')
DIGEST=re.compile(r'^[0-9a-f]{64}$')
def digest_file(path):
    digest=hashlib.sha256()
    with open(path,'rb') as stream:
        while True:
            chunk=stream.read(1024*1024)
            if not chunk:
                return digest.hexdigest()
            digest.update(chunk)
def reject_symlinks(root,path):
    current=root
    relative=os.path.relpath(path,root)
    if relative == '..' or relative.startswith('../') or os.path.islink(root):
        raise ValueError('path')
    for part in relative.split(os.sep):
        current=os.path.join(current,part)
        if os.path.islink(current):
            raise ValueError('symlink')
raw=sys.stdin.buffer.read(65537)
if len(raw)>65536:
    raise SystemExit(2)
try:
    request=json.loads(raw.decode('utf-8'))
    if not isinstance(request,dict) or set(request)!=EXPECTED:
        raise ValueError('shape')
    if request['schema_version']!='rolo-target-bootstrap-execution-request/v1':
        raise ValueError('schema')
    if not IDENTIFIER.fullmatch(request['package_id']):
        raise ValueError('package')
    if not DIGEST.fullmatch(request['manifest_sha256']):
        raise ValueError('digest')
    root=os.path.realpath(os.path.expanduser('~/.local/share/rolo/bootstrap/incoming'))
    package_root=os.path.join(
        root,'packages',request['package_id'],request['manifest_sha256'])
    manifest_path=os.path.join(package_root,'target-package.json')
    reject_symlinks(root,manifest_path)
    if os.path.getsize(manifest_path)>1048576:
        raise ValueError('manifest size')
    with open(manifest_path,'r',encoding='utf-8') as stream:
        manifest=json.load(stream)
    canonical=json.dumps(
        manifest,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
    if hashlib.sha256(canonical).hexdigest()!=request['manifest_sha256']:
        raise ValueError('manifest digest')
    if manifest.get('schema_version')!='rolo-target-package/v1':
        raise ValueError('manifest schema')
    if manifest.get('package_id')!=request['package_id']:
        raise ValueError('manifest package')
    entrypoint=manifest.get('entrypoint')
    if (not isinstance(entrypoint,str) or not entrypoint
            or '\\' in entrypoint or ':' in entrypoint):
        raise ValueError('entrypoint')
    parts=entrypoint.split('/')
    if any(not part or part in ('.','..') for part in parts):
        raise ValueError('entrypoint')
    declared=[item for item in manifest.get('files',[])
              if isinstance(item,dict) and item.get('path')==entrypoint
              and item.get('role')=='ENTRYPOINT']
    if len(declared)!=1:
        raise ValueError('entrypoint declaration')
    item=declared[0]
    executable=os.path.join(package_root,*parts)
    reject_symlinks(package_root,executable)
    if (not os.path.isfile(executable) or os.path.getsize(executable)!=item.get('size_bytes')
            or digest_file(executable)!=item.get('sha256')):
        raise ValueError('entrypoint integrity')
    mode=item.get('mode')
    if type(mode) is not int or not 0<=mode<=0o777 or mode&0o111==0:
        raise ValueError('entrypoint mode')
    os.chmod(executable,mode)
    safe_env={name:os.environ[name] for name in ('HOME','LANG','LC_ALL','PATH','TMPDIR')
              if name in os.environ}
    safe_env.setdefault('PATH','/usr/local/bin:/usr/bin:/bin')
    with tempfile.TemporaryFile() as request_stream:
        request_stream.write(raw)
        request_stream.seek(0)
        os.dup2(request_stream.fileno(),0)
        os.execve(executable,[executable,'target-executor','bootstrap'],safe_env)
except (KeyError,OSError,TypeError,UnicodeError,ValueError):
    raise SystemExit(2)
"""


class TargetBootstrapExecutionOperation(str, Enum):
    STATUS = "STATUS"
    INSTALL_ACTIVATE = "INSTALL_ACTIVATE"
    HEALTH = "HEALTH"
    ROLLBACK = "ROLLBACK"


class TargetBootstrapExecutionErrorCode(str, Enum):
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    ACTIVE_UNAVAILABLE = "ACTIVE_UNAVAILABLE"
    AUTHORIZATION_KEY_CONFLICT = "AUTHORIZATION_KEY_CONFLICT"
    AUTHORIZATION_KEY_UNAVAILABLE = "AUTHORIZATION_KEY_UNAVAILABLE"
    HEALTH_CHECK_FAILED = "HEALTH_CHECK_FAILED"
    IO_ERROR = "IO_ERROR"
    PACKAGE_INVALID = "PACKAGE_INVALID"
    PREFLIGHT_BLOCKED = "PREFLIGHT_BLOCKED"
    ROLLBACK_UNAVAILABLE = "ROLLBACK_UNAVAILABLE"
    STATE_CONFLICT = "STATE_CONFLICT"
    TARGET_INSPECTION_FAILED = "TARGET_INSPECTION_FAILED"


class TargetBootstrapAuthorizationKeyStatus(str, Enum):
    NOT_REQUESTED = "NOT_REQUESTED"
    INSTALLED = "INSTALLED"
    ALREADY_CURRENT = "ALREADY_CURRENT"
    FAILED = "FAILED"


class TargetBootstrapExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-bootstrap-execution-request/v1"] = (
        "rolo-target-bootstrap-execution-request/v1"
    )
    request_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    operation: TargetBootstrapExecutionOperation
    target_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    package_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    signing_key_id: str | None = Field(default=None, pattern=_IDENTIFIER_PATTERN)
    signing_public_key_base64: str | None = Field(default=None, max_length=32_768)
    signing_public_key_sha256: str | None = Field(
        default=None,
        pattern=_SHA256_PATTERN,
    )
    approval_id: str | None = Field(default=None, pattern=r"^approval-[0-9a-f]{32}$")
    authorization: DeploymentAuthorizationProof | None = None
    expect_current_present: bool | None = None
    expected_current_manifest_sha256: str | None = Field(
        default=None,
        pattern=_SHA256_PATTERN,
    )
    authorization_key_pin: DeploymentAuthorizationKeyPin | None = None
    expected_authorization_key_sha256: str | None = Field(
        default=None,
        pattern=_SHA256_PATTERN,
    )
    timeout_s: float = Field(default=300.0, ge=10.0, le=1800.0)

    @field_validator("signing_public_key_base64")
    @classmethod
    def validate_public_key_base64(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            payload = b64decode(value, validate=True)
        except ValueError as exc:
            raise ValueError("target bootstrap signing public key is invalid base64") from exc
        if not 1 <= len(payload) <= 16 * 1024:
            raise ValueError("target bootstrap signing public key size is out of bounds")
        return value

    @model_validator(mode="after")
    def require_operation_inputs(self) -> TargetBootstrapExecutionRequest:
        mutation = self.operation in {
            TargetBootstrapExecutionOperation.INSTALL_ACTIVATE,
            TargetBootstrapExecutionOperation.ROLLBACK,
        }
        requires_key = self.operation != TargetBootstrapExecutionOperation.STATUS
        if mutation != (self.approval_id is not None):
            raise ValueError("target bootstrap mutation requires exactly one approval reference")
        has_any_key = (
            self.signing_key_id is not None
            or self.signing_public_key_base64 is not None
            or self.signing_public_key_sha256 is not None
        )
        has_complete_key = (
            self.signing_key_id is not None
            and self.signing_public_key_base64 is not None
            and self.signing_public_key_sha256 is not None
        )
        if (requires_key and not has_complete_key) or (
            not requires_key and has_any_key
        ):
            raise ValueError("target bootstrap operation signing-key inputs are inconsistent")
        if requires_key and (
            ed25519_public_key_sha256(self.public_key_bytes())
            != self.signing_public_key_sha256
        ):
            raise ValueError("target bootstrap signing public key digest mismatch")
        if self.operation == TargetBootstrapExecutionOperation.ROLLBACK:
            if self.expected_current_manifest_sha256 is None:
                raise ValueError("target bootstrap rollback requires expected current digest")
            if self.expect_current_present is not None:
                raise ValueError("target bootstrap rollback does not accept current presence")
        elif self.operation == TargetBootstrapExecutionOperation.INSTALL_ACTIVATE:
            pass
        elif (
            self.expect_current_present is not None
            or self.expected_current_manifest_sha256 is not None
        ):
            raise ValueError("read-only target bootstrap operation rejects CAS inputs")
        if self.authorization_key_pin is None:
            if self.expected_authorization_key_sha256 is not None:
                raise ValueError(
                    "target bootstrap authorization-key CAS requires a new pin"
                )
        else:
            if self.operation != TargetBootstrapExecutionOperation.INSTALL_ACTIVATE:
                raise ValueError(
                    "target bootstrap authorization-key update requires install activation"
                )
            if (
                self.authorization_key_pin.target_id != self.target_id
                or self.authorization_key_pin.installed_by_approval_id
                != self.approval_id
            ):
                raise ValueError(
                    "target bootstrap authorization-key pin binding mismatch"
                )
        validate_deployment_request_authorization_binding(
            self,
            authorization=self.authorization,
            expected_target_id=self.target_id,
            expected_approval_id=self.approval_id,
        )
        return self

    def public_key_bytes(self) -> bytes:
        if self.signing_public_key_base64 is None:
            raise ValueError("target bootstrap operation has no signing public key")
        return b64decode(self.signing_public_key_base64, validate=True)

    def canonical_sha256(self) -> str:
        payload = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


class TargetBootstrapExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-bootstrap-execution-result/v1"] = (
        "rolo-target-bootstrap-execution-result/v1"
    )
    request_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    request_sha256: str = Field(pattern=_SHA256_PATTERN)
    target_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    package_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    signing_key_id: str | None = Field(default=None, pattern=_IDENTIFIER_PATTERN)
    signing_public_key_sha256: str | None = Field(
        default=None,
        pattern=_SHA256_PATTERN,
    )
    executor_kind: TargetExecutorKind
    operation: TargetBootstrapExecutionOperation
    status: TargetExecutionStatus
    transport_error_code: TargetExecutionErrorCode | None = None
    bootstrap_error_code: TargetBootstrapExecutionErrorCode | None = None
    blockers: list[str] = Field(default_factory=list, max_length=64)
    install_result: TargetBootstrapInstallResult | None = None
    install_index: TargetInstallIndex | None = None
    healthy: bool | None = None
    authorization_key_pin_sha256: str | None = Field(
        default=None,
        pattern=_SHA256_PATTERN,
    )
    authorization_key_status: TargetBootstrapAuthorizationKeyStatus = (
        TargetBootstrapAuthorizationKeyStatus.NOT_REQUESTED
    )

    @model_validator(mode="after")
    def require_consistent_execution(self) -> TargetBootstrapExecutionResult:
        if self.blockers != sorted(set(self.blockers)):
            raise ValueError("target bootstrap execution blockers must be unique and sorted")
        requires_key = self.operation != TargetBootstrapExecutionOperation.STATUS
        has_key = (
            self.signing_key_id is not None
            and self.signing_public_key_sha256 is not None
        )
        has_partial_key = (
            self.signing_key_id is not None
            or self.signing_public_key_sha256 is not None
        )
        if (requires_key and not has_key) or (not requires_key and has_partial_key):
            raise ValueError("target bootstrap result signing-key fields are inconsistent")
        errors = int(self.transport_error_code is not None) + int(
            self.bootstrap_error_code is not None
        )
        if self.status == TargetExecutionStatus.SUCCEEDED and errors:
            raise ValueError("successful target bootstrap execution cannot contain an error")
        if self.status == TargetExecutionStatus.FAILED and errors != 1:
            raise ValueError("failed target bootstrap execution requires exactly one error")
        if self.blockers and (
            self.bootstrap_error_code
            != TargetBootstrapExecutionErrorCode.PREFLIGHT_BLOCKED
        ):
            raise ValueError("target bootstrap blockers require PREFLIGHT_BLOCKED")
        if self.status == TargetExecutionStatus.SUCCEEDED:
            if self.operation == TargetBootstrapExecutionOperation.STATUS:
                if self.install_result is not None or self.healthy is not None:
                    raise ValueError("target bootstrap status result contains unrelated fields")
            elif self.operation == TargetBootstrapExecutionOperation.HEALTH:
                if self.install_index is None or self.healthy is None:
                    raise ValueError("target bootstrap health result is incomplete")
            elif self.install_result is None:
                raise ValueError("target bootstrap mutation result is incomplete")
            elif (
                self.operation == TargetBootstrapExecutionOperation.ROLLBACK
                and (
                    self.install_result.installed.package_id != self.package_id
                    or self.install_result.installed.manifest_sha256
                    != self.manifest_sha256
                )
            ):
                raise ValueError(
                    "target bootstrap rollback result differs from requested previous release"
                )
        if (
            self.authorization_key_status
            == TargetBootstrapAuthorizationKeyStatus.NOT_REQUESTED
        ) != (self.authorization_key_pin_sha256 is None):
            raise ValueError(
                "target bootstrap authorization-key result is inconsistent"
            )
        return self


class TargetBootstrapDeploymentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-bootstrap-deployment-result/v1"] = (
        "rolo-target-bootstrap-deployment-result/v1"
    )
    target_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    signing_key_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    signing_public_key_sha256: str = Field(pattern=_SHA256_PATTERN)
    upload: TargetPackageUploadResult
    execution: TargetBootstrapExecutionResult

    @model_validator(mode="after")
    def bind_deployment(self) -> TargetBootstrapDeploymentResult:
        if self.execution.target_id != self.target_id:
            raise ValueError("target bootstrap deployment target identity mismatch")
        if self.execution.operation != TargetBootstrapExecutionOperation.INSTALL_ACTIVATE:
            raise ValueError("target bootstrap deployment requires install execution")
        if (
            self.execution.signing_key_id != self.signing_key_id
            or self.execution.signing_public_key_sha256
            != self.signing_public_key_sha256
        ):
            raise ValueError("target bootstrap deployment signing key pin mismatch")
        if (
            self.upload.package_id != self.execution.package_id
            or self.upload.manifest_sha256 != self.execution.manifest_sha256
        ):
            raise ValueError("target bootstrap deployment package digest mismatch")
        return self


class TargetBootstrapOperator:
    """One product-facing subject for verified upload followed by target execution."""

    def __init__(
        self,
        executor: TargetExecutor,
        *,
        signing_key_id: str,
        signing_public_key: bytes,
        chunk_size_bytes: int = 256 * 1024,
    ) -> None:
        self._executor = executor
        self._key_id = signing_key_id
        self._public_key = signing_public_key
        self._verifier = Ed25519TargetPackageVerifier(
            {signing_key_id: signing_public_key}
        )
        self._public_key_sha256 = self._verifier.public_key_sha256(signing_key_id)
        self._uploader = TargetPackageUploader(
            executor,
            self._verifier,
            chunk_size_bytes=chunk_size_bytes,
        )

    def install_and_activate(
        self,
        package_root: Path,
        *,
        target_id: str,
        request_id: str,
        approval_id: str,
        expect_current_present: bool | None = None,
        expected_current_manifest_sha256: str | None = None,
        authorization_key_pin: DeploymentAuthorizationKeyPin | None = None,
        expected_authorization_key_sha256: str | None = None,
        timeout_s: float = 300.0,
        cancel_event: threading.Event | None = None,
    ) -> TargetBootstrapDeploymentResult:
        if len(request_id) > 80 or re.fullmatch(_IDENTIFIER_PATTERN, request_id) is None:
            raise ValueError("target bootstrap deployment request ID is invalid")
        _, manifest, signature = load_target_package(package_root)
        if signature.key_id != self._key_id:
            raise ValueError("target bootstrap package signing key ID differs from pin")
        request = TargetBootstrapExecutionRequest(
            request_id=request_id,
            operation=TargetBootstrapExecutionOperation.INSTALL_ACTIVATE,
            target_id=target_id,
            package_id=manifest.package_id,
            manifest_sha256=manifest.canonical_sha256(),
            signing_key_id=self._key_id,
            signing_public_key_base64=encode_base64(self._public_key).decode("ascii"),
            signing_public_key_sha256=self._public_key_sha256,
            approval_id=approval_id,
            expect_current_present=expect_current_present,
            expected_current_manifest_sha256=expected_current_manifest_sha256,
            authorization_key_pin=authorization_key_pin,
            expected_authorization_key_sha256=(
                expected_authorization_key_sha256
            ),
            timeout_s=timeout_s,
        )
        upload = self._uploader.upload(
            package_root,
            request_prefix=f"{request_id}-upload",
            cancel_event=cancel_event,
        )
        execution = self._executor.execute_bootstrap(
            request,
            cancel_event=cancel_event,
        )
        return TargetBootstrapDeploymentResult(
            target_id=target_id,
            signing_key_id=self._key_id,
            signing_public_key_sha256=self._public_key_sha256,
            upload=upload,
            execution=execution,
        )


class FixedTargetRuntimeHealthChecker:
    """Health-check only the product-owned read-only companion protocol."""

    def __init__(self, runner: BoundedProcessRunner | None = None) -> None:
        self._runner = runner or BoundedProcessRunner()

    def check(self, entrypoint: Path, manifest) -> bool:  # type: ignore[no-untyped-def]
        request = TargetInspectionRequest(
            request_id=f"health-{manifest.canonical_sha256()[:24]}",
            tool=TargetInspectionTool.PLATFORM,
            timeout_s=20.0,
            max_stdout_bytes=128 * 1024,
            max_stderr_bytes=16 * 1024,
        )
        outcome = self._runner.run(
            _ProcessSpec(
                argv=[str(entrypoint), "target-executor", "inspect"],
                stdin=request.model_dump_json(),
                timeout_s=request.timeout_s,
                max_stdout_bytes=request.max_stdout_bytes,
                max_stderr_bytes=request.max_stderr_bytes,
                environment=_safe_process_environment(),
            )
        )
        if outcome.error_code is not None or outcome.exit_code != 0:
            return False
        try:
            result = TargetInspectionResult.model_validate_json(outcome.stdout)
        except ValueError:
            return False
        return (
            result.request_id == request.request_id
            and result.request_sha256 == request.canonical_sha256()
            and result.status == TargetExecutionStatus.SUCCEEDED
        )


class TargetBootstrapExecutionService:
    def __init__(
        self,
        *,
        incoming_root: Path,
        install_root: Path,
        facts_provider: Callable[[], TargetPlatformFacts] | None = None,
        health_checker: TargetRuntimeHealthChecker | None = None,
        authorization_key_registry: DeploymentAuthorizationKeyRegistry | None = None,
        transaction_root: Path | None = None,
    ) -> None:
        self._incoming_root = incoming_root.expanduser().resolve()
        self._installer = TargetPackageInstaller(install_root)
        self._facts_provider = facts_provider or self._detect_facts
        self._health_checker = health_checker or FixedTargetRuntimeHealthChecker()
        self._authorization_keys = authorization_key_registry
        self._transaction_root = (
            transaction_root or install_root / "bootstrap-transactions"
        ).expanduser().absolute()
        if self._transaction_root.is_symlink():
            raise ValueError("target bootstrap transaction root cannot be a symbolic link")

    @staticmethod
    def _detect_facts() -> TargetPlatformFacts:
        return TargetRuntimeCapabilityDetector(LocalTargetExecutor()).detect(
            request_id="bootstrap-runtime-capabilities"
        )

    def _package_root(self, request: TargetBootstrapExecutionRequest) -> Path:
        return (
            self._incoming_root
            / "packages"
            / request.package_id
            / request.manifest_sha256
        )

    @staticmethod
    def _verifier(
        request: TargetBootstrapExecutionRequest,
    ) -> Ed25519TargetPackageVerifier:
        assert request.signing_key_id is not None
        return Ed25519TargetPackageVerifier(
            {request.signing_key_id: request.public_key_bytes()}
        )

    @staticmethod
    def _result(
        request: TargetBootstrapExecutionRequest,
        *,
        status: TargetExecutionStatus,
        bootstrap_error: TargetBootstrapExecutionErrorCode | None = None,
        blockers: list[str] | None = None,
        install_result: TargetBootstrapInstallResult | None = None,
        install_index: TargetInstallIndex | None = None,
        healthy: bool | None = None,
        authorization_key_status: TargetBootstrapAuthorizationKeyStatus | None = None,
    ) -> TargetBootstrapExecutionResult:
        pin = request.authorization_key_pin
        effective_key_status = authorization_key_status or (
            TargetBootstrapAuthorizationKeyStatus.FAILED
            if pin is not None
            else TargetBootstrapAuthorizationKeyStatus.NOT_REQUESTED
        )
        return TargetBootstrapExecutionResult(
            request_id=request.request_id,
            request_sha256=request.canonical_sha256(),
            target_id=request.target_id,
            package_id=request.package_id,
            manifest_sha256=request.manifest_sha256,
            signing_key_id=request.signing_key_id,
            signing_public_key_sha256=request.signing_public_key_sha256,
            executor_kind=TargetExecutorKind.LOCAL,
            operation=request.operation,
            status=status,
            bootstrap_error_code=bootstrap_error,
            blockers=sorted(set(blockers or [])),
            install_result=install_result,
            install_index=install_index,
            healthy=healthy,
            authorization_key_pin_sha256=(
                pin.canonical_sha256() if pin is not None else None
            ),
            authorization_key_status=effective_key_status,
        )

    def _execute_install_activate(
        self,
        request: TargetBootstrapExecutionRequest,
        *,
        verifier: Ed25519TargetPackageVerifier,
        package_root: Path,
        preflight,
    ) -> TargetBootstrapExecutionResult:
        pin = request.authorization_key_pin
        if pin is not None and self._authorization_keys is None:
            return self._result(
                request,
                status=TargetExecutionStatus.FAILED,
                bootstrap_error=(
                    TargetBootstrapExecutionErrorCode.AUTHORIZATION_KEY_UNAVAILABLE
                ),
            )
        if pin is not None:
            assert self._authorization_keys is not None
            try:
                self._authorization_keys.assess_bootstrap_update(
                    pin,
                    expected_current_public_key_sha256=(
                        request.expected_authorization_key_sha256
                    ),
                )
            except DeploymentAuthorizationKeyConflict:
                return self._result(
                    request,
                    status=TargetExecutionStatus.FAILED,
                    bootstrap_error=(
                        TargetBootstrapExecutionErrorCode.AUTHORIZATION_KEY_CONFLICT
                    ),
                )

        install_result: TargetBootstrapInstallResult
        current = self._installer.status()
        recovering_pin_commit = (
            pin is not None
            and current is not None
            and current.current.manifest_sha256 == request.manifest_sha256
        )
        if recovering_pin_commit:
            current, healthy = self._installer.health_current(
                verifier=verifier,
                health_checker=self._health_checker,
            )
            if not healthy:
                return self._result(
                    request,
                    status=TargetExecutionStatus.FAILED,
                    bootstrap_error=(
                        TargetBootstrapExecutionErrorCode.HEALTH_CHECK_FAILED
                    ),
                    install_index=current,
                    healthy=False,
                )
            install_result = TargetBootstrapInstallResult(
                status=BootstrapInstallStatus.ALREADY_ACTIVE,
                installed=current.current,
                active=current.current,
                previous_preserved=True,
            )
        else:
            install_result = self._installer.install_and_activate(
                package_root,
                preflight=preflight,
                verifier=verifier,
                health_checker=self._health_checker,
                expect_current_present=request.expect_current_present,
                expected_current_manifest_sha256=(
                    request.expected_current_manifest_sha256
                ),
            )
        healthy = install_result.status != BootstrapInstallStatus.HEALTH_CHECK_FAILED
        if not healthy:
            return self._result(
                request,
                status=TargetExecutionStatus.FAILED,
                bootstrap_error=TargetBootstrapExecutionErrorCode.HEALTH_CHECK_FAILED,
                install_result=install_result,
            )
        key_status = TargetBootstrapAuthorizationKeyStatus.NOT_REQUESTED
        if pin is not None:
            assert self._authorization_keys is not None
            try:
                disposition = self._authorization_keys.apply_bootstrap_update(
                    pin,
                    expected_current_public_key_sha256=(
                        request.expected_authorization_key_sha256
                    ),
                )
            except DeploymentAuthorizationKeyConflict:
                return self._result(
                    request,
                    status=TargetExecutionStatus.FAILED,
                    bootstrap_error=(
                        TargetBootstrapExecutionErrorCode.AUTHORIZATION_KEY_CONFLICT
                    ),
                    install_result=install_result,
                )
            key_status = (
                TargetBootstrapAuthorizationKeyStatus.ALREADY_CURRENT
                if disposition == "ALREADY_CURRENT"
                else TargetBootstrapAuthorizationKeyStatus.INSTALLED
            )
        return self._result(
            request,
            status=TargetExecutionStatus.SUCCEEDED,
            install_result=install_result,
            authorization_key_status=key_status,
        )

    def execute(
        self,
        request: TargetBootstrapExecutionRequest,
    ) -> TargetBootstrapExecutionResult:
        try:
            if request.operation == TargetBootstrapExecutionOperation.STATUS:
                return self._result(
                    request,
                    status=TargetExecutionStatus.SUCCEEDED,
                    install_index=self._installer.status(),
                )
            verifier = self._verifier(request)
            if request.operation == TargetBootstrapExecutionOperation.HEALTH:
                index, healthy = self._installer.health_current(
                    verifier=verifier,
                    health_checker=self._health_checker,
                )
                return self._result(
                    request,
                    status=(
                        TargetExecutionStatus.SUCCEEDED
                        if healthy
                        else TargetExecutionStatus.FAILED
                    ),
                    bootstrap_error=(
                        None
                        if healthy
                        else TargetBootstrapExecutionErrorCode.HEALTH_CHECK_FAILED
                    ),
                    install_index=index,
                    healthy=healthy,
                )
            if request.operation == TargetBootstrapExecutionOperation.ROLLBACK:
                transaction_path = (
                    self._transaction_root / f"{request.target_id}.transaction"
                )
                with interprocess_lock(
                    transaction_path,
                    timeout_s=request.timeout_s,
                    stale_after_s=max(request.timeout_s * 2, 3600.0),
                ):
                    result = self._installer.rollback(
                        verifier=verifier,
                        health_checker=self._health_checker,
                        expected_current_manifest_sha256=(
                            request.expected_current_manifest_sha256 or ""
                        ),
                        expected_previous_package_id=request.package_id,
                        expected_previous_manifest_sha256=request.manifest_sha256,
                    )
                return self._result(
                    request,
                    status=TargetExecutionStatus.SUCCEEDED,
                    install_result=result,
                )
            package_root = self._package_root(request)
            _, manifest, signature = load_target_package(package_root)
            if (
                manifest.package_id != request.package_id
                or manifest.canonical_sha256() != request.manifest_sha256
            ):
                raise ValueError("target bootstrap package identity mismatch")
            verify_target_package(package_root, manifest, signature, verifier)
            facts = self._facts_provider()
            preflight = build_target_preflight(manifest, facts)
            if preflight.blockers:
                return self._result(
                    request,
                    status=TargetExecutionStatus.FAILED,
                    bootstrap_error=(
                        TargetBootstrapExecutionErrorCode.PREFLIGHT_BLOCKED
                    ),
                    blockers=preflight.blockers,
                )
            transaction_path = (
                self._transaction_root / f"{request.target_id}.transaction"
            )
            with interprocess_lock(
                transaction_path,
                timeout_s=request.timeout_s,
                stale_after_s=max(request.timeout_s * 2, 3600.0),
            ):
                return self._execute_install_activate(
                    request,
                    verifier=verifier,
                    package_root=package_root,
                    preflight=preflight,
                )
        except TargetPackageInstallStateConflict:
            code = TargetBootstrapExecutionErrorCode.STATE_CONFLICT
        except TargetPackageActiveUnavailable:
            code = TargetBootstrapExecutionErrorCode.ACTIVE_UNAVAILABLE
        except TargetPackageRollbackUnavailable:
            code = TargetBootstrapExecutionErrorCode.ROLLBACK_UNAVAILABLE
        except TargetCapabilityDetectionError:
            code = TargetBootstrapExecutionErrorCode.TARGET_INSPECTION_FAILED
        except (OSError, ValueError):
            code = TargetBootstrapExecutionErrorCode.PACKAGE_INVALID
        return self._result(
            request,
            status=TargetExecutionStatus.FAILED,
            bootstrap_error=code,
        )
