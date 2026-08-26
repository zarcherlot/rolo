from __future__ import annotations

import hashlib
import json
import os
import platform
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
from base64 import b64decode, b64encode
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from rolo.targets.credentials import CredentialPurpose, CredentialResolver
from rolo.targets.models import ApprovalAction, TargetConnectionProfile

if TYPE_CHECKING:
    from rolo.adapter_runner import AdapterRunner
    from rolo.targets.adapter_release_activation import (
        AdapterReleaseActivationExecutionResult,
        AdapterReleaseActivationRequest,
    )
    from rolo.targets.adapter_release_reconciliation import (
        AdapterReleaseStatusExecutionResult,
        AdapterReleaseStatusRequest,
    )
    from rolo.targets.adapter_release_transfer import (
        AdapterReleaseStageExecutionResult,
        AdapterReleaseStageRequest,
    )
    from rolo.targets.bootstrap_execution import (
        TargetBootstrapExecutionRequest,
        TargetBootstrapExecutionResult,
    )
    from rolo.targets.deployment_authorization import DeploymentAuthorizationKeyRegistry
    from rolo.targets.enrollment import (
        TargetEnrollmentRequest,
        TargetEnrollmentResult,
    )
    from rolo.targets.evidence_v4 import (
        TargetEvidenceCollectionRequestV4,
        TargetEvidenceCollectionResultV4,
    )
    from rolo.targets.host_provisioning import (
        TargetHostProvisioningExecutionResult,
        TargetHostProvisioningObservation,
        TargetHostProvisioningPlan,
    )
    from rolo.targets.host_service import (
        TargetHostServiceExecutionResult,
        TargetHostServiceRequest,
    )
    from rolo.targets.runtime_deployment import (
        AdapterReleaseDescribeExecutionResult,
        AdapterReleaseDescribeRequest,
        TargetProjectEvidenceExecutionResult,
        TargetProjectEvidenceRequest,
    )
    from rolo.targets.source_discovery import (
        TargetSourceDiscoveryExecutionResult,
        TargetSourceDiscoveryRequest,
    )

_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$"
_MAX_PROTOCOL_BYTES = 2_600_000


class TargetExecutorKind(str, Enum):
    LOCAL = "LOCAL"
    SSH = "SSH"


class TargetInspectionTool(str, Enum):
    PLATFORM = "PLATFORM"
    RUNTIME_CAPABILITIES = "RUNTIME_CAPABILITIES"
    PATH_STAT = "PATH_STAT"
    EXECUTABLE_HELP = "EXECUTABLE_HELP"


class TargetExecutionStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class TargetExecutionErrorCode(str, Enum):
    CANCELLED = "CANCELLED"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    CONNECTION_FAILED = "CONNECTION_FAILED"
    CREDENTIAL_UNAVAILABLE = "CREDENTIAL_UNAVAILABLE"
    HOST_KEY_VERIFICATION_FAILED = "HOST_KEY_VERIFICATION_FAILED"
    INTEGRITY_ERROR = "INTEGRITY_ERROR"
    IO_ERROR = "IO_ERROR"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    AUTHORIZATION_FAILED = "AUTHORIZATION_FAILED"
    NON_ZERO_EXIT = "NON_ZERO_EXIT"
    OUTPUT_LIMIT = "OUTPUT_LIMIT"
    OFFSET_MISMATCH = "OFFSET_MISMATCH"
    PROTOCOL_ERROR = "PROTOCOL_ERROR"
    SPAWN_FAILED = "SPAWN_FAILED"
    TIMEOUT = "TIMEOUT"


def _absolute_target_or_native_path(value: str) -> str:
    if any(character in value for character in ("\x00", "\r", "\n")):
        raise ValueError("inspection operand contains control characters")
    if PurePosixPath(value).is_absolute():
        return str(PurePosixPath(value))
    if len(value) >= 3 and value[0].isalpha() and value[1] == ":" and value[2] in "\\/":
        return value.replace("\\", "/")
    raise ValueError("inspection path must be absolute")


class TargetInspectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-inspection-request/v1"] = (
        "rolo-target-inspection-request/v1"
    )
    request_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    tool: TargetInspectionTool
    operand: str | None = Field(default=None, min_length=1, max_length=4096)
    timeout_s: float = Field(default=10.0, ge=0.1, le=300.0)
    max_stdout_bytes: int = Field(default=256_000, ge=1, le=2_000_000)
    max_stderr_bytes: int = Field(default=64_000, ge=1, le=512_000)

    @field_validator("operand")
    @classmethod
    def validate_operand_controls(cls, value: str | None) -> str | None:
        if value is not None and any(character in value for character in ("\x00", "\r", "\n")):
            raise ValueError("inspection operand contains control characters")
        return value

    @model_validator(mode="after")
    def require_tool_operand(self) -> TargetInspectionRequest:
        if self.tool in {
            TargetInspectionTool.PLATFORM,
            TargetInspectionTool.RUNTIME_CAPABILITIES,
        } and self.operand is not None:
            raise ValueError(f"{self.tool.value} inspection does not accept an operand")
        if self.tool == TargetInspectionTool.PATH_STAT:
            if self.operand is None:
                raise ValueError("PATH_STAT inspection requires an operand")
            self.operand = _absolute_target_or_native_path(self.operand)
        if self.tool == TargetInspectionTool.EXECUTABLE_HELP and self.operand is None:
            raise ValueError("EXECUTABLE_HELP inspection requires an operand")
        return self

    def canonical_sha256(self) -> str:
        payload = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


class TargetInspectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-inspection-result/v1"] = (
        "rolo-target-inspection-result/v1"
    )
    request_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    executor_kind: TargetExecutorKind
    status: TargetExecutionStatus
    error_code: TargetExecutionErrorCode | None = None
    exit_code: int | None = None
    stdout: str = Field(max_length=2_000_000)
    stderr: str = Field(max_length=512_000)
    timed_out: bool = False
    output_limited: bool = False
    cancelled: bool = False
    started_at: datetime
    finished_at: datetime

    @model_validator(mode="after")
    def require_consistent_outcome(self) -> TargetInspectionResult:
        if self.finished_at < self.started_at:
            raise ValueError("inspection finish time cannot precede start time")
        if self.status == TargetExecutionStatus.SUCCEEDED:
            if self.error_code is not None or self.exit_code != 0:
                raise ValueError("successful inspection must have exit 0 and no error code")
        elif self.error_code is None:
            raise ValueError("failed inspection requires an error code")
        if self.timed_out != (self.error_code == TargetExecutionErrorCode.TIMEOUT):
            raise ValueError("timed_out must match TIMEOUT error code")
        if self.output_limited != (self.error_code == TargetExecutionErrorCode.OUTPUT_LIMIT):
            raise ValueError("output_limited must match OUTPUT_LIMIT error code")
        if self.cancelled != (self.error_code == TargetExecutionErrorCode.CANCELLED):
            raise ValueError("cancelled must match CANCELLED error code")
        return self


class TargetPackageTransferOperation(str, Enum):
    QUERY = "QUERY"
    WRITE = "WRITE"


class TargetPackageTransferRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-package-transfer-request/v1"] = (
        "rolo-target-package-transfer-request/v1"
    )
    request_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    operation: TargetPackageTransferOperation
    package_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    path: str = Field(min_length=1, max_length=4096)
    file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    file_size_bytes: int = Field(ge=0, le=1_000_000_000)
    offset_bytes: int = Field(default=0, ge=0, le=1_000_000_000)
    chunk_size_bytes: int = Field(default=0, ge=0, le=512 * 1024)
    chunk_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    chunk_base64: str | None = Field(default=None, max_length=700_000)

    @field_validator("path")
    @classmethod
    def validate_transfer_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or not path.parts or ".." in path.parts or "." in path.parts:
            raise ValueError("target package transfer path must be normalized and relative")
        if any(character in value for character in ("\x00", "\r", "\n", "\\", ":")):
            raise ValueError("target package transfer path contains forbidden characters")
        return str(path)

    @model_validator(mode="after")
    def validate_operation_payload(self) -> TargetPackageTransferRequest:
        if self.operation == TargetPackageTransferOperation.QUERY:
            if (
                self.offset_bytes != 0
                or self.chunk_size_bytes != 0
                or self.chunk_sha256 is not None
                or self.chunk_base64 is not None
            ):
                raise ValueError("target package transfer query cannot contain chunk data")
            return self
        if self.chunk_sha256 is None or self.chunk_base64 is None:
            raise ValueError("target package transfer write requires chunk data")
        try:
            chunk = b64decode(self.chunk_base64, validate=True)
        except ValueError as exc:
            raise ValueError("target package transfer chunk is invalid base64") from exc
        if len(chunk) != self.chunk_size_bytes:
            raise ValueError("target package transfer chunk size mismatch")
        if hashlib.sha256(chunk).hexdigest() != self.chunk_sha256:
            raise ValueError("target package transfer chunk digest mismatch")
        if self.offset_bytes + self.chunk_size_bytes > self.file_size_bytes:
            raise ValueError("target package transfer chunk exceeds declared file size")
        if self.chunk_size_bytes == 0 and self.file_size_bytes != 0:
            raise ValueError("empty transfer chunk is only valid for an empty file")
        return self

    def chunk_bytes(self) -> bytes:
        if self.operation != TargetPackageTransferOperation.WRITE:
            raise ValueError("target package transfer query has no chunk")
        return b64decode(self.chunk_base64 or "", validate=True)

    def canonical_sha256(self) -> str:
        payload = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


class TargetPackageTransferResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-package-transfer-result/v1"] = (
        "rolo-target-package-transfer-result/v1"
    )
    request_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    executor_kind: TargetExecutorKind
    status: TargetExecutionStatus
    error_code: TargetExecutionErrorCode | None = None
    received_size_bytes: int = Field(ge=0, le=1_000_000_000)
    file_size_bytes: int = Field(ge=0, le=1_000_000_000)
    complete: bool

    @model_validator(mode="after")
    def require_consistent_transfer(self) -> TargetPackageTransferResult:
        if self.received_size_bytes > self.file_size_bytes:
            raise ValueError("target package transfer received size exceeds file size")
        if self.complete and self.received_size_bytes != self.file_size_bytes:
            raise ValueError("complete target package transfer requires the full file size")
        if self.status == TargetExecutionStatus.SUCCEEDED and self.error_code is not None:
            raise ValueError("successful target package transfer cannot contain an error")
        if self.status == TargetExecutionStatus.FAILED and self.error_code is None:
            raise ValueError("failed target package transfer requires an error code")
        return self


class TargetExecutor(Protocol):
    def inspect(
        self,
        request: TargetInspectionRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> TargetInspectionResult: ...

    def transfer_package_chunk(
        self,
        request: TargetPackageTransferRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> TargetPackageTransferResult: ...

    def execute_bootstrap(
        self,
        request: TargetBootstrapExecutionRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> TargetBootstrapExecutionResult: ...

    def execute_enrollment(
        self,
        request: TargetEnrollmentRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> TargetEnrollmentResult: ...

    def collect_evidence_v4(
        self,
        request: TargetEvidenceCollectionRequestV4,
        *,
        cancel_event: threading.Event | None = None,
    ) -> TargetEvidenceCollectionResultV4: ...

    def stage_adapter_release(
        self,
        request: AdapterReleaseStageRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> AdapterReleaseStageExecutionResult: ...

    def activate_adapter_release(
        self,
        request: AdapterReleaseActivationRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> AdapterReleaseActivationExecutionResult: ...

    def describe_adapter_release(
        self,
        request: AdapterReleaseDescribeRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> AdapterReleaseDescribeExecutionResult: ...

    def status_adapter_release(
        self,
        request: AdapterReleaseStatusRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> AdapterReleaseStatusExecutionResult: ...

    def detect_project_evidence(
        self,
        request: TargetProjectEvidenceRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> TargetProjectEvidenceExecutionResult: ...

    def discover_source(
        self,
        request: TargetSourceDiscoveryRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> TargetSourceDiscoveryExecutionResult: ...


@dataclass(frozen=True)
class _ProcessSpec:
    argv: list[str]
    stdin: str
    timeout_s: float
    max_stdout_bytes: int
    max_stderr_bytes: int
    cwd: Path | None = None
    redactions: tuple[str, ...] = ()
    environment: Mapping[str, str] | None = None


@dataclass(frozen=True)
class _ProcessOutcome:
    error_code: TargetExecutionErrorCode | None
    exit_code: int | None
    stdout: str
    stderr: str
    started_at: datetime
    finished_at: datetime


def _redact(value: str, redactions: tuple[str, ...]) -> str:
    result = value
    for secret in sorted((item for item in redactions if item), key=len, reverse=True):
        result = result.replace(secret, "<redacted>")
    return result


class BoundedProcessRunner:
    """Run argv-only subprocesses with bounded streams and cross-platform tree cleanup."""

    def run(
        self,
        spec: _ProcessSpec,
        *,
        cancel_event: threading.Event | None = None,
    ) -> _ProcessOutcome:
        if not spec.argv or any(
            not item or "\x00" in item
            for item in spec.argv
        ):
            raise ValueError("target process requires a non-empty control-safe argv")
        started_at = datetime.now(timezone.utc)
        options: dict[str, object] = {
            "stdin": subprocess.PIPE,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "cwd": spec.cwd,
            "env": spec.environment,
        }
        if os.name == "nt":
            options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            options["start_new_session"] = True
        try:
            process = subprocess.Popen(spec.argv, **options)
        except OSError as exc:
            finished_at = datetime.now(timezone.utc)
            return _ProcessOutcome(
                error_code=TargetExecutionErrorCode.SPAWN_FAILED,
                exit_code=None,
                stdout="",
                stderr=_redact(str(exc), spec.redactions)[: spec.max_stderr_bytes],
                started_at=started_at,
                finished_at=finished_at,
            )
        assert process.stdin is not None
        assert process.stdout is not None
        assert process.stderr is not None
        stdout = bytearray()
        stderr = bytearray()
        exceeded = threading.Event()

        def drain(stream: object, target: bytearray, limit: int) -> None:
            while True:
                chunk = stream.read(65_536)  # type: ignore[attr-defined]
                if not chunk:
                    return
                remaining = max(0, limit - len(target))
                target.extend(chunk[:remaining])
                if len(chunk) > remaining:
                    exceeded.set()

        readers = [
            threading.Thread(
                target=drain,
                args=(process.stdout, stdout, spec.max_stdout_bytes),
                daemon=True,
            ),
            threading.Thread(
                target=drain,
                args=(process.stderr, stderr, spec.max_stderr_bytes),
                daemon=True,
            ),
        ]
        for reader in readers:
            reader.start()
        try:
            process.stdin.write(spec.stdin.encode("utf-8"))
            process.stdin.close()
        except (BrokenPipeError, OSError):
            pass
        deadline = time.monotonic() + spec.timeout_s
        error_code: TargetExecutionErrorCode | None = None
        while process.poll() is None:
            if cancel_event is not None and cancel_event.is_set():
                error_code = TargetExecutionErrorCode.CANCELLED
                self._terminate_tree(process)
                break
            if exceeded.is_set():
                error_code = TargetExecutionErrorCode.OUTPUT_LIMIT
                self._terminate_tree(process)
                break
            if time.monotonic() >= deadline:
                error_code = TargetExecutionErrorCode.TIMEOUT
                self._terminate_tree(process)
                break
            time.sleep(0.01)
        try:
            exit_code = process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._terminate_tree(process)
            if error_code is None:
                error_code = TargetExecutionErrorCode.TIMEOUT
            try:
                exit_code = process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                exit_code = None
        for reader in readers:
            reader.join(timeout=2)
        if error_code is None and exceeded.is_set():
            error_code = TargetExecutionErrorCode.OUTPUT_LIMIT
        if error_code is None and exit_code != 0:
            error_code = TargetExecutionErrorCode.NON_ZERO_EXIT
        finished_at = datetime.now(timezone.utc)
        return _ProcessOutcome(
            error_code=error_code,
            exit_code=exit_code,
            stdout=_redact(stdout.decode("utf-8", errors="replace"), spec.redactions),
            stderr=_redact(stderr.decode("utf-8", errors="replace"), spec.redactions),
            started_at=started_at,
            finished_at=finished_at,
        )

    @staticmethod
    def _terminate_tree(process: subprocess.Popen[bytes]) -> None:
        if process.poll() is not None:
            return
        if os.name == "nt":
            try:
                subprocess.run(
                    ["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    timeout=5,
                    env=_safe_process_environment(),
                )
            except (OSError, subprocess.TimeoutExpired):
                pass
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        try:
            process.kill()
        except OSError:
            pass


_PLATFORM_SCRIPT = """import json,os,platform,sys
print(json.dumps({
    'machine': platform.machine(),
    'os': platform.system().casefold(),
    'os_release': platform.release(),
    'python': platform.python_version(),
    'python_executable': sys.executable,
    'uid': os.getuid() if hasattr(os, 'getuid') else None,
}, sort_keys=True, separators=(',', ':')))
"""

_RUNTIME_CAPABILITIES_SCRIPT = """import importlib.util,json,os,platform,shutil,subprocess,sys
def probe(argv,env=None):
    try:
        result=subprocess.run(argv,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=3,check=False,env=env)
        return result.returncode == 0
    except (OSError,subprocess.TimeoutExpired):
        return False
def posix_limit(name,fallback):
    try:
        import resource
        value=resource.getrlimit(getattr(resource,name))[0]
        return fallback if value in (-1,resource.RLIM_INFINITY) else max(0,int(value))
    except (AttributeError,ImportError,OSError,ValueError):
        return fallback
def bounded_int_file(path):
    try:
        raw=open(path,'r',encoding='ascii').read(64).strip()
        return None if raw == 'max' else max(0,int(raw))
    except (OSError,UnicodeError,ValueError):
        return None
def cgroup_process_capacity(default):
    for maximum_path,current_path in (
        ('/sys/fs/cgroup/pids.max','/sys/fs/cgroup/pids.current'),
        ('/sys/fs/cgroup/pids/pids.max','/sys/fs/cgroup/pids/pids.current'),
    ):
        maximum=bounded_int_file(maximum_path)
        if maximum is not None:
            current=bounded_int_file(current_path) or 0
            return min(default,max(0,maximum-current))
    return default
is_linux=platform.system().casefold() == 'linux'
safe_env={name:os.environ[name] for name in ('COMSPEC','PATH','SYSTEMROOT','WINDIR')
          if name in os.environ}
safe_env.update({'LANG':'C','LC_ALL':'C'})
bwrap=shutil.which('bwrap') if is_linux else None
bwrap_available=bool(bwrap and probe([bwrap,'--version'],safe_env))
unshare=shutil.which('unshare') if is_linux else None
user_namespace=bool(unshare and probe([unshare,'--user','--map-root-user','true'],safe_env))
mount_namespace=bool(unshare and probe(
    [unshare,'--user','--map-root-user','--mount','true'],safe_env))
network_namespace=bool(unshare and probe(
    [unshare,'--user','--map-root-user','--net','true'],safe_env))
if bwrap_available:
    base=[bwrap,'--die-with-parent','--ro-bind','/','/','--proc','/proc','--dev','/dev','--unshare-user','--uid','0','--gid','0']
    sandbox_ok=probe(base+['--','true'],safe_env)
    user_namespace=user_namespace or sandbox_ok
    mount_namespace=mount_namespace or sandbox_ok
    network_namespace=network_namespace or probe(base+['--unshare-net','--','true'],safe_env)
pythonpath_env=dict(safe_env)
pythonpath_env['PYTHONPATH']=os.devnull
pythonpath_probe='import os,sys;sys.exit(0 if os.environ.get(\"PYTHONPATH\") else 1)'
explicit_pythonpath=probe([sys.executable,'-c',pythonpath_probe],pythonpath_env)
process_capacity=cgroup_process_capacity(posix_limit('RLIMIT_NPROC',2**31-1))
print(json.dumps({
    'schema_version':'rolo-target-platform-facts/v1',
    'os':platform.system().casefold(),
    'architecture':platform.machine() or 'unknown',
    'python_version':platform.python_version(),
    'bubblewrap_available':bwrap_available,
    'user_namespace_available':user_namespace,
    'mount_namespace_available':mount_namespace,
    'network_namespace_available':network_namespace,
    'available_address_space_bytes':posix_limit('RLIMIT_AS',2**63-1),
    'available_processes':process_capacity,
    'runtime_path_available':bool(
        os.environ.get('PATH') and os.path.isabs(sys.executable)
        and os.path.isfile(sys.executable)),
    'explicit_pythonpath_supported':explicit_pythonpath,
    'virtualenv_supported':importlib.util.find_spec('venv') is not None,
},sort_keys=True,separators=(',',':')))
"""

_PATH_STAT_SCRIPT = """import json,os,pathlib,stat,sys
p=pathlib.Path(sys.argv[1]); s=p.lstat()
print(json.dumps({
    'exists': True,
    'is_dir': stat.S_ISDIR(s.st_mode),
    'is_file': stat.S_ISREG(s.st_mode),
    'is_symlink': stat.S_ISLNK(s.st_mode),
    'mode': stat.S_IMODE(s.st_mode),
    'path': str(p),
    'size': s.st_size,
}, sort_keys=True, separators=(',', ':')))
"""


def _safe_process_environment() -> dict[str, str]:
    allowed = {
        "COMSPEC",
        "LANG",
        "LC_ALL",
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
        "WINDIR",
    }
    return {name: value for name, value in os.environ.items() if name.upper() in allowed}


def _inspection_argv(request: TargetInspectionRequest) -> list[str]:
    if request.tool == TargetInspectionTool.PLATFORM:
        return [sys.executable, "-c", _PLATFORM_SCRIPT]
    if request.tool == TargetInspectionTool.RUNTIME_CAPABILITIES:
        return [sys.executable, "-c", _RUNTIME_CAPABILITIES_SCRIPT]
    if request.tool == TargetInspectionTool.PATH_STAT:
        return [sys.executable, "-c", _PATH_STAT_SCRIPT, request.operand or ""]
    if request.tool == TargetInspectionTool.EXECUTABLE_HELP:
        return [request.operand or "", "--help"]
    raise ValueError(f"unsupported inspection tool: {request.tool.value}")


def _result_from_outcome(
    request: TargetInspectionRequest,
    *,
    executor_kind: TargetExecutorKind,
    outcome: _ProcessOutcome,
    override_error: TargetExecutionErrorCode | None = None,
) -> TargetInspectionResult:
    error = override_error or outcome.error_code
    return TargetInspectionResult(
        request_id=request.request_id,
        request_sha256=request.canonical_sha256(),
        executor_kind=executor_kind,
        status=(
            TargetExecutionStatus.SUCCEEDED
            if error is None
            else TargetExecutionStatus.FAILED
        ),
        error_code=error,
        exit_code=outcome.exit_code,
        stdout=outcome.stdout,
        stderr=outcome.stderr,
        timed_out=error == TargetExecutionErrorCode.TIMEOUT,
        output_limited=error == TargetExecutionErrorCode.OUTPUT_LIMIT,
        cancelled=error == TargetExecutionErrorCode.CANCELLED,
        started_at=outcome.started_at,
        finished_at=outcome.finished_at,
    )


class LocalTargetExecutor:
    def __init__(
        self,
        runner: BoundedProcessRunner | None = None,
        *,
        transfer_root: Path | None = None,
        install_root: Path | None = None,
        enrollment_root: Path | None = None,
        adapter_install_root: Path | None = None,
        adapter_runner: AdapterRunner | None = None,
        adapter_sandbox_launcher: Path | None = None,
        deployment_authorization_registry: DeploymentAuthorizationKeyRegistry | None = None,
        require_runtime_evidence_authorization: bool = False,
    ) -> None:
        self._runner = runner or BoundedProcessRunner()
        self._transfer_root = transfer_root or (
            Path.home() / ".local" / "share" / "rolo" / "bootstrap" / "incoming"
        )
        self._install_root = install_root or (
            Path.home() / ".local" / "share" / "rolo" / "runtime"
        )
        self._enrollment_root = enrollment_root or (
            Path.home() / ".local" / "share" / "rolo" / "enrollment"
        )
        self._adapter_install_root = adapter_install_root or (
            Path.home() / ".local" / "share" / "rolo" / "adapters"
        )
        self._adapter_runner = adapter_runner
        self._adapter_sandbox_launcher = adapter_sandbox_launcher
        self._deployment_authorization_registry = deployment_authorization_registry
        self._require_runtime_evidence_authorization = (
            require_runtime_evidence_authorization
        )

    def _verify_deployment_authorization(
        self,
        request: BaseModel,
        *,
        authorization: object,
        target_id: str,
        action: ApprovalAction,
        approval_id: str | None = None,
    ) -> None:
        if self._deployment_authorization_registry is None:
            return
        from rolo.targets.deployment_authorization import (
            DeploymentAuthorizationProof,
            verify_deployment_request_authorization,
        )

        proof = (
            authorization
            if isinstance(authorization, DeploymentAuthorizationProof)
            else None
        )
        pin = self._deployment_authorization_registry.load(target_id)
        verify_deployment_request_authorization(
            request,
            authorization=proof,
            pin=pin,
            expected_target_id=target_id,
            expected_action=action,
            expected_approval_id=approval_id,
        )

    def inspect(
        self,
        request: TargetInspectionRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> TargetInspectionResult:
        outcome = self._runner.run(
            _ProcessSpec(
                argv=_inspection_argv(request),
                stdin="",
                timeout_s=request.timeout_s,
                max_stdout_bytes=request.max_stdout_bytes,
                max_stderr_bytes=request.max_stderr_bytes,
                environment=_safe_process_environment(),
            ),
            cancel_event=cancel_event,
        )
        return _result_from_outcome(
            request,
            executor_kind=TargetExecutorKind.LOCAL,
            outcome=outcome,
        )

    def transfer_package_chunk(
        self,
        request: TargetPackageTransferRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> TargetPackageTransferResult:
        if cancel_event is not None and cancel_event.is_set():
            return TargetPackageTransferResult(
                request_id=request.request_id,
                request_sha256=request.canonical_sha256(),
                executor_kind=TargetExecutorKind.LOCAL,
                status=TargetExecutionStatus.FAILED,
                error_code=TargetExecutionErrorCode.CANCELLED,
                received_size_bytes=0,
                file_size_bytes=request.file_size_bytes,
                complete=False,
            )
        from rolo.targets.package_transfer import TargetPackageChunkStore

        return TargetPackageChunkStore(self._transfer_root).apply(request)

    def execute_bootstrap(
        self,
        request: TargetBootstrapExecutionRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> TargetBootstrapExecutionResult:
        from rolo.targets.bootstrap_execution import (
            TargetBootstrapExecutionOperation,
            TargetBootstrapExecutionResult,
            TargetBootstrapExecutionService,
        )

        if cancel_event is not None and cancel_event.is_set():
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
                status=TargetExecutionStatus.FAILED,
                transport_error_code=TargetExecutionErrorCode.CANCELLED,
            )
        if request.operation == TargetBootstrapExecutionOperation.ROLLBACK:
            if self._deployment_authorization_registry is None:
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
                    status=TargetExecutionStatus.FAILED,
                    transport_error_code=TargetExecutionErrorCode.AUTHORIZATION_FAILED,
                )
            try:
                self._verify_deployment_authorization(
                    request,
                    authorization=request.authorization,
                    target_id=request.target_id,
                    action=ApprovalAction.ROLLBACK_TARGET_RUNTIME,
                    approval_id=request.approval_id,
                )
            except (OSError, ValueError):
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
                    status=TargetExecutionStatus.FAILED,
                    transport_error_code=TargetExecutionErrorCode.AUTHORIZATION_FAILED,
                )
        return TargetBootstrapExecutionService(
            incoming_root=self._transfer_root,
            install_root=self._install_root,
            authorization_key_registry=self._deployment_authorization_registry,
        ).execute(request)

    def execute_enrollment(
        self,
        request: TargetEnrollmentRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> TargetEnrollmentResult:
        from rolo.targets.enrollment import (
            TargetEnrollmentErrorCode,
            TargetEnrollmentResult,
            TargetEnrollmentService,
            TargetEnrollmentStateConflict,
        )

        def failed(
            *,
            transport: TargetExecutionErrorCode | None = None,
            enrollment: TargetEnrollmentErrorCode | None = None,
        ) -> TargetEnrollmentResult:
            return TargetEnrollmentResult(
                request_id=request.request_id,
                request_sha256=request.canonical_sha256(),
                operation=request.operation,
                target_id=request.target_id,
                robot_id=request.robot_id,
                executor_kind=TargetExecutorKind.LOCAL,
                execution_status=TargetExecutionStatus.FAILED,
                transport_error_code=transport,
                enrollment_error_code=enrollment,
            )

        if cancel_event is not None and cancel_event.is_set():
            return failed(transport=TargetExecutionErrorCode.CANCELLED)
        try:
            return TargetEnrollmentService(self._enrollment_root).execute(request)
        except TargetEnrollmentStateConflict:
            return failed(enrollment=TargetEnrollmentErrorCode.STATE_CONFLICT)
        except OSError:
            return failed(enrollment=TargetEnrollmentErrorCode.IO_ERROR)
        except ValueError:
            return failed(enrollment=TargetEnrollmentErrorCode.INVALID_STATE)

    def collect_evidence_v4(
        self,
        request: TargetEvidenceCollectionRequestV4,
        *,
        cancel_event: threading.Event | None = None,
    ) -> TargetEvidenceCollectionResultV4:
        from rolo.targets.enrollment import TargetEnrollmentService
        from rolo.targets.evidence_v4 import (
            TargetEvidenceCollectionResultV4,
            collect_target_evidence_v4,
        )

        def failed(error: TargetExecutionErrorCode) -> TargetEvidenceCollectionResultV4:
            return TargetEvidenceCollectionResultV4(
                request_id=request.request_id,
                request_sha256=request.canonical_sha256(),
                target_id=request.target_id,
                robot_id=request.evidence_request.robot_id,
                executor_kind=TargetExecutorKind.LOCAL,
                execution_status=TargetExecutionStatus.FAILED,
                error_code=error,
            )

        if cancel_event is not None and cancel_event.is_set():
            return failed(TargetExecutionErrorCode.CANCELLED)
        if self._deployment_authorization_registry is not None and (
            self._require_runtime_evidence_authorization
            or request.approval_id is not None
            or request.authorization is not None
        ):
            try:
                self._verify_deployment_authorization(
                    request,
                    authorization=request.authorization,
                    target_id=request.target_id,
                    action=ApprovalAction.COLLECT_RUNTIME_EVIDENCE,
                    approval_id=request.approval_id,
                )
            except (OSError, ValueError):
                return failed(TargetExecutionErrorCode.AUTHORIZATION_FAILED)
        try:
            bundle = collect_target_evidence_v4(
                request.evidence_request,
                TargetEnrollmentService(self._enrollment_root),
            )
            return TargetEvidenceCollectionResultV4(
                request_id=request.request_id,
                request_sha256=request.canonical_sha256(),
                target_id=request.target_id,
                robot_id=request.evidence_request.robot_id,
                executor_kind=TargetExecutorKind.LOCAL,
                execution_status=TargetExecutionStatus.SUCCEEDED,
                bundle=bundle,
            )
        except OSError:
            return failed(TargetExecutionErrorCode.IO_ERROR)
        except ValueError:
            return failed(TargetExecutionErrorCode.INTEGRITY_ERROR)

    def stage_adapter_release(
        self,
        request: AdapterReleaseStageRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> AdapterReleaseStageExecutionResult:
        from rolo.targets.adapter_release_transfer import (
            AdapterReleaseStageExecutionResult,
            AdapterReleaseStager,
            Ed25519AdapterReleaseVerifier,
        )

        def failed(error: TargetExecutionErrorCode) -> AdapterReleaseStageExecutionResult:
            return AdapterReleaseStageExecutionResult(
                request_id=request.request_id,
                request_sha256=request.canonical_sha256(),
                target_id=request.target_id,
                robot_id=request.robot_id,
                release_id=request.release_id,
                package_id=request.package_id,
                manifest_sha256=request.manifest_sha256,
                signing_key_id=request.signing_key_id,
                signing_public_key_sha256=request.signing_public_key_sha256,
                executor_kind=TargetExecutorKind.LOCAL,
                execution_status=TargetExecutionStatus.FAILED,
                error_code=error,
            )

        if cancel_event is not None and cancel_event.is_set():
            return failed(TargetExecutionErrorCode.CANCELLED)
        try:
            self._verify_deployment_authorization(
                request,
                authorization=request.authorization,
                target_id=request.target_id,
                action=ApprovalAction.STAGE_RELEASE,
                approval_id=request.approval_id,
            )
        except (OSError, ValueError):
            return failed(TargetExecutionErrorCode.AUTHORIZATION_FAILED)
        try:
            verifier = Ed25519AdapterReleaseVerifier(
                {request.signing_key_id: request.public_key_bytes()}
            )
            stage = AdapterReleaseStager(
                incoming_root=self._transfer_root,
                install_root=self._adapter_install_root,
            ).stage(request, verifier=verifier)
        except ValueError:
            return failed(TargetExecutionErrorCode.INTEGRITY_ERROR)
        except (OSError, TimeoutError):
            return failed(TargetExecutionErrorCode.IO_ERROR)
        return AdapterReleaseStageExecutionResult(
            request_id=request.request_id,
            request_sha256=request.canonical_sha256(),
            target_id=request.target_id,
            robot_id=request.robot_id,
            release_id=request.release_id,
            package_id=request.package_id,
            manifest_sha256=request.manifest_sha256,
            signing_key_id=request.signing_key_id,
            signing_public_key_sha256=request.signing_public_key_sha256,
            executor_kind=TargetExecutorKind.LOCAL,
            execution_status=TargetExecutionStatus.SUCCEEDED,
            stage=stage,
        )

    def activate_adapter_release(
        self,
        request: AdapterReleaseActivationRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> AdapterReleaseActivationExecutionResult:
        from rolo.targets.adapter_release_activation import (
            AdapterReleaseActivationErrorCode,
            AdapterReleaseActivationExecutionResult,
            AdapterReleaseActivationStateConflict,
            AdapterReleaseActivator,
        )

        def failed(
            error: AdapterReleaseActivationErrorCode,
        ) -> AdapterReleaseActivationExecutionResult:
            return AdapterReleaseActivationExecutionResult(
                request_id=request.request_id,
                request_sha256=request.canonical_sha256(),
                operation=request.operation,
                target_id=request.target_id,
                robot_id=request.robot_id,
                release_id=request.release_id,
                transfer_manifest_sha256=request.transfer_manifest_sha256,
                executor_kind=TargetExecutorKind.LOCAL,
                execution_status=TargetExecutionStatus.FAILED,
                activation_error_code=error,
            )

        if cancel_event is not None and cancel_event.is_set():
            return AdapterReleaseActivationExecutionResult(
                request_id=request.request_id,
                request_sha256=request.canonical_sha256(),
                operation=request.operation,
                target_id=request.target_id,
                robot_id=request.robot_id,
                release_id=request.release_id,
                transfer_manifest_sha256=request.transfer_manifest_sha256,
                executor_kind=TargetExecutorKind.LOCAL,
                execution_status=TargetExecutionStatus.FAILED,
                transport_error_code=TargetExecutionErrorCode.CANCELLED,
            )
        try:
            self._verify_deployment_authorization(
                request,
                authorization=request.authorization,
                target_id=request.target_id,
                action=(
                    ApprovalAction.ACTIVATE_RELEASE
                    if request.operation.value == "ACTIVATE"
                    else ApprovalAction.ROLLBACK_RELEASE
                ),
                approval_id=request.approval_id,
            )
        except (OSError, ValueError):
            return AdapterReleaseActivationExecutionResult(
                request_id=request.request_id,
                request_sha256=request.canonical_sha256(),
                operation=request.operation,
                target_id=request.target_id,
                robot_id=request.robot_id,
                release_id=request.release_id,
                transfer_manifest_sha256=request.transfer_manifest_sha256,
                executor_kind=TargetExecutorKind.LOCAL,
                execution_status=TargetExecutionStatus.FAILED,
                transport_error_code=TargetExecutionErrorCode.AUTHORIZATION_FAILED,
            )
        try:
            result = AdapterReleaseActivator(self._adapter_install_root).execute(request)
        except AdapterReleaseActivationStateConflict:
            return failed(AdapterReleaseActivationErrorCode.STATE_CONFLICT)
        except OSError:
            return failed(AdapterReleaseActivationErrorCode.IO_ERROR)
        except ValueError as exc:
            code = (
                AdapterReleaseActivationErrorCode.INVALID_GATE
                if "gate" in str(exc).casefold() or "receipt" in str(exc).casefold()
                else AdapterReleaseActivationErrorCode.INVALID_STAGE
            )
            return failed(code)
        return AdapterReleaseActivationExecutionResult(
            request_id=request.request_id,
            request_sha256=request.canonical_sha256(),
            operation=request.operation,
            target_id=request.target_id,
            robot_id=request.robot_id,
            release_id=request.release_id,
            transfer_manifest_sha256=request.transfer_manifest_sha256,
            executor_kind=TargetExecutorKind.LOCAL,
            execution_status=TargetExecutionStatus.SUCCEEDED,
            result=result,
        )

    def status_adapter_release(
        self,
        request: AdapterReleaseStatusRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> AdapterReleaseStatusExecutionResult:
        from rolo.targets.adapter_release_reconciliation import (
            AdapterReleaseStatusExecutionResult,
            AdapterReleaseStatusService,
        )

        desired = request.desired

        def failed(error: TargetExecutionErrorCode) -> AdapterReleaseStatusExecutionResult:
            return AdapterReleaseStatusExecutionResult(
                request_id=request.request_id,
                request_sha256=request.canonical_sha256(),
                target_id=desired.target_id,
                robot_id=desired.robot_id,
                executor_kind=TargetExecutorKind.LOCAL,
                execution_status=TargetExecutionStatus.FAILED,
                error_code=error,
            )

        if cancel_event is not None and cancel_event.is_set():
            return failed(TargetExecutionErrorCode.CANCELLED)
        try:
            snapshot = AdapterReleaseStatusService(self._adapter_install_root).observe(request)
        except ValueError:
            return failed(TargetExecutionErrorCode.INTEGRITY_ERROR)
        except OSError:
            return failed(TargetExecutionErrorCode.IO_ERROR)
        return AdapterReleaseStatusExecutionResult(
            request_id=request.request_id,
            request_sha256=request.canonical_sha256(),
            target_id=desired.target_id,
            robot_id=desired.robot_id,
            executor_kind=TargetExecutorKind.LOCAL,
            execution_status=TargetExecutionStatus.SUCCEEDED,
            snapshot=snapshot,
        )

    def detect_project_evidence(
        self,
        request: TargetProjectEvidenceRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> TargetProjectEvidenceExecutionResult:
        from rolo.targets.runtime_deployment import (
            TargetProjectEvidenceExecutionResult,
            detect_target_project_evidence,
        )

        workspace = request.workspace

        def failed(error: TargetExecutionErrorCode) -> TargetProjectEvidenceExecutionResult:
            return TargetProjectEvidenceExecutionResult(
                request_id=request.request_id,
                request_sha256=request.canonical_sha256(),
                target_id=workspace.target_id,
                robot_id=workspace.robot_id,
                workspace_id=workspace.workspace_id,
                executor_kind=TargetExecutorKind.LOCAL,
                execution_status=TargetExecutionStatus.FAILED,
                error_code=error,
            )

        if cancel_event is not None and cancel_event.is_set():
            return failed(TargetExecutionErrorCode.CANCELLED)
        try:
            self._verify_deployment_authorization(
                request,
                authorization=request.authorization,
                target_id=workspace.target_id,
                action=ApprovalAction.READ_PROJECT_EVIDENCE,
                approval_id=request.approval_id,
            )
        except (OSError, ValueError):
            return failed(TargetExecutionErrorCode.AUTHORIZATION_FAILED)
        try:
            snapshot = detect_target_project_evidence(request)
        except ValueError:
            return failed(TargetExecutionErrorCode.INTEGRITY_ERROR)
        except OSError:
            return failed(TargetExecutionErrorCode.IO_ERROR)
        return TargetProjectEvidenceExecutionResult(
            request_id=request.request_id,
            request_sha256=request.canonical_sha256(),
            target_id=workspace.target_id,
            robot_id=workspace.robot_id,
            workspace_id=workspace.workspace_id,
            executor_kind=TargetExecutorKind.LOCAL,
            execution_status=TargetExecutionStatus.SUCCEEDED,
            snapshot=snapshot,
        )

    def discover_source(
        self,
        request: TargetSourceDiscoveryRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> TargetSourceDiscoveryExecutionResult:
        from rolo.targets.source_discovery import (
            TargetSourceDiscoveryExecutionResult,
            discover_target_source,
        )

        workspace = request.workspace

        def failed(error: TargetExecutionErrorCode) -> TargetSourceDiscoveryExecutionResult:
            return TargetSourceDiscoveryExecutionResult(
                request_id=request.request_id,
                request_sha256=request.canonical_sha256(),
                target_id=workspace.target_id,
                robot_id=workspace.robot_id,
                workspace_id=workspace.workspace_id,
                executor_kind=TargetExecutorKind.LOCAL,
                execution_status=TargetExecutionStatus.FAILED,
                error_code=error,
            )

        if cancel_event is not None and cancel_event.is_set():
            return failed(TargetExecutionErrorCode.CANCELLED)
        try:
            self._verify_deployment_authorization(
                request,
                authorization=request.authorization,
                target_id=workspace.target_id,
                action=ApprovalAction.ANALYZE_PROJECT_SOURCE,
                approval_id=request.approval_id,
            )
        except (OSError, ValueError):
            return failed(TargetExecutionErrorCode.AUTHORIZATION_FAILED)
        try:
            snapshot = discover_target_source(request)
        except ValueError:
            return failed(TargetExecutionErrorCode.INTEGRITY_ERROR)
        except OSError:
            return failed(TargetExecutionErrorCode.IO_ERROR)
        return TargetSourceDiscoveryExecutionResult(
            request_id=request.request_id,
            request_sha256=request.canonical_sha256(),
            target_id=workspace.target_id,
            robot_id=workspace.robot_id,
            workspace_id=workspace.workspace_id,
            executor_kind=TargetExecutorKind.LOCAL,
            execution_status=TargetExecutionStatus.SUCCEEDED,
            snapshot=snapshot,
        )

    def describe_adapter_release(
        self,
        request: AdapterReleaseDescribeRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> AdapterReleaseDescribeExecutionResult:
        from rolo.adapter_runner import BoundedAdapterRunner
        from rolo.core.config import get_settings
        from rolo.targets.adapter_release_transfer import (
            Ed25519AdapterReleaseVerifier,
            load_verified_adapter_release_transfer,
        )
        from rolo.targets.enrollment import TargetEnrollmentService
        from rolo.targets.runtime_deployment import (
            AdapterReleaseDescribeExecutionResult,
            execute_target_describe,
        )

        describe = request.describe

        def failed(error: TargetExecutionErrorCode) -> AdapterReleaseDescribeExecutionResult:
            return AdapterReleaseDescribeExecutionResult(
                request_id=request.request_id,
                request_sha256=request.canonical_sha256(),
                target_id=describe.target_id,
                robot_id=describe.robot_id,
                release_id=describe.release_id,
                transfer_manifest_sha256=request.transfer_manifest_sha256,
                executor_kind=TargetExecutorKind.LOCAL,
                execution_status=TargetExecutionStatus.FAILED,
                error_code=error,
            )

        if cancel_event is not None and cancel_event.is_set():
            return failed(TargetExecutionErrorCode.CANCELLED)
        try:
            self._verify_deployment_authorization(
                request,
                authorization=request.authorization,
                target_id=describe.target_id,
                action=ApprovalAction.DESCRIBE_RELEASE,
            )
        except (OSError, ValueError):
            return failed(TargetExecutionErrorCode.AUTHORIZATION_FAILED)
        try:
            verifier = Ed25519AdapterReleaseVerifier(
                {request.signing_key_id: request.public_key_bytes()}
            )
            stage_root = (
                self._adapter_install_root
                / "robots"
                / describe.robot_id
                / "staged"
                / f"{describe.release_id}-{describe.release_manifest_sha256[:16]}"
            )
            _, transfer, signature, context = load_verified_adapter_release_transfer(
                stage_root,
                verifier,
            )
            if (
                transfer.canonical_sha256() != request.transfer_manifest_sha256
                or transfer.target_id != describe.target_id
                or transfer.robot_id != describe.robot_id
                or transfer.release_id != describe.release_id
                or transfer.release_manifest_sha256
                != describe.release_manifest_sha256
                or transfer.bundle_manifest_sha256 != describe.bundle_manifest_sha256
                or transfer.runtime_context_sha256 != describe.runtime_context_sha256
                or signature.key_id != request.signing_key_id
                or verifier.public_key_sha256(signature.key_id)
                != request.signing_public_key_sha256
            ):
                raise ValueError("adapter release describe staged transfer mismatch")
            launcher = self._adapter_sandbox_launcher or (
                get_settings().rolo_adapter_sandbox_launcher
            )
            if launcher is None:
                return failed(TargetExecutionErrorCode.CONFIGURATION_ERROR)
            runner = self._adapter_runner or BoundedAdapterRunner(
                sandbox_launcher=launcher,
                max_address_space_bytes=context.sandbox_budget.max_address_space_bytes,
                max_processes=context.sandbox_budget.max_processes,
            )
            result = execute_target_describe(
                describe,
                context=context,
                release_root=stage_root / "release",
                sandbox_launcher=launcher,
                service=TargetEnrollmentService(self._enrollment_root),
                runner=runner,
            )
        except OSError:
            return failed(TargetExecutionErrorCode.IO_ERROR)
        except ValueError:
            return failed(TargetExecutionErrorCode.INTEGRITY_ERROR)
        return AdapterReleaseDescribeExecutionResult(
            request_id=request.request_id,
            request_sha256=request.canonical_sha256(),
            target_id=describe.target_id,
            robot_id=describe.robot_id,
            release_id=describe.release_id,
            transfer_manifest_sha256=request.transfer_manifest_sha256,
            executor_kind=TargetExecutorKind.LOCAL,
            execution_status=TargetExecutionStatus.SUCCEEDED,
            describe=result,
        )


def _ssh_failure_code(outcome: _ProcessOutcome) -> TargetExecutionErrorCode:
    if outcome.error_code in {
        TargetExecutionErrorCode.CANCELLED,
        TargetExecutionErrorCode.CONFIGURATION_ERROR,
        TargetExecutionErrorCode.CREDENTIAL_UNAVAILABLE,
        TargetExecutionErrorCode.OUTPUT_LIMIT,
        TargetExecutionErrorCode.SPAWN_FAILED,
        TargetExecutionErrorCode.TIMEOUT,
    }:
        return outcome.error_code
    detail = outcome.stderr.casefold()
    if "host key verification failed" in detail or "identification has changed" in detail:
        return TargetExecutionErrorCode.HOST_KEY_VERIFICATION_FAILED
    if "permission denied" in detail or "authentication failed" in detail:
        return TargetExecutionErrorCode.AUTHENTICATION_FAILED
    if outcome.exit_code is not None and outcome.exit_code != 255:
        return TargetExecutionErrorCode.NON_ZERO_EXIT
    return TargetExecutionErrorCode.CONNECTION_FAILED


def _quote_ssh_config(value: str) -> str:
    if any(character in value for character in ("\x00", "\r", "\n")):
        raise ValueError("SSH config value contains control characters")
    return '"' + value.replace("\\", "/").replace('"', '\\"') + '"'


def _known_hosts_identity(profile: TargetConnectionProfile) -> Path:
    known_hosts = Path(profile.known_hosts_path).expanduser().resolve()
    if not known_hosts.is_file():
        raise ValueError("pinned SSH known_hosts file is unavailable")
    if known_hosts.stat().st_size > 2_000_000:
        raise ValueError("pinned SSH known_hosts file exceeded its size limit")
    expected_host = profile.host if profile.port == 22 else f"[{profile.host}]:{profile.port}"
    expected_fingerprint = profile.expected_host_key_sha256
    found_ca = False
    try:
        lines = known_hosts.read_text(encoding="utf-8").splitlines()
    except UnicodeError as exc:
        raise ValueError("pinned SSH known_hosts file is not UTF-8") from exc
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        marker = fields[0] if fields[0].startswith("@") else None
        offset = 1 if marker is not None else 0
        if len(fields) < offset + 3:
            continue
        hosts, encoded_key = fields[offset], fields[offset + 2]
        if expected_host not in hosts.split(","):
            continue
        if marker == "@cert-authority":
            found_ca = True
        if expected_fingerprint is not None:
            try:
                key = b64decode(encoded_key, validate=True)
            except ValueError:
                continue
            fingerprint = "SHA256:" + b64encode(hashlib.sha256(key).digest()).decode(
                "ascii"
            ).rstrip("=")
            if fingerprint == expected_fingerprint:
                return known_hosts
    if expected_fingerprint is not None:
        raise ValueError("pinned SSH host fingerprint is absent from known_hosts")
    if profile.ssh_ca_ref is not None and not found_ca:
        raise ValueError("pinned SSH CA entry is absent from known_hosts")
    return known_hosts


class SshTargetExecutor:
    def __init__(
        self,
        connection: TargetConnectionProfile,
        credential_resolver: CredentialResolver,
        *,
        proxy_connection: TargetConnectionProfile | None = None,
        runner: BoundedProcessRunner | None = None,
        ssh_executable: str = "ssh",
        connect_timeout_s: int = 10,
        credential_purpose: CredentialPurpose = CredentialPurpose.SSH_RUNTIME,
    ) -> None:
        if connection.proxy_jump_profile_id:
            if proxy_connection is None:
                raise ValueError("SSH proxy connection profile is required")
            if proxy_connection.connection_profile_id != connection.proxy_jump_profile_id:
                raise ValueError("SSH proxy connection profile identity mismatch")
        elif proxy_connection is not None:
            raise ValueError("unexpected SSH proxy connection profile")
        if not 1 <= connect_timeout_s <= 300:
            raise ValueError("SSH connect timeout must be between 1 and 300 seconds")
        self._connection = connection
        self._proxy = proxy_connection
        self._credentials = credential_resolver
        self._runner = runner or BoundedProcessRunner()
        self._ssh_executable = ssh_executable
        self._connect_timeout_s = connect_timeout_s
        self._credential_purpose = credential_purpose

    def _credential_path(self, profile: TargetConnectionProfile) -> Path:
        reference = profile.credential_ref
        if self._credential_purpose == CredentialPurpose.SSH_PROVISIONING:
            if profile.provisioning_credential_ref is None:
                raise ValueError("SSH provisioning credential is not configured")
            reference = profile.provisioning_credential_ref
        elif (
            self._credential_purpose == CredentialPurpose.SSH_RUNTIME
            and profile.runtime_credential_ref is not None
        ):
            reference = profile.runtime_credential_ref
        credential = self._credentials.resolve(
            reference,
            purpose=self._credential_purpose,
        )
        if credential.secret_path is None or not credential.secret_path.is_file():
            raise ValueError("SSH credential provider did not return an available identity file")
        return credential.secret_path.resolve()

    def _profile_lines(
        self,
        alias: str,
        profile: TargetConnectionProfile,
        identity: Path,
    ) -> list[str]:
        known_hosts = _known_hosts_identity(profile)
        user = profile.user
        if self._credential_purpose == CredentialPurpose.SSH_PROVISIONING:
            if profile.provisioning_user is None:
                raise ValueError("SSH provisioning user is not configured")
            user = profile.provisioning_user
        elif (
            self._credential_purpose == CredentialPurpose.SSH_RUNTIME
            and profile.runtime_user is not None
        ):
            user = profile.runtime_user
        return [
            f"Host {alias}",
            f"  HostName {_quote_ssh_config(profile.host)}",
            f"  User {_quote_ssh_config(user)}",
            f"  Port {profile.port}",
            f"  IdentityFile {_quote_ssh_config(str(identity))}",
            "  IdentitiesOnly yes",
            "  IdentityAgent none",
            "  BatchMode yes",
            "  PasswordAuthentication no",
            "  KbdInteractiveAuthentication no",
            "  StrictHostKeyChecking yes",
            f"  UserKnownHostsFile {_quote_ssh_config(str(known_hosts))}",
            "  GlobalKnownHostsFile none",
            "  ForwardAgent no",
            "  ClearAllForwardings yes",
            "  RequestTTY no",
            "  PermitLocalCommand no",
            f"  ConnectTimeout {self._connect_timeout_s}",
        ]

    def _run_remote(
        self,
        *,
        remote_command: list[str],
        stdin: str,
        timeout_s: float,
        max_stdout_bytes: int,
        max_stderr_bytes: int,
        cancel_event: threading.Event | None,
    ) -> _ProcessOutcome:
        started_at = datetime.now(timezone.utc)
        try:
            target_identity = self._credential_path(self._connection)
            proxy_identity = self._credential_path(self._proxy) if self._proxy else None
        except (OSError, ValueError):
            return _ProcessOutcome(
                error_code=TargetExecutionErrorCode.CREDENTIAL_UNAVAILABLE,
                exit_code=None,
                stdout="",
                stderr="SSH credential is unavailable",
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )
        try:
            with tempfile.TemporaryDirectory(prefix="rolo-ssh-") as temporary:
                config_path = Path(temporary) / "config"
                lines: list[str] = []
                if self._proxy is not None and proxy_identity is not None:
                    lines.extend(
                        self._profile_lines("rolo-proxy", self._proxy, proxy_identity)
                    )
                    lines.append("")
                lines.extend(
                    self._profile_lines("rolo-target", self._connection, target_identity)
                )
                if self._proxy is not None:
                    lines.append("  ProxyJump rolo-proxy")
                config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                if os.name == "posix":
                    config_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
                redactions = tuple(
                    str(path)
                    for path in (target_identity, proxy_identity)
                    if path is not None
                )
                return self._runner.run(
                    _ProcessSpec(
                        argv=[
                            self._ssh_executable,
                            "-F",
                            str(config_path),
                            "-T",
                            "-oBatchMode=yes",
                            "-oStrictHostKeyChecking=yes",
                            "-oForwardAgent=no",
                            "-oClearAllForwardings=yes",
                            "-oRequestTTY=no",
                            "rolo-target",
                            *remote_command,
                        ],
                        stdin=stdin,
                        timeout_s=timeout_s + self._connect_timeout_s,
                        max_stdout_bytes=min(_MAX_PROTOCOL_BYTES, max_stdout_bytes),
                        max_stderr_bytes=max_stderr_bytes,
                        redactions=redactions,
                        environment=_safe_process_environment(),
                    ),
                    cancel_event=cancel_event,
                )
        except ValueError as exc:
            detail = str(exc)[:max_stderr_bytes]
        except OSError:
            detail = "SSH executor configuration failed"
        return _ProcessOutcome(
            error_code=TargetExecutionErrorCode.CONFIGURATION_ERROR,
            exit_code=None,
            stdout="",
            stderr=detail,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
        )

    def inspect(
        self,
        request: TargetInspectionRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> TargetInspectionResult:
        bootstrap_capabilities = (
            request.tool == TargetInspectionTool.RUNTIME_CAPABILITIES
            and self._credential_purpose == CredentialPurpose.SSH_BOOTSTRAP
        )
        outcome = self._run_remote(
            remote_command=(
                ["robotctl", "target-executor", "runtime-capabilities"]
                if bootstrap_capabilities
                else ["robotctl", "target-executor", "inspect"]
            ),
            stdin=("" if bootstrap_capabilities else request.model_dump_json()),
            timeout_s=request.timeout_s,
            max_stdout_bytes=(
                request.max_stdout_bytes + request.max_stderr_bytes + 16_384
            ),
            max_stderr_bytes=request.max_stderr_bytes,
            cancel_event=cancel_event,
        )
        if outcome.error_code is not None or outcome.exit_code != 0:
            return _result_from_outcome(
                request,
                executor_kind=TargetExecutorKind.SSH,
                outcome=outcome,
                override_error=_ssh_failure_code(outcome),
            )
        if request.tool == TargetInspectionTool.RUNTIME_CAPABILITIES:
            return _result_from_outcome(
                request,
                executor_kind=TargetExecutorKind.SSH,
                outcome=outcome,
            )
        try:
            result = TargetInspectionResult.model_validate_json(outcome.stdout)
        except ValueError:
            invalid = _ProcessOutcome(
                error_code=TargetExecutionErrorCode.PROTOCOL_ERROR,
                exit_code=outcome.exit_code,
                stdout="",
                stderr="target inspection returned invalid protocol JSON",
                started_at=outcome.started_at,
                finished_at=outcome.finished_at,
            )
            return _result_from_outcome(
                request,
                executor_kind=TargetExecutorKind.SSH,
                outcome=invalid,
            )
        if (
            result.request_id != request.request_id
            or result.request_sha256 != request.canonical_sha256()
        ):
            invalid = outcome.__class__(
                error_code=TargetExecutionErrorCode.PROTOCOL_ERROR,
                exit_code=outcome.exit_code,
                stdout="",
                stderr="target inspection response identity mismatch",
                started_at=outcome.started_at,
                finished_at=outcome.finished_at,
            )
            return _result_from_outcome(
                request,
                executor_kind=TargetExecutorKind.SSH,
                outcome=invalid,
            )
        return result.model_copy(update={"executor_kind": TargetExecutorKind.SSH})

    def provision_host(
        self,
        plan: TargetHostProvisioningPlan,
        *,
        cancel_event: threading.Event | None = None,
    ) -> TargetHostProvisioningExecutionResult:
        from rolo.targets.host_provisioning import (
            TargetHostProvisioningExecutionError,
            TargetHostProvisioningExecutionResult,
            TargetHostProvisioningExecutionStatus,
            host_provisioning_remote_command,
        )

        def failed(
            error: TargetHostProvisioningExecutionError,
            *,
            started_at: datetime | None = None,
            finished_at: datetime | None = None,
        ) -> TargetHostProvisioningExecutionResult:
            now = datetime.now(timezone.utc)
            return TargetHostProvisioningExecutionResult(
                target_id=plan.target_id,
                plan_sha256=plan.canonical_sha256(),
                status=TargetHostProvisioningExecutionStatus.FAILED,
                error_code=error,
                started_at=started_at or now,
                finished_at=finished_at or now,
            )

        if self._credential_purpose != CredentialPurpose.SSH_PROVISIONING:
            return failed(TargetHostProvisioningExecutionError.CREDENTIAL_UNAVAILABLE)
        if cancel_event is not None and cancel_event.is_set():
            return failed(TargetHostProvisioningExecutionError.CANCELLED)
        outcome = self._run_remote(
            remote_command=[host_provisioning_remote_command()],
            stdin=plan.model_dump_json(),
            timeout_s=120.0,
            max_stdout_bytes=128 * 1024,
            max_stderr_bytes=32 * 1024,
            cancel_event=cancel_event,
        )
        if outcome.error_code is not None or outcome.exit_code != 0:
            error = (
                TargetHostProvisioningExecutionError.CANCELLED
                if outcome.error_code == TargetExecutionErrorCode.CANCELLED
                else TargetHostProvisioningExecutionError.CREDENTIAL_UNAVAILABLE
                if outcome.error_code == TargetExecutionErrorCode.CREDENTIAL_UNAVAILABLE
                else TargetHostProvisioningExecutionError.CONNECTION_FAILED
            )
            return failed(
                error,
                started_at=outcome.started_at,
                finished_at=outcome.finished_at,
            )
        try:
            result = TargetHostProvisioningExecutionResult.model_validate_json(
                outcome.stdout
            )
        except ValueError:
            return failed(
                TargetHostProvisioningExecutionError.PROTOCOL_ERROR,
                started_at=outcome.started_at,
                finished_at=outcome.finished_at,
            )
        if (
            result.target_id != plan.target_id
            or result.plan_sha256 != plan.canonical_sha256()
        ):
            return failed(
                TargetHostProvisioningExecutionError.PROTOCOL_ERROR,
                started_at=outcome.started_at,
                finished_at=outcome.finished_at,
            )
        return result

    def observe_host_provisioning(
        self,
        plan: TargetHostProvisioningPlan,
        *,
        cancel_event: threading.Event | None = None,
    ) -> TargetHostProvisioningObservation:
        """Observe privileged host state without replaying the provisioning plan."""

        from rolo.targets.host_provisioning import (
            TargetHostProvisioningExecutionError,
            TargetHostProvisioningObservation,
            TargetHostProvisioningObservationStatus,
            host_provisioning_observer_remote_command,
        )

        def failed(
            error: TargetHostProvisioningExecutionError,
        ) -> TargetHostProvisioningObservation:
            return TargetHostProvisioningObservation(
                target_id=plan.target_id,
                expected_plan_sha256=plan.canonical_sha256(),
                status=TargetHostProvisioningObservationStatus.FAILED,
                error_code=error,
                observed_at=datetime.now(timezone.utc),
            )

        if self._credential_purpose != CredentialPurpose.SSH_PROVISIONING:
            return failed(TargetHostProvisioningExecutionError.CREDENTIAL_UNAVAILABLE)
        if cancel_event is not None and cancel_event.is_set():
            return failed(TargetHostProvisioningExecutionError.CANCELLED)
        outcome = self._run_remote(
            remote_command=[host_provisioning_observer_remote_command()],
            stdin=plan.model_dump_json(),
            timeout_s=60.0,
            max_stdout_bytes=128 * 1024,
            max_stderr_bytes=32 * 1024,
            cancel_event=cancel_event,
        )
        if outcome.error_code is not None or outcome.exit_code != 0:
            error = (
                TargetHostProvisioningExecutionError.CANCELLED
                if outcome.error_code == TargetExecutionErrorCode.CANCELLED
                else TargetHostProvisioningExecutionError.CREDENTIAL_UNAVAILABLE
                if outcome.error_code == TargetExecutionErrorCode.CREDENTIAL_UNAVAILABLE
                else TargetHostProvisioningExecutionError.CONNECTION_FAILED
            )
            return failed(error)
        try:
            observation = TargetHostProvisioningObservation.model_validate_json(
                outcome.stdout
            )
        except ValueError:
            return failed(TargetHostProvisioningExecutionError.PROTOCOL_ERROR)
        if (
            observation.target_id != plan.target_id
            or observation.expected_plan_sha256 != plan.canonical_sha256()
        ):
            return failed(TargetHostProvisioningExecutionError.PROTOCOL_ERROR)
        return observation

    def execute_host_service(
        self,
        request: TargetHostServiceRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> TargetHostServiceExecutionResult:
        from rolo.targets.host_service import (
            TargetHostServiceError,
            TargetHostServiceExecutionResult,
            TargetHostServiceStatus,
            host_service_remote_command,
        )

        def failed(error: TargetHostServiceError) -> TargetHostServiceExecutionResult:
            now = datetime.now(timezone.utc)
            return TargetHostServiceExecutionResult(
                request_id=request.request_id,
                request_sha256=request.canonical_sha256(),
                target_id=request.target_id,
                operation=request.operation,
                status=TargetHostServiceStatus.FAILED,
                error_code=error,
                started_at=now,
                finished_at=now,
            )

        if self._credential_purpose != CredentialPurpose.SSH_PROVISIONING:
            return failed(TargetHostServiceError.CREDENTIAL_UNAVAILABLE)
        if cancel_event is not None and cancel_event.is_set():
            return failed(TargetHostServiceError.CANCELLED)
        outcome = self._run_remote(
            remote_command=[host_service_remote_command()],
            stdin=request.model_dump_json(),
            timeout_s=60.0,
            max_stdout_bytes=128 * 1024,
            max_stderr_bytes=32 * 1024,
            cancel_event=cancel_event,
        )
        if outcome.error_code is not None or outcome.exit_code != 0:
            error = (
                TargetHostServiceError.CANCELLED
                if outcome.error_code == TargetExecutionErrorCode.CANCELLED
                else TargetHostServiceError.CREDENTIAL_UNAVAILABLE
                if outcome.error_code == TargetExecutionErrorCode.CREDENTIAL_UNAVAILABLE
                else TargetHostServiceError.CONNECTION_FAILED
            )
            return failed(error)
        try:
            result = TargetHostServiceExecutionResult.model_validate_json(outcome.stdout)
        except ValueError:
            return failed(TargetHostServiceError.PROTOCOL_ERROR)
        if (
            result.request_id != request.request_id
            or result.request_sha256 != request.canonical_sha256()
            or result.target_id != request.target_id
            or result.operation != request.operation
        ):
            return failed(TargetHostServiceError.PROTOCOL_ERROR)
        return result

    def execute_bootstrap(
        self,
        request: TargetBootstrapExecutionRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> TargetBootstrapExecutionResult:
        from rolo.targets.bootstrap_execution import (
            TargetBootstrapExecutionOperation,
            TargetBootstrapExecutionResult,
        )

        mutation = request.operation in {
            TargetBootstrapExecutionOperation.INSTALL_ACTIVATE,
            TargetBootstrapExecutionOperation.ROLLBACK,
        }
        if mutation and self._credential_purpose != CredentialPurpose.SSH_BOOTSTRAP:
            return TargetBootstrapExecutionResult(
                request_id=request.request_id,
                request_sha256=request.canonical_sha256(),
                target_id=request.target_id,
                package_id=request.package_id,
                manifest_sha256=request.manifest_sha256,
                signing_key_id=request.signing_key_id,
                signing_public_key_sha256=request.signing_public_key_sha256,
                executor_kind=TargetExecutorKind.SSH,
                operation=request.operation,
                status=TargetExecutionStatus.FAILED,
                transport_error_code=TargetExecutionErrorCode.CONFIGURATION_ERROR,
            )
        remote_command = (
            ["robotctl", "target-executor", "bootstrap"]
            if (
                self._credential_purpose == CredentialPurpose.SSH_RUNTIME
                or request.operation == TargetBootstrapExecutionOperation.ROLLBACK
            )
            else ["robotctl", "target-executor", "bootstrap"]
        )
        outcome = self._run_remote(
            remote_command=remote_command,
            stdin=request.model_dump_json(),
            timeout_s=request.timeout_s,
            max_stdout_bytes=512 * 1024,
            max_stderr_bytes=32 * 1024,
            cancel_event=cancel_event,
        )
        if outcome.error_code is not None or outcome.exit_code != 0:
            return TargetBootstrapExecutionResult(
                request_id=request.request_id,
                request_sha256=request.canonical_sha256(),
                target_id=request.target_id,
                package_id=request.package_id,
                manifest_sha256=request.manifest_sha256,
                signing_key_id=request.signing_key_id,
                signing_public_key_sha256=request.signing_public_key_sha256,
                executor_kind=TargetExecutorKind.SSH,
                operation=request.operation,
                status=TargetExecutionStatus.FAILED,
                transport_error_code=_ssh_failure_code(outcome),
            )
        try:
            result = TargetBootstrapExecutionResult.model_validate_json(outcome.stdout)
        except ValueError:
            return TargetBootstrapExecutionResult(
                request_id=request.request_id,
                request_sha256=request.canonical_sha256(),
                target_id=request.target_id,
                package_id=request.package_id,
                manifest_sha256=request.manifest_sha256,
                signing_key_id=request.signing_key_id,
                signing_public_key_sha256=request.signing_public_key_sha256,
                executor_kind=TargetExecutorKind.SSH,
                operation=request.operation,
                status=TargetExecutionStatus.FAILED,
                transport_error_code=TargetExecutionErrorCode.PROTOCOL_ERROR,
            )
        if (
            result.request_id != request.request_id
            or result.request_sha256 != request.canonical_sha256()
            or result.target_id != request.target_id
            or result.package_id != request.package_id
            or result.manifest_sha256 != request.manifest_sha256
            or result.signing_key_id != request.signing_key_id
            or (
                result.signing_public_key_sha256
                != request.signing_public_key_sha256
            )
            or result.operation != request.operation
        ):
            return TargetBootstrapExecutionResult(
                request_id=request.request_id,
                request_sha256=request.canonical_sha256(),
                target_id=request.target_id,
                package_id=request.package_id,
                manifest_sha256=request.manifest_sha256,
                signing_key_id=request.signing_key_id,
                signing_public_key_sha256=request.signing_public_key_sha256,
                executor_kind=TargetExecutorKind.SSH,
                operation=request.operation,
                status=TargetExecutionStatus.FAILED,
                transport_error_code=TargetExecutionErrorCode.PROTOCOL_ERROR,
            )
        return result.model_copy(update={"executor_kind": TargetExecutorKind.SSH})

    def execute_enrollment(
        self,
        request: TargetEnrollmentRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> TargetEnrollmentResult:
        from rolo.targets.enrollment import (
            TargetEnrollmentOperation,
            TargetEnrollmentResult,
            verify_enrollment_attestation,
        )

        mutation = request.operation in {
            TargetEnrollmentOperation.ENROLL,
            TargetEnrollmentOperation.ROTATE,
        }

        def failed(error: TargetExecutionErrorCode) -> TargetEnrollmentResult:
            return TargetEnrollmentResult(
                request_id=request.request_id,
                request_sha256=request.canonical_sha256(),
                operation=request.operation,
                target_id=request.target_id,
                robot_id=request.robot_id,
                executor_kind=TargetExecutorKind.SSH,
                execution_status=TargetExecutionStatus.FAILED,
                transport_error_code=error,
            )

        if mutation and self._credential_purpose != CredentialPurpose.SSH_BOOTSTRAP:
            return failed(TargetExecutionErrorCode.CONFIGURATION_ERROR)
        outcome = self._run_remote(
            remote_command=["robotctl", "target-executor", "enroll"],
            stdin=request.model_dump_json(),
            timeout_s=request.timeout_s,
            max_stdout_bytes=256 * 1024,
            max_stderr_bytes=32 * 1024,
            cancel_event=cancel_event,
        )
        if outcome.error_code is not None or outcome.exit_code != 0:
            return failed(_ssh_failure_code(outcome))
        try:
            result = TargetEnrollmentResult.model_validate_json(outcome.stdout)
            verify_enrollment_attestation(request, result)
        except ValueError:
            return failed(TargetExecutionErrorCode.PROTOCOL_ERROR)
        return result.model_copy(update={"executor_kind": TargetExecutorKind.SSH})

    def collect_evidence_v4(
        self,
        request: TargetEvidenceCollectionRequestV4,
        *,
        cancel_event: threading.Event | None = None,
    ) -> TargetEvidenceCollectionResultV4:
        from rolo.targets.evidence_v4 import TargetEvidenceCollectionResultV4

        def failed(error: TargetExecutionErrorCode) -> TargetEvidenceCollectionResultV4:
            return TargetEvidenceCollectionResultV4(
                request_id=request.request_id,
                request_sha256=request.canonical_sha256(),
                target_id=request.target_id,
                robot_id=request.evidence_request.robot_id,
                executor_kind=TargetExecutorKind.SSH,
                execution_status=TargetExecutionStatus.FAILED,
                error_code=error,
            )

        authorized_runtime = (
            self._credential_purpose == CredentialPurpose.SSH_RUNTIME
            and request.approval_id is not None
            and request.authorization is not None
        )
        bootstrap_collection = (
            self._credential_purpose == CredentialPurpose.SSH_BOOTSTRAP
            and request.approval_id is None
            and request.authorization is None
        )
        if not (authorized_runtime or bootstrap_collection):
            return failed(TargetExecutionErrorCode.CONFIGURATION_ERROR)
        outcome = self._run_remote(
            remote_command=["robotctl", "target-executor", "evidence-v4"],
            stdin=request.model_dump_json(),
            timeout_s=request.timeout_s,
            max_stdout_bytes=2_000_000,
            max_stderr_bytes=64_000,
            cancel_event=cancel_event,
        )
        if outcome.error_code is not None or outcome.exit_code != 0:
            return failed(_ssh_failure_code(outcome))
        try:
            result = TargetEvidenceCollectionResultV4.model_validate_json(outcome.stdout)
        except ValueError:
            return failed(TargetExecutionErrorCode.PROTOCOL_ERROR)
        if (
            result.request_id != request.request_id
            or result.request_sha256 != request.canonical_sha256()
            or result.target_id != request.target_id
            or result.robot_id != request.evidence_request.robot_id
        ):
            return failed(TargetExecutionErrorCode.PROTOCOL_ERROR)
        return result.model_copy(update={"executor_kind": TargetExecutorKind.SSH})

    def stage_adapter_release(
        self,
        request: AdapterReleaseStageRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> AdapterReleaseStageExecutionResult:
        from rolo.targets.adapter_release_transfer import (
            AdapterReleaseStageExecutionResult,
        )

        def failed(error: TargetExecutionErrorCode) -> AdapterReleaseStageExecutionResult:
            return AdapterReleaseStageExecutionResult(
                request_id=request.request_id,
                request_sha256=request.canonical_sha256(),
                target_id=request.target_id,
                robot_id=request.robot_id,
                release_id=request.release_id,
                package_id=request.package_id,
                manifest_sha256=request.manifest_sha256,
                signing_key_id=request.signing_key_id,
                signing_public_key_sha256=request.signing_public_key_sha256,
                executor_kind=TargetExecutorKind.SSH,
                execution_status=TargetExecutionStatus.FAILED,
                error_code=error,
            )

        if self._credential_purpose != CredentialPurpose.SSH_BOOTSTRAP:
            return failed(TargetExecutionErrorCode.CONFIGURATION_ERROR)
        outcome = self._run_remote(
            remote_command=["robotctl", "target-executor", "adapter-release-stage"],
            stdin=request.model_dump_json(),
            timeout_s=300.0,
            max_stdout_bytes=64 * 1024,
            max_stderr_bytes=32 * 1024,
            cancel_event=cancel_event,
        )
        if outcome.error_code is not None or outcome.exit_code != 0:
            return failed(_ssh_failure_code(outcome))
        try:
            result = AdapterReleaseStageExecutionResult.model_validate_json(outcome.stdout)
        except ValueError:
            return failed(TargetExecutionErrorCode.PROTOCOL_ERROR)
        if (
            result.request_id != request.request_id
            or result.request_sha256 != request.canonical_sha256()
            or result.target_id != request.target_id
            or result.robot_id != request.robot_id
            or result.release_id != request.release_id
            or result.package_id != request.package_id
            or result.manifest_sha256 != request.manifest_sha256
            or result.signing_key_id != request.signing_key_id
            or result.signing_public_key_sha256
            != request.signing_public_key_sha256
        ):
            return failed(TargetExecutionErrorCode.PROTOCOL_ERROR)
        return result.model_copy(update={"executor_kind": TargetExecutorKind.SSH})

    def activate_adapter_release(
        self,
        request: AdapterReleaseActivationRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> AdapterReleaseActivationExecutionResult:
        from rolo.targets.adapter_release_activation import (
            AdapterReleaseActivationExecutionResult,
        )

        def failed(error: TargetExecutionErrorCode) -> AdapterReleaseActivationExecutionResult:
            return AdapterReleaseActivationExecutionResult(
                request_id=request.request_id,
                request_sha256=request.canonical_sha256(),
                operation=request.operation,
                target_id=request.target_id,
                robot_id=request.robot_id,
                release_id=request.release_id,
                transfer_manifest_sha256=request.transfer_manifest_sha256,
                executor_kind=TargetExecutorKind.SSH,
                execution_status=TargetExecutionStatus.FAILED,
                transport_error_code=error,
            )

        if self._credential_purpose != CredentialPurpose.SSH_BOOTSTRAP:
            return failed(TargetExecutionErrorCode.CONFIGURATION_ERROR)
        outcome = self._run_remote(
            remote_command=["robotctl", "target-executor", "adapter-release-activate"],
            stdin=request.model_dump_json(),
            timeout_s=300.0,
            max_stdout_bytes=256 * 1024,
            max_stderr_bytes=32 * 1024,
            cancel_event=cancel_event,
        )
        if outcome.error_code is not None or outcome.exit_code != 0:
            return failed(_ssh_failure_code(outcome))
        try:
            result = AdapterReleaseActivationExecutionResult.model_validate_json(
                outcome.stdout
            )
        except ValueError:
            return failed(TargetExecutionErrorCode.PROTOCOL_ERROR)
        if (
            result.request_id != request.request_id
            or result.request_sha256 != request.canonical_sha256()
            or result.operation != request.operation
            or result.target_id != request.target_id
            or result.robot_id != request.robot_id
            or result.release_id != request.release_id
            or result.transfer_manifest_sha256
            != request.transfer_manifest_sha256
        ):
            return failed(TargetExecutionErrorCode.PROTOCOL_ERROR)
        return result.model_copy(update={"executor_kind": TargetExecutorKind.SSH})

    def status_adapter_release(
        self,
        request: AdapterReleaseStatusRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> AdapterReleaseStatusExecutionResult:
        from rolo.targets.adapter_release_reconciliation import (
            AdapterReleaseStatusExecutionResult,
        )

        desired = request.desired

        def failed(error: TargetExecutionErrorCode) -> AdapterReleaseStatusExecutionResult:
            return AdapterReleaseStatusExecutionResult(
                request_id=request.request_id,
                request_sha256=request.canonical_sha256(),
                target_id=desired.target_id,
                robot_id=desired.robot_id,
                executor_kind=TargetExecutorKind.SSH,
                execution_status=TargetExecutionStatus.FAILED,
                error_code=error,
            )

        if self._credential_purpose not in {
            CredentialPurpose.SSH_BOOTSTRAP,
            CredentialPurpose.SSH_RUNTIME,
        }:
            return failed(TargetExecutionErrorCode.CONFIGURATION_ERROR)
        outcome = self._run_remote(
            remote_command=["robotctl", "target-executor", "adapter-release-status"],
            stdin=request.model_dump_json(),
            timeout_s=request.timeout_s,
            max_stdout_bytes=128 * 1024,
            max_stderr_bytes=32 * 1024,
            cancel_event=cancel_event,
        )
        if outcome.error_code is not None or outcome.exit_code != 0:
            return failed(_ssh_failure_code(outcome))
        try:
            result = AdapterReleaseStatusExecutionResult.model_validate_json(outcome.stdout)
        except ValueError:
            return failed(TargetExecutionErrorCode.PROTOCOL_ERROR)
        if (
            result.request_id != request.request_id
            or result.request_sha256 != request.canonical_sha256()
            or result.target_id != desired.target_id
            or result.robot_id != desired.robot_id
        ):
            return failed(TargetExecutionErrorCode.PROTOCOL_ERROR)
        return result.model_copy(update={"executor_kind": TargetExecutorKind.SSH})

    def detect_project_evidence(
        self,
        request: TargetProjectEvidenceRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> TargetProjectEvidenceExecutionResult:
        from rolo.targets.runtime_deployment import TargetProjectEvidenceExecutionResult

        workspace = request.workspace

        def failed(error: TargetExecutionErrorCode) -> TargetProjectEvidenceExecutionResult:
            return TargetProjectEvidenceExecutionResult(
                request_id=request.request_id,
                request_sha256=request.canonical_sha256(),
                target_id=workspace.target_id,
                robot_id=workspace.robot_id,
                workspace_id=workspace.workspace_id,
                executor_kind=TargetExecutorKind.SSH,
                execution_status=TargetExecutionStatus.FAILED,
                error_code=error,
            )

        if self._credential_purpose not in {
            CredentialPurpose.SSH_BOOTSTRAP,
            CredentialPurpose.SSH_RUNTIME,
        }:
            return failed(TargetExecutionErrorCode.CONFIGURATION_ERROR)
        outcome = self._run_remote(
            remote_command=["robotctl", "target-executor", "project-evidence"],
            stdin=request.model_dump_json(),
            timeout_s=request.timeout_s,
            max_stdout_bytes=2_000_000,
            max_stderr_bytes=64 * 1024,
            cancel_event=cancel_event,
        )
        if outcome.error_code is not None or outcome.exit_code != 0:
            return failed(_ssh_failure_code(outcome))
        try:
            result = TargetProjectEvidenceExecutionResult.model_validate_json(outcome.stdout)
        except ValueError:
            return failed(TargetExecutionErrorCode.PROTOCOL_ERROR)
        if (
            result.request_id != request.request_id
            or result.request_sha256 != request.canonical_sha256()
            or result.target_id != workspace.target_id
            or result.robot_id != workspace.robot_id
            or result.workspace_id != workspace.workspace_id
        ):
            return failed(TargetExecutionErrorCode.PROTOCOL_ERROR)
        return result.model_copy(update={"executor_kind": TargetExecutorKind.SSH})

    def discover_source(
        self,
        request: TargetSourceDiscoveryRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> TargetSourceDiscoveryExecutionResult:
        from rolo.targets.source_discovery import TargetSourceDiscoveryExecutionResult

        workspace = request.workspace

        def failed(error: TargetExecutionErrorCode) -> TargetSourceDiscoveryExecutionResult:
            return TargetSourceDiscoveryExecutionResult(
                request_id=request.request_id,
                request_sha256=request.canonical_sha256(),
                target_id=workspace.target_id,
                robot_id=workspace.robot_id,
                workspace_id=workspace.workspace_id,
                executor_kind=TargetExecutorKind.SSH,
                execution_status=TargetExecutionStatus.FAILED,
                error_code=error,
            )

        if self._credential_purpose not in {
            CredentialPurpose.SSH_BOOTSTRAP,
            CredentialPurpose.SSH_RUNTIME,
        }:
            return failed(TargetExecutionErrorCode.CONFIGURATION_ERROR)
        outcome = self._run_remote(
            remote_command=["robotctl", "target-executor", "source-discovery"],
            stdin=request.model_dump_json(),
            timeout_s=request.timeout_s,
            max_stdout_bytes=2_500_000,
            max_stderr_bytes=64 * 1024,
            cancel_event=cancel_event,
        )
        if outcome.error_code is not None or outcome.exit_code != 0:
            return failed(_ssh_failure_code(outcome))
        try:
            result = TargetSourceDiscoveryExecutionResult.model_validate_json(outcome.stdout)
        except ValueError:
            return failed(TargetExecutionErrorCode.PROTOCOL_ERROR)
        if (
            result.request_id != request.request_id
            or result.request_sha256 != request.canonical_sha256()
            or result.target_id != workspace.target_id
            or result.robot_id != workspace.robot_id
            or result.workspace_id != workspace.workspace_id
        ):
            return failed(TargetExecutionErrorCode.PROTOCOL_ERROR)
        return result.model_copy(update={"executor_kind": TargetExecutorKind.SSH})

    def describe_adapter_release(
        self,
        request: AdapterReleaseDescribeRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> AdapterReleaseDescribeExecutionResult:
        from rolo.targets.runtime_deployment import (
            AdapterReleaseDescribeExecutionResult,
        )

        describe = request.describe

        def failed(error: TargetExecutionErrorCode) -> AdapterReleaseDescribeExecutionResult:
            return AdapterReleaseDescribeExecutionResult(
                request_id=request.request_id,
                request_sha256=request.canonical_sha256(),
                target_id=describe.target_id,
                robot_id=describe.robot_id,
                release_id=describe.release_id,
                transfer_manifest_sha256=request.transfer_manifest_sha256,
                executor_kind=TargetExecutorKind.SSH,
                execution_status=TargetExecutionStatus.FAILED,
                error_code=error,
            )

        if self._credential_purpose != CredentialPurpose.SSH_BOOTSTRAP:
            return failed(TargetExecutionErrorCode.CONFIGURATION_ERROR)
        outcome = self._run_remote(
            remote_command=["robotctl", "target-executor", "adapter-release-describe"],
            stdin=request.model_dump_json(),
            timeout_s=describe.timeout_s + 30.0,
            max_stdout_bytes=512 * 1024,
            max_stderr_bytes=64 * 1024,
            cancel_event=cancel_event,
        )
        if outcome.error_code is not None or outcome.exit_code != 0:
            return failed(_ssh_failure_code(outcome))
        try:
            result = AdapterReleaseDescribeExecutionResult.model_validate_json(
                outcome.stdout
            )
        except ValueError:
            return failed(TargetExecutionErrorCode.PROTOCOL_ERROR)
        if (
            result.request_id != request.request_id
            or result.request_sha256 != request.canonical_sha256()
            or result.target_id != describe.target_id
            or result.robot_id != describe.robot_id
            or result.release_id != describe.release_id
            or result.transfer_manifest_sha256
            != request.transfer_manifest_sha256
        ):
            return failed(TargetExecutionErrorCode.PROTOCOL_ERROR)
        return result.model_copy(update={"executor_kind": TargetExecutorKind.SSH})

    def transfer_package_chunk(
        self,
        request: TargetPackageTransferRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> TargetPackageTransferResult:
        outcome = self._run_remote(
            remote_command=["robotctl", "target-executor", "package-transfer"],
            stdin=request.model_dump_json(),
            timeout_s=60.0,
            max_stdout_bytes=64 * 1024,
            max_stderr_bytes=16 * 1024,
            cancel_event=cancel_event,
        )
        if outcome.error_code is not None or outcome.exit_code != 0:
            return TargetPackageTransferResult(
                request_id=request.request_id,
                request_sha256=request.canonical_sha256(),
                executor_kind=TargetExecutorKind.SSH,
                status=TargetExecutionStatus.FAILED,
                error_code=_ssh_failure_code(outcome),
                received_size_bytes=0,
                file_size_bytes=request.file_size_bytes,
                complete=False,
            )
        try:
            result = TargetPackageTransferResult.model_validate_json(outcome.stdout)
        except ValueError:
            return TargetPackageTransferResult(
                request_id=request.request_id,
                request_sha256=request.canonical_sha256(),
                executor_kind=TargetExecutorKind.SSH,
                status=TargetExecutionStatus.FAILED,
                error_code=TargetExecutionErrorCode.PROTOCOL_ERROR,
                received_size_bytes=0,
                file_size_bytes=request.file_size_bytes,
                complete=False,
            )
        if (
            result.request_id != request.request_id
            or result.request_sha256 != request.canonical_sha256()
            or result.file_size_bytes != request.file_size_bytes
        ):
            return TargetPackageTransferResult(
                request_id=request.request_id,
                request_sha256=request.canonical_sha256(),
                executor_kind=TargetExecutorKind.SSH,
                status=TargetExecutionStatus.FAILED,
                error_code=TargetExecutionErrorCode.PROTOCOL_ERROR,
                received_size_bytes=0,
                file_size_bytes=request.file_size_bytes,
                complete=False,
            )
        return result.model_copy(update={"executor_kind": TargetExecutorKind.SSH})


def platform_snapshot() -> dict[str, object]:
    """Direct helper used only by tests and diagnostics, matching PLATFORM output fields."""
    return {
        "machine": platform.machine(),
        "os": platform.system().casefold(),
        "os_release": platform.release(),
        "python": platform.python_version(),
        "python_executable": sys.executable,
        "uid": os.getuid() if hasattr(os, "getuid") else None,
    }
