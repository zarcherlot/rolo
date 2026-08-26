from __future__ import annotations

import hashlib
import os
import threading
from base64 import b64encode
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from rolo.core.persistence import interprocess_lock
from rolo.targets.executor import (
    TargetExecutionErrorCode,
    TargetExecutionStatus,
    TargetExecutor,
    TargetExecutorKind,
    TargetPackageTransferOperation,
    TargetPackageTransferRequest,
    TargetPackageTransferResult,
)
from rolo.targets.package_installer import (
    PACKAGE_MANIFEST_NAME,
    PACKAGE_SIGNATURE_NAME,
    TargetPackageSignatureVerifier,
    load_target_package,
    verify_target_package,
)

_PREINSTALL_TRANSFER_SCRIPT = r"""import base64,fcntl,hashlib,json,os,re,sys
EXPECTED={'schema_version','request_id','operation','package_id','manifest_sha256','path','file_sha256','file_size_bytes','offset_bytes','chunk_size_bytes','chunk_sha256','chunk_base64'}
IDENTIFIER=re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$')
DIGEST=re.compile(r'^[0-9a-f]{64}$')
def canonical(value):
    payload=json.dumps(
        value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()
def emit(request,received,complete,error=None):
    result={
        'schema_version':'rolo-target-package-transfer-result/v1',
        'request_id':request['request_id'],
        'request_sha256':canonical(request),
        'executor_kind':'LOCAL',
        'status':'FAILED' if error else 'SUCCEEDED',
        'error_code':error,
        'received_size_bytes':received,
        'file_size_bytes':request['file_size_bytes'],
        'complete':complete,
    }
    print(json.dumps(result,sort_keys=True,separators=(',',':')))
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
    if os.path.islink(current):
        raise ValueError('symlink')
    relative=os.path.relpath(path,root)
    if relative == '..' or relative.startswith('../'):
        raise ValueError('escape')
    for part in relative.split(os.sep):
        current=os.path.join(current,part)
        if os.path.islink(current):
            raise ValueError('symlink')
raw=sys.stdin.buffer.read(800001)
if len(raw)>800000:
    raise SystemExit(2)
try:
    request=json.loads(raw.decode('utf-8'))
    if not isinstance(request,dict) or set(request)!=EXPECTED:
        raise ValueError('shape')
    if request['schema_version']!='rolo-target-package-transfer-request/v1':
        raise ValueError('schema')
    if not IDENTIFIER.fullmatch(request['request_id']):
        raise ValueError('request id')
    if not IDENTIFIER.fullmatch(request['package_id']):
        raise ValueError('package id')
    if not DIGEST.fullmatch(request['manifest_sha256']):
        raise ValueError('manifest digest')
    if not DIGEST.fullmatch(request['file_sha256']):
        raise ValueError('file digest')
    if request['operation'] not in ('QUERY','WRITE'):
        raise ValueError('operation')
    path=request['path']
    if (not isinstance(path,str) or not path or len(path)>4096
            or '\\' in path or ':' in path
            or any(character in path for character in ('\x00','\r','\n'))):
        raise ValueError('path')
    parts=path.split('/')
    if any(not part or part in ('.','..') for part in parts):
        raise ValueError('path')
    size=request['file_size_bytes']
    offset=request['offset_bytes']
    chunk_size=request['chunk_size_bytes']
    if type(size) is not int or not 0<=size<=1000000000:
        raise ValueError('size')
    if type(offset) is not int or not 0<=offset<=size:
        raise ValueError('offset')
    if type(chunk_size) is not int or not 0<=chunk_size<=524288:
        raise ValueError('chunk size')
    if request['operation']=='QUERY':
        if (offset or chunk_size or request['chunk_sha256'] is not None
                or request['chunk_base64'] is not None):
            raise ValueError('query payload')
        chunk=None
    else:
        if (not isinstance(request['chunk_base64'],str)
                or not DIGEST.fullmatch(request['chunk_sha256'] or '')):
            raise ValueError('chunk')
        chunk=base64.b64decode(request['chunk_base64'],validate=True)
        if len(chunk)!=chunk_size or hashlib.sha256(chunk).hexdigest()!=request['chunk_sha256']:
            raise ValueError('chunk integrity')
        if offset+chunk_size>size or (chunk_size==0 and size!=0):
            raise ValueError('chunk bounds')
except (KeyError,TypeError,ValueError,UnicodeError):
    raise SystemExit(2)
root=os.path.realpath(os.path.expanduser('~/.local/share/rolo/bootstrap/incoming'))
package_root=os.path.join(root,'packages',request['package_id'],request['manifest_sha256'])
final=os.path.join(package_root,*parts)
state_root=os.path.join(root,'state',request['package_id'],request['manifest_sha256'])
state_digest=hashlib.sha256(path.encode('utf-8')).hexdigest()
state=os.path.join(state_root,state_digest[:32]+'.part')
legacy_state=os.path.join(state_root,state_digest+'.part')
if os.path.isfile(legacy_state) and not os.path.exists(state):
    state=legacy_state
lock=state+'.lock'
try:
    reject_symlinks(root,final)
    reject_symlinks(root,state)
    os.makedirs(state_root,mode=0o700,exist_ok=True)
    with open(lock,'a+b') as lock_stream:
        fcntl.flock(lock_stream,fcntl.LOCK_EX)
        if os.path.isfile(final):
            if os.path.getsize(final)==size and digest_file(final)==request['file_sha256']:
                emit(request,size,True)
            else:
                emit(request,0,False,'INTEGRITY_ERROR')
            raise SystemExit(0)
        received=os.path.getsize(state) if os.path.isfile(state) else 0
        if request['operation']=='QUERY':
            if received==size and os.path.isfile(state):
                if digest_file(state)!=request['file_sha256']:
                    os.unlink(state)
                    emit(request,0,False,'INTEGRITY_ERROR')
                else:
                    os.makedirs(os.path.dirname(final),mode=0o700,exist_ok=True)
                    reject_symlinks(package_root,final)
                    os.replace(state,final)
                    emit(request,received,True)
            else:
                emit(request,received,False)
            raise SystemExit(0)
        if offset!=received:
            emit(request,received,False,'OFFSET_MISMATCH')
            raise SystemExit(0)
        with open(state,'ab') as stream:
            stream.write(chunk)
            stream.flush()
            os.fsync(stream.fileno())
        received+=len(chunk)
        if received==size:
            if digest_file(state)!=request['file_sha256']:
                os.unlink(state)
                emit(request,0,False,'INTEGRITY_ERROR')
            else:
                os.makedirs(os.path.dirname(final),mode=0o700,exist_ok=True)
                reject_symlinks(package_root,final)
                os.replace(state,final)
                emit(request,received,True)
        else:
            emit(request,received,False)
except SystemExit:
    raise
except (OSError,ValueError):
    emit(request,0,False,'IO_ERROR')
"""


class TargetPackageUploadResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-package-upload-result/v1"] = (
        "rolo-target-package-upload-result/v1"
    )
    package_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
    package_version: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$")
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    package_ref: str = Field(
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}:[0-9a-f]{64}$"
    )
    files_total: int = Field(ge=1, le=4098)
    bytes_total: int = Field(ge=0)
    bytes_uploaded: int = Field(ge=0)
    bytes_resumed: int = Field(ge=0)


class TargetPackageUploadError(RuntimeError):
    def __init__(self, error_code: TargetExecutionErrorCode, path: str) -> None:
        self.error_code = error_code
        self.path = path
        super().__init__(f"target package upload failed for {path}: {error_code.value}")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


class TargetPackageChunkStore:
    """Crash-recoverable target-side chunk storage under one fixed incoming root."""

    def __init__(self, root: Path) -> None:
        candidate = root.expanduser()
        if candidate.is_symlink():
            raise ValueError("target package incoming root cannot be a symlink")
        self.root = candidate.resolve()

    def _paths(self, request: TargetPackageTransferRequest) -> tuple[Path, Path, Path]:
        package_root = (
            self.root / "packages" / request.package_id / request.manifest_sha256
        )
        relative = PurePosixPath(request.path)
        final = package_root.joinpath(*relative.parts)
        state_root = (
            self.root / "state" / request.package_id / request.manifest_sha256
        )
        state_digest = hashlib.sha256(request.path.encode("utf-8")).hexdigest()
        state = state_root / f"{state_digest[:32]}.part"
        legacy_state = state_root / f"{state_digest}.part"
        if legacy_state.is_file() and not state.exists():
            state = legacy_state
        return package_root, final, state

    @staticmethod
    def _reject_symlinks(root: Path, path: Path) -> None:
        current = root
        if current.is_symlink():
            raise ValueError("target package transfer path contains a symlink")
        for part in path.relative_to(root).parts:
            current = current / part
            if current.is_symlink():
                raise ValueError("target package transfer path contains a symlink")

    @staticmethod
    def _result(
        request: TargetPackageTransferRequest,
        *,
        executor_kind: TargetExecutorKind,
        received: int,
        complete: bool,
        error_code: TargetExecutionErrorCode | None = None,
    ) -> TargetPackageTransferResult:
        return TargetPackageTransferResult(
            request_id=request.request_id,
            request_sha256=request.canonical_sha256(),
            executor_kind=executor_kind,
            status=(
                TargetExecutionStatus.FAILED
                if error_code is not None
                else TargetExecutionStatus.SUCCEEDED
            ),
            error_code=error_code,
            received_size_bytes=received,
            file_size_bytes=request.file_size_bytes,
            complete=complete,
        )

    def apply(
        self,
        request: TargetPackageTransferRequest,
        *,
        executor_kind: TargetExecutorKind = TargetExecutorKind.LOCAL,
    ) -> TargetPackageTransferResult:
        package_root, final, state = self._paths(request)
        lock_target = state.with_suffix(".lock-target")
        try:
            self._reject_symlinks(self.root, final)
            self._reject_symlinks(self.root, state)
            with interprocess_lock(lock_target):
                if final.is_file():
                    if (
                        final.stat().st_size == request.file_size_bytes
                        and _sha256_file(final) == request.file_sha256
                    ):
                        return self._result(
                            request,
                            executor_kind=executor_kind,
                            received=request.file_size_bytes,
                            complete=True,
                        )
                    return self._result(
                        request,
                        executor_kind=executor_kind,
                        received=0,
                        complete=False,
                        error_code=TargetExecutionErrorCode.INTEGRITY_ERROR,
                    )
                received = state.stat().st_size if state.is_file() else 0
                if request.operation == TargetPackageTransferOperation.QUERY:
                    if received == request.file_size_bytes and state.is_file():
                        if _sha256_file(state) != request.file_sha256:
                            state.unlink(missing_ok=True)
                            return self._result(
                                request,
                                executor_kind=executor_kind,
                                received=0,
                                complete=False,
                                error_code=TargetExecutionErrorCode.INTEGRITY_ERROR,
                            )
                        final.parent.mkdir(parents=True, exist_ok=True)
                        self._reject_symlinks(package_root, final)
                        os.replace(state, final)
                        return self._result(
                            request,
                            executor_kind=executor_kind,
                            received=received,
                            complete=True,
                        )
                    return self._result(
                        request,
                        executor_kind=executor_kind,
                        received=received,
                        complete=False,
                    )
                if request.offset_bytes != received:
                    return self._result(
                        request,
                        executor_kind=executor_kind,
                        received=received,
                        complete=False,
                        error_code=TargetExecutionErrorCode.OFFSET_MISMATCH,
                    )
                state.parent.mkdir(parents=True, exist_ok=True)
                chunk = request.chunk_bytes()
                with state.open("ab") as stream:
                    stream.write(chunk)
                    stream.flush()
                    os.fsync(stream.fileno())
                received += len(chunk)
                if received == request.file_size_bytes:
                    if _sha256_file(state) != request.file_sha256:
                        state.unlink(missing_ok=True)
                        return self._result(
                            request,
                            executor_kind=executor_kind,
                            received=0,
                            complete=False,
                            error_code=TargetExecutionErrorCode.INTEGRITY_ERROR,
                        )
                    final.parent.mkdir(parents=True, exist_ok=True)
                    self._reject_symlinks(package_root, final)
                    os.replace(state, final)
                    return self._result(
                        request,
                        executor_kind=executor_kind,
                        received=received,
                        complete=True,
                    )
                return self._result(
                    request,
                    executor_kind=executor_kind,
                    received=received,
                    complete=False,
                )
        except (OSError, TimeoutError, ValueError):
            return self._result(
                request,
                executor_kind=executor_kind,
                received=0,
                complete=False,
                error_code=TargetExecutionErrorCode.IO_ERROR,
            )


class TargetPackageUploader:
    def __init__(
        self,
        executor: TargetExecutor,
        verifier: TargetPackageSignatureVerifier,
        *,
        chunk_size_bytes: int = 256 * 1024,
    ) -> None:
        if not 1 <= chunk_size_bytes <= 512 * 1024:
            raise ValueError("target package upload chunk size is out of bounds")
        self._executor = executor
        self._verifier = verifier
        self._chunk_size = chunk_size_bytes

    @staticmethod
    def _request_id(prefix: str, file_index: int, suffix: str) -> str:
        return f"{prefix}-{file_index:04d}-{suffix}"

    def upload(
        self,
        package_root: Path,
        *,
        request_prefix: str,
        cancel_event: threading.Event | None = None,
    ) -> TargetPackageUploadResult:
        root, manifest, signature = load_target_package(package_root)
        verify_target_package(root, manifest, signature, self._verifier)
        paths = [PACKAGE_MANIFEST_NAME, PACKAGE_SIGNATURE_NAME]
        paths.extend(item.path for item in manifest.files)
        bytes_total = 0
        bytes_uploaded = 0
        bytes_resumed = 0
        for index, relative in enumerate(paths):
            source = root.joinpath(*PurePosixPath(relative).parts)
            size = source.stat().st_size
            digest = _sha256_file(source)
            bytes_total += size
            query = TargetPackageTransferRequest(
                request_id=self._request_id(request_prefix, index, "query"),
                operation=TargetPackageTransferOperation.QUERY,
                package_id=manifest.package_id,
                manifest_sha256=manifest.canonical_sha256(),
                path=relative,
                file_sha256=digest,
                file_size_bytes=size,
            )
            status = self._executor.transfer_package_chunk(
                query,
                cancel_event=cancel_event,
            )
            if status.status != TargetExecutionStatus.SUCCEEDED:
                raise TargetPackageUploadError(
                    status.error_code or TargetExecutionErrorCode.PROTOCOL_ERROR,
                    relative,
                )
            if status.complete:
                bytes_resumed += size
                continue
            offset = status.received_size_bytes
            bytes_resumed += offset
            with source.open("rb") as stream:
                stream.seek(offset)
                while offset < size or (size == 0 and offset == 0):
                    chunk = stream.read(self._chunk_size)
                    write = TargetPackageTransferRequest(
                        request_id=self._request_id(
                            request_prefix,
                            index,
                            f"{offset:016x}",
                        ),
                        operation=TargetPackageTransferOperation.WRITE,
                        package_id=manifest.package_id,
                        manifest_sha256=manifest.canonical_sha256(),
                        path=relative,
                        file_sha256=digest,
                        file_size_bytes=size,
                        offset_bytes=offset,
                        chunk_size_bytes=len(chunk),
                        chunk_sha256=hashlib.sha256(chunk).hexdigest(),
                        chunk_base64=b64encode(chunk).decode("ascii"),
                    )
                    result = self._executor.transfer_package_chunk(
                        write,
                        cancel_event=cancel_event,
                    )
                    if (
                        result.status == TargetExecutionStatus.FAILED
                        and result.error_code == TargetExecutionErrorCode.OFFSET_MISMATCH
                    ):
                        offset = result.received_size_bytes
                        stream.seek(offset)
                        continue
                    if result.status != TargetExecutionStatus.SUCCEEDED:
                        raise TargetPackageUploadError(
                            result.error_code or TargetExecutionErrorCode.PROTOCOL_ERROR,
                            relative,
                        )
                    expected = offset + len(chunk)
                    if result.received_size_bytes != expected:
                        raise TargetPackageUploadError(
                            TargetExecutionErrorCode.PROTOCOL_ERROR,
                            relative,
                        )
                    bytes_uploaded += len(chunk)
                    offset = expected
                    if size == 0:
                        break
            if not result.complete:
                raise TargetPackageUploadError(
                    TargetExecutionErrorCode.PROTOCOL_ERROR,
                    relative,
                )
        return TargetPackageUploadResult(
            package_id=manifest.package_id,
            package_version=manifest.package_version,
            manifest_sha256=manifest.canonical_sha256(),
            package_ref=f"{manifest.package_id}:{manifest.canonical_sha256()}",
            files_total=len(paths),
            bytes_total=bytes_total,
            bytes_uploaded=bytes_uploaded,
            bytes_resumed=bytes_resumed,
        )
