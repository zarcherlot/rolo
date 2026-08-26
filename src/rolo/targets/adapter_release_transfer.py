from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
from base64 import b64decode, b64encode
from collections.abc import Mapping
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Literal, Protocol
from uuid import uuid4

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from rolo.core.persistence import interprocess_lock
from rolo.targets.deployment_authorization import (
    DeploymentAuthorizationProof,
    validate_deployment_request_authorization_binding,
)
from rolo.targets.executor import (
    TargetExecutionErrorCode,
    TargetExecutionStatus,
    TargetExecutor,
    TargetExecutorKind,
    TargetPackageTransferOperation,
    TargetPackageTransferRequest,
)
from rolo.targets.package_signing import (
    _load_public_key,
    _read_bounded_key,
    ed25519_public_key_sha256,
)
from rolo.targets.runtime_deployment import (
    LocatedRuntimeContext,
    verify_frozen_adapter_release,
)

ADAPTER_TRANSFER_MANIFEST = "adapter-release-transfer.json"
ADAPTER_TRANSFER_SIGNATURE = "adapter-release-transfer.sig.json"
ADAPTER_RUNTIME_CONTEXT = "located-runtime-context.json"

_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"
_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_APPROVAL_PATTERN = r"^approval-[0-9a-f]{32}$"
_MAX_FILES = 4098
_MAX_FILE_BYTES = 512 * 1024 * 1024
_MAX_TOTAL_BYTES = 1024 * 1024 * 1024
_MAX_MANIFEST_BYTES = 4 * 1024 * 1024
_MAX_SIGNATURE_BYTES = 64 * 1024
_MAX_CONTEXT_BYTES = 2 * 1024 * 1024


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _relative_path(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or "." in path.parts or ".." in path.parts:
        raise ValueError("adapter release transfer path must be normalized and relative")
    if any(character in value for character in ("\x00", "\r", "\n", "\\", ":")):
        raise ValueError("adapter release transfer path contains forbidden characters")
    return str(path)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_text_bounded(path: Path, *, limit: int, label: str) -> str:
    if path.stat().st_size > limit:
        raise ValueError(f"{label} exceeds its size limit")
    return path.read_text(encoding="utf-8")


def _safe_file(root: Path, relative: str) -> Path:
    normalized = _relative_path(relative)
    candidate = root.joinpath(*PurePosixPath(normalized).parts)
    current = root
    for part in PurePosixPath(normalized).parts:
        current = current / part
        try:
            metadata = current.lstat()
        except OSError as exc:
            raise ValueError("adapter release transfer file is unavailable") from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise ValueError("adapter release transfer path contains a symbolic link")
    if not candidate.is_file():
        raise ValueError("adapter release transfer path is not a regular file")
    try:
        candidate.resolve(strict=True).relative_to(root.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise ValueError("adapter release transfer file escapes its root") from exc
    return candidate


def _tree_files(root: Path) -> set[str]:
    files: set[str] = set()
    for candidate in root.rglob("*"):
        metadata = candidate.lstat()
        if stat.S_ISLNK(metadata.st_mode):
            raise ValueError("adapter release transfer tree contains a symbolic link")
        if stat.S_ISREG(metadata.st_mode):
            files.add(candidate.relative_to(root).as_posix())
        elif not stat.S_ISDIR(metadata.st_mode):
            raise ValueError("adapter release transfer tree contains a non-regular entry")
    return files


class AdapterReleaseTransferFileRole(str, Enum):
    RELEASE = "RELEASE"
    RUNTIME_CONTEXT = "RUNTIME_CONTEXT"


class AdapterReleaseTransferFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1, max_length=4096)
    sha256: str = Field(pattern=_SHA256_PATTERN)
    size_bytes: int = Field(ge=0, le=_MAX_FILE_BYTES)
    executable: bool = False
    role: AdapterReleaseTransferFileRole

    _path = field_validator("path")(_relative_path)


class AdapterReleaseTransferManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-adapter-release-transfer/v1"] = (
        "rolo-adapter-release-transfer/v1"
    )
    package_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    target_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    robot_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    release_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    release_manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    bundle_manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    runtime_context_sha256: str = Field(pattern=_SHA256_PATTERN)
    files: list[AdapterReleaseTransferFile] = Field(
        min_length=2,
        max_length=_MAX_FILES,
    )
    total_size_bytes: int = Field(ge=0, le=_MAX_TOTAL_BYTES)

    @model_validator(mode="after")
    def require_canonical_files(self) -> AdapterReleaseTransferManifest:
        paths = [item.path for item in self.files]
        if paths != sorted(set(paths)):
            raise ValueError("adapter release transfer files must be unique and sorted")
        if sum(item.size_bytes for item in self.files) != self.total_size_bytes:
            raise ValueError("adapter release transfer total size mismatch")
        contexts = [
            item
            for item in self.files
            if item.role == AdapterReleaseTransferFileRole.RUNTIME_CONTEXT
        ]
        if len(contexts) != 1 or contexts[0].path != ADAPTER_RUNTIME_CONTEXT:
            raise ValueError("adapter release transfer requires one runtime context")
        if not any(item.path == "release/manifest.json" for item in self.files):
            raise ValueError("adapter release transfer lacks its release manifest")
        return self

    def canonical_json(self) -> str:
        return _canonical_json(self.model_dump(mode="json"))

    def canonical_sha256(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


class AdapterReleaseTransferSignature(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-adapter-release-transfer-signature/v1"] = (
        "rolo-adapter-release-transfer-signature/v1"
    )
    algorithm: Literal["Ed25519"] = "Ed25519"
    key_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    signature_base64: str = Field(pattern=r"^[A-Za-z0-9+/]{86}==$")

    @field_validator("signature_base64")
    @classmethod
    def validate_signature_bytes(cls, value: str) -> str:
        try:
            payload = b64decode(value, validate=True)
        except ValueError as exc:
            raise ValueError("adapter release transfer signature is invalid base64") from exc
        if len(payload) != 64:
            raise ValueError("adapter release transfer signature must be 64 bytes")
        return value


class AdapterReleaseSignatureVerifier(Protocol):
    def public_key_sha256(self, key_id: str) -> str: ...

    def verify(
        self,
        manifest: AdapterReleaseTransferManifest,
        signature: AdapterReleaseTransferSignature,
    ) -> None: ...

    def verify_payload(self, key_id: str, payload: bytes, signature: bytes) -> None: ...


class Ed25519AdapterReleaseVerifier:
    def __init__(self, public_keys: Mapping[str, bytes | Path]) -> None:
        if not public_keys:
            raise ValueError("at least one adapter release public key is required")
        self._keys: dict[str, Ed25519PublicKey] = {}
        self._fingerprints: dict[str, str] = {}
        for key_id, value in public_keys.items():
            payload = _read_bounded_key(value, private=False) if isinstance(value, Path) else value
            self._keys[key_id] = _load_public_key(payload, key_id=key_id)
            self._fingerprints[key_id] = ed25519_public_key_sha256(payload)

    def public_key_sha256(self, key_id: str) -> str:
        try:
            return self._fingerprints[key_id]
        except KeyError as exc:
            raise ValueError("adapter release signing key is not pinned") from exc

    def verify(
        self,
        manifest: AdapterReleaseTransferManifest,
        signature: AdapterReleaseTransferSignature,
    ) -> None:
        if signature.manifest_sha256 != manifest.canonical_sha256():
            raise ValueError("adapter release signature manifest digest mismatch")
        self.verify_payload(
            signature.key_id,
            manifest.canonical_json().encode("utf-8"),
            b64decode(signature.signature_base64, validate=True),
        )

    def verify_payload(self, key_id: str, payload: bytes, signature: bytes) -> None:
        try:
            key = self._keys[key_id]
        except KeyError as exc:
            raise ValueError("adapter release signing key is not pinned") from exc
        try:
            key.verify(signature, payload)
        except (InvalidSignature, ValueError) as exc:
            raise ValueError("adapter release Ed25519 signature verification failed") from exc


def sign_adapter_release_transfer(
    manifest: AdapterReleaseTransferManifest,
    *,
    key_id: str,
    private_key_path: Path,
) -> AdapterReleaseTransferSignature:
    try:
        key = serialization.load_pem_private_key(
            _read_bounded_key(private_key_path, private=True),
            password=None,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("adapter release private signing key is invalid") from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("adapter release private signing key must be Ed25519")
    signature = key.sign(manifest.canonical_json().encode("utf-8"))
    return AdapterReleaseTransferSignature(
        key_id=key_id,
        manifest_sha256=manifest.canonical_sha256(),
        signature_base64=b64encode(signature).decode("ascii"),
    )


def _manifest_file(
    path: Path,
    *,
    root: Path,
    role: AdapterReleaseTransferFileRole,
) -> AdapterReleaseTransferFile:
    metadata = path.stat()
    if metadata.st_size > _MAX_FILE_BYTES:
        raise ValueError("adapter release transfer file exceeds its size limit")
    return AdapterReleaseTransferFile(
        path=path.relative_to(root).as_posix(),
        sha256=_sha256_file(path),
        size_bytes=metadata.st_size,
        executable=bool(metadata.st_mode & stat.S_IXUSR),
        role=role,
    )


def prepare_adapter_release_transfer(
    release_root: Path,
    *,
    output_root: Path,
    target_id: str,
    context: LocatedRuntimeContext,
    key_id: str,
    private_key_path: Path,
) -> tuple[Path, AdapterReleaseTransferManifest, AdapterReleaseTransferSignature]:
    """Freeze only declared release files plus one located context into a signed transfer."""

    verified_root, release, _ = verify_frozen_adapter_release(release_root)
    if context.target_id != target_id or context.robot_id != release.robot_id:
        raise ValueError("adapter release transfer context identity mismatch")
    output = output_root.expanduser().absolute()
    if output.is_symlink() or output.exists():
        raise ValueError("adapter release transfer output must be an absent real path")
    resolved_output = output.resolve(strict=False)
    if resolved_output.is_relative_to(verified_root) or verified_root.is_relative_to(
        resolved_output
    ):
        raise ValueError("adapter release transfer output cannot contain or enter source")
    if private_key_path.expanduser().resolve().is_relative_to(verified_root):
        raise ValueError("adapter release signing key cannot be inside the release")
    staging = output.with_name(f".{output.name}.staging-{uuid4().hex[:12]}")
    if staging.exists() or staging.is_symlink():
        raise ValueError("adapter release transfer staging path already exists")
    try:
        shutil.copytree(verified_root, staging / "release", symlinks=True)
        (staging / ADAPTER_RUNTIME_CONTEXT).write_text(
            context.model_dump_json(indent=2, by_alias=True) + "\n",
            encoding="utf-8",
        )
        files = [
            _manifest_file(
                staging / relative,
                root=staging,
                role=(
                    AdapterReleaseTransferFileRole.RUNTIME_CONTEXT
                    if relative == ADAPTER_RUNTIME_CONTEXT
                    else AdapterReleaseTransferFileRole.RELEASE
                ),
            )
            for relative in sorted(
                {ADAPTER_RUNTIME_CONTEXT}
                | {f"release/{item}" for item in _tree_files(staging / "release")}
            )
        ]
        total = sum(item.size_bytes for item in files)
        if total > _MAX_TOTAL_BYTES:
            raise ValueError("adapter release transfer exceeds its total size limit")
        # Keep the fixed incoming path below legacy Windows MAX_PATH during
        # controller-side conformance while retaining a collision-resistant ID.
        package_id = f"ar-{hashlib.sha256(target_id.encode()).hexdigest()[:16]}"
        manifest = AdapterReleaseTransferManifest(
            package_id=package_id,
            target_id=target_id,
            robot_id=release.robot_id,
            release_id=release.release_id,
            release_manifest_sha256=_sha256_file(verified_root / "manifest.json"),
            bundle_manifest_sha256=release.bundle_manifest_sha256,
            runtime_context_sha256=context.canonical_sha256(),
            files=files,
            total_size_bytes=total,
        )
        signature = sign_adapter_release_transfer(
            manifest,
            key_id=key_id,
            private_key_path=private_key_path,
        )
        (staging / ADAPTER_TRANSFER_MANIFEST).write_text(
            manifest.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )
        (staging / ADAPTER_TRANSFER_SIGNATURE).write_text(
            signature.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging, output)
        return output, manifest, signature
    except Exception:
        if staging.is_dir():
            shutil.rmtree(staging)
        raise


def load_verified_adapter_release_transfer(
    root: Path,
    verifier: AdapterReleaseSignatureVerifier,
) -> tuple[
    Path,
    AdapterReleaseTransferManifest,
    AdapterReleaseTransferSignature,
    LocatedRuntimeContext,
]:
    candidate = root.expanduser().absolute()
    if candidate.is_symlink() or not candidate.is_dir():
        raise ValueError("adapter release transfer root is unavailable")
    resolved = candidate.resolve(strict=True)
    manifest_path = _safe_file(resolved, ADAPTER_TRANSFER_MANIFEST)
    signature_path = _safe_file(resolved, ADAPTER_TRANSFER_SIGNATURE)
    manifest = AdapterReleaseTransferManifest.model_validate_json(
        _read_text_bounded(
            manifest_path,
            limit=_MAX_MANIFEST_BYTES,
            label="adapter release transfer manifest",
        )
    )
    signature = AdapterReleaseTransferSignature.model_validate_json(
        _read_text_bounded(
            signature_path,
            limit=_MAX_SIGNATURE_BYTES,
            label="adapter release transfer signature",
        )
    )
    verifier.verify(manifest, signature)
    expected = {ADAPTER_TRANSFER_MANIFEST, ADAPTER_TRANSFER_SIGNATURE}
    expected.update(item.path for item in manifest.files)
    if _tree_files(resolved) != expected:
        raise ValueError("adapter release transfer file set differs from its manifest")
    for item in manifest.files:
        path = _safe_file(resolved, item.path)
        if path.stat().st_size != item.size_bytes or _sha256_file(path) != item.sha256:
            raise ValueError("adapter release transfer file digest or size mismatch")
    context = LocatedRuntimeContext.model_validate_json(
        _read_text_bounded(
            _safe_file(resolved, ADAPTER_RUNTIME_CONTEXT),
            limit=_MAX_CONTEXT_BYTES,
            label="located runtime context",
        )
    )
    if (
        context.target_id != manifest.target_id
        or context.robot_id != manifest.robot_id
        or context.canonical_sha256() != manifest.runtime_context_sha256
    ):
        raise ValueError("adapter release transfer runtime context mismatch")
    verify_frozen_adapter_release(
        resolved / "release",
        expected_manifest_sha256=manifest.release_manifest_sha256,
    )
    return resolved, manifest, signature, context


class AdapterReleaseUploadResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-adapter-release-upload-result/v1"] = (
        "rolo-adapter-release-upload-result/v1"
    )
    package_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    release_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    files_total: int = Field(ge=3, le=_MAX_FILES + 2)
    bytes_total: int = Field(ge=0, le=_MAX_TOTAL_BYTES + 1_000_000)
    bytes_uploaded: int = Field(ge=0)
    bytes_resumed: int = Field(ge=0)


class AdapterReleaseUploader:
    def __init__(
        self,
        executor: TargetExecutor,
        verifier: AdapterReleaseSignatureVerifier,
        *,
        chunk_size_bytes: int = 256 * 1024,
    ) -> None:
        if not 1 <= chunk_size_bytes <= 512 * 1024:
            raise ValueError("adapter release transfer chunk size is out of bounds")
        self._executor = executor
        self._verifier = verifier
        self._chunk_size = chunk_size_bytes

    def upload(self, root: Path, *, request_prefix: str) -> AdapterReleaseUploadResult:
        resolved, manifest, _, _ = load_verified_adapter_release_transfer(
            root,
            self._verifier,
        )
        paths = [ADAPTER_TRANSFER_MANIFEST, ADAPTER_TRANSFER_SIGNATURE]
        paths.extend(item.path for item in manifest.files)
        uploaded = 0
        resumed = 0
        total = 0
        manifest_sha256 = manifest.canonical_sha256()
        for index, relative in enumerate(paths):
            source = _safe_file(resolved, relative)
            size = source.stat().st_size
            digest = _sha256_file(source)
            total += size
            query = TargetPackageTransferRequest(
                request_id=f"{request_prefix}-{index:04d}-query",
                operation=TargetPackageTransferOperation.QUERY,
                package_id=manifest.package_id,
                manifest_sha256=manifest_sha256,
                path=relative,
                file_sha256=digest,
                file_size_bytes=size,
            )
            result = self._executor.transfer_package_chunk(query)
            if result.status != TargetExecutionStatus.SUCCEEDED:
                raise RuntimeError(
                    "adapter release upload query failed: "
                    f"{result.error_code or TargetExecutionErrorCode.PROTOCOL_ERROR}"
                )
            if result.complete:
                resumed += size
                continue
            offset = result.received_size_bytes
            resumed += offset
            with source.open("rb") as stream:
                stream.seek(offset)
                while offset < size or (size == 0 and offset == 0):
                    chunk = stream.read(self._chunk_size)
                    write = TargetPackageTransferRequest(
                        request_id=f"{request_prefix}-{index:04d}-{offset:016x}",
                        operation=TargetPackageTransferOperation.WRITE,
                        package_id=manifest.package_id,
                        manifest_sha256=manifest_sha256,
                        path=relative,
                        file_sha256=digest,
                        file_size_bytes=size,
                        offset_bytes=offset,
                        chunk_size_bytes=len(chunk),
                        chunk_sha256=hashlib.sha256(chunk).hexdigest(),
                        chunk_base64=b64encode(chunk).decode("ascii"),
                    )
                    result = self._executor.transfer_package_chunk(write)
                    if (
                        result.status == TargetExecutionStatus.FAILED
                        and result.error_code == TargetExecutionErrorCode.OFFSET_MISMATCH
                    ):
                        offset = result.received_size_bytes
                        stream.seek(offset)
                        continue
                    if result.status != TargetExecutionStatus.SUCCEEDED:
                        raise RuntimeError(
                            "adapter release upload write failed: "
                            f"{result.error_code or TargetExecutionErrorCode.PROTOCOL_ERROR}"
                        )
                    expected = offset + len(chunk)
                    if result.received_size_bytes != expected:
                        raise RuntimeError("adapter release upload response offset mismatch")
                    uploaded += len(chunk)
                    offset = expected
                    if size == 0:
                        break
            if not result.complete:
                raise RuntimeError("adapter release upload ended before file completion")
        return AdapterReleaseUploadResult(
            package_id=manifest.package_id,
            release_id=manifest.release_id,
            manifest_sha256=manifest_sha256,
            files_total=len(paths),
            bytes_total=total,
            bytes_uploaded=uploaded,
            bytes_resumed=resumed,
        )


class AdapterReleaseStageStatus(str, Enum):
    STAGED = "STAGED"
    ALREADY_STAGED = "ALREADY_STAGED"


class AdapterReleaseStageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-adapter-release-stage-request/v1"] = (
        "rolo-adapter-release-stage-request/v1"
    )
    request_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    target_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    robot_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    release_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    package_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    signing_key_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    signing_public_key_base64: str = Field(max_length=32_768)
    signing_public_key_sha256: str = Field(pattern=_SHA256_PATTERN)
    approval_id: str = Field(pattern=_APPROVAL_PATTERN)
    authorization: DeploymentAuthorizationProof | None = None

    @field_validator("signing_public_key_base64")
    @classmethod
    def validate_public_key(cls, value: str) -> str:
        try:
            payload = b64decode(value, validate=True)
        except ValueError as exc:
            raise ValueError("adapter release public key is invalid base64") from exc
        if not 1 <= len(payload) <= 16 * 1024:
            raise ValueError("adapter release public key size is out of bounds")
        return value

    @model_validator(mode="after")
    def bind_public_key_digest(self) -> AdapterReleaseStageRequest:
        if ed25519_public_key_sha256(self.public_key_bytes()) != self.signing_public_key_sha256:
            raise ValueError("adapter release public key digest mismatch")
        validate_deployment_request_authorization_binding(
            self,
            authorization=self.authorization,
            expected_target_id=self.target_id,
            expected_approval_id=self.approval_id,
        )
        return self

    def public_key_bytes(self) -> bytes:
        return b64decode(self.signing_public_key_base64, validate=True)

    def canonical_sha256(self) -> str:
        return hashlib.sha256(
            _canonical_json(self.model_dump(mode="json")).encode("utf-8")
        ).hexdigest()


class AdapterReleaseStageResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-adapter-release-stage-result/v1"] = (
        "rolo-adapter-release-stage-result/v1"
    )
    request_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    request_sha256: str = Field(pattern=_SHA256_PATTERN)
    target_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    robot_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    release_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    package_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    signing_key_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    signing_public_key_sha256: str = Field(pattern=_SHA256_PATTERN)
    status: AdapterReleaseStageStatus
    staged_root: str = Field(min_length=1, max_length=4096)
    release_root: str = Field(min_length=1, max_length=4096)
    runtime_context_path: str = Field(min_length=1, max_length=4096)


class AdapterReleaseStageExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-adapter-release-stage-execution-result/v1"] = (
        "rolo-adapter-release-stage-execution-result/v1"
    )
    request_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    request_sha256: str = Field(pattern=_SHA256_PATTERN)
    target_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    robot_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    release_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    package_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    signing_key_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    signing_public_key_sha256: str = Field(pattern=_SHA256_PATTERN)
    executor_kind: TargetExecutorKind
    execution_status: TargetExecutionStatus
    error_code: TargetExecutionErrorCode | None = None
    stage: AdapterReleaseStageResult | None = None

    @model_validator(mode="after")
    def require_consistent_execution(self) -> AdapterReleaseStageExecutionResult:
        if self.execution_status == TargetExecutionStatus.SUCCEEDED:
            if self.error_code is not None or self.stage is None:
                raise ValueError("successful adapter release stage execution is incomplete")
        elif self.error_code is None or self.stage is not None:
            raise ValueError("failed adapter release stage execution is inconsistent")
        if self.stage is not None and (
            self.stage.request_id != self.request_id
            or self.stage.request_sha256 != self.request_sha256
            or self.stage.target_id != self.target_id
            or self.stage.robot_id != self.robot_id
            or self.stage.release_id != self.release_id
            or self.stage.package_id != self.package_id
            or self.stage.manifest_sha256 != self.manifest_sha256
            or self.stage.signing_key_id != self.signing_key_id
            or self.stage.signing_public_key_sha256
            != self.signing_public_key_sha256
        ):
            raise ValueError("adapter release stage execution binding mismatch")
        return self


class AdapterReleaseDeploymentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-adapter-release-deployment-result/v1"] = (
        "rolo-adapter-release-deployment-result/v1"
    )
    target_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    robot_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    release_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    signing_key_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    signing_public_key_sha256: str = Field(pattern=_SHA256_PATTERN)
    upload: AdapterReleaseUploadResult
    execution: AdapterReleaseStageExecutionResult

    @model_validator(mode="after")
    def bind_deployment(self) -> AdapterReleaseDeploymentResult:
        if (
            self.execution.target_id != self.target_id
            or self.execution.robot_id != self.robot_id
            or self.execution.release_id != self.release_id
            or self.upload.release_id != self.release_id
            or self.upload.package_id != self.execution.package_id
            or self.execution.signing_key_id != self.signing_key_id
            or self.execution.signing_public_key_sha256
            != self.signing_public_key_sha256
        ):
            raise ValueError("adapter release deployment identity mismatch")
        if self.upload.manifest_sha256 != self.execution.manifest_sha256:
            raise ValueError("adapter release deployment manifest digest mismatch")
        return self


class AdapterReleaseDeploymentOperator:
    """Upload a verified frozen release, then request non-active target staging."""

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
        self._verifier = Ed25519AdapterReleaseVerifier(
            {signing_key_id: signing_public_key}
        )
        self._public_key_sha256 = self._verifier.public_key_sha256(signing_key_id)
        self._uploader = AdapterReleaseUploader(
            executor,
            self._verifier,
            chunk_size_bytes=chunk_size_bytes,
        )

    def upload_and_stage(
        self,
        root: Path,
        *,
        target_id: str,
        request_id: str,
        approval_id: str,
    ) -> AdapterReleaseDeploymentResult:
        _, manifest, signature, _ = load_verified_adapter_release_transfer(
            root,
            self._verifier,
        )
        if target_id != manifest.target_id or signature.key_id != self._key_id:
            raise ValueError("adapter release deployment identity or signing key mismatch")
        if len(request_id) > 80:
            raise ValueError("adapter release deployment request ID is too long")
        request = AdapterReleaseStageRequest(
            request_id=request_id,
            target_id=manifest.target_id,
            robot_id=manifest.robot_id,
            release_id=manifest.release_id,
            package_id=manifest.package_id,
            manifest_sha256=manifest.canonical_sha256(),
            signing_key_id=self._key_id,
            signing_public_key_base64=b64encode(self._public_key).decode("ascii"),
            signing_public_key_sha256=self._public_key_sha256,
            approval_id=approval_id,
        )
        upload = self._uploader.upload(root, request_prefix=f"{request_id}-upload")
        execution = self._executor.stage_adapter_release(request)
        return AdapterReleaseDeploymentResult(
            target_id=manifest.target_id,
            robot_id=manifest.robot_id,
            release_id=manifest.release_id,
            signing_key_id=self._key_id,
            signing_public_key_sha256=self._public_key_sha256,
            upload=upload,
            execution=execution,
        )


def _make_tree_read_only(root: Path) -> None:
    if os.name != "posix":
        # W5 targets Linux. Windows test hosts cannot express the same Unix
        # write/execute contract with chmod alone, and read-only trees impede cleanup.
        return
    files = sorted((path for path in root.rglob("*") if path.is_file()), reverse=True)
    directories = sorted((path for path in root.rglob("*") if path.is_dir()), reverse=True)
    for path in files:
        mode = path.stat().st_mode
        path.chmod(0o555 if mode & stat.S_IXUSR else 0o444)
    for path in directories:
        path.chmod(0o555)
    root.chmod(0o555)


def _remove_staging_tree(root: Path) -> None:
    if not root.is_dir():
        return
    if os.name == "posix":
        for path in root.rglob("*"):
            if path.is_dir():
                path.chmod(0o755)
            elif path.is_file():
                path.chmod(0o644)
        root.chmod(0o755)
    shutil.rmtree(root)


class AdapterReleaseStager:
    """Verify signed incoming bytes and atomically create a non-active read-only stage."""

    def __init__(self, *, incoming_root: Path, install_root: Path) -> None:
        self.incoming_root = incoming_root.expanduser().absolute()
        self.install_root = install_root.expanduser().absolute()
        if self.incoming_root.is_symlink() or self.install_root.is_symlink():
            raise ValueError("adapter release roots cannot be symbolic links")

    def stage(
        self,
        request: AdapterReleaseStageRequest,
        *,
        verifier: AdapterReleaseSignatureVerifier,
    ) -> AdapterReleaseStageResult:
        source = (
            self.incoming_root
            / "packages"
            / request.package_id
            / request.manifest_sha256
        )
        resolved, manifest, signature, _ = load_verified_adapter_release_transfer(
            source,
            verifier,
        )
        if (
            manifest.canonical_sha256() != request.manifest_sha256
            or manifest.target_id != request.target_id
            or manifest.robot_id != request.robot_id
            or manifest.release_id != request.release_id
            or manifest.package_id != request.package_id
            or signature.key_id != request.signing_key_id
            or verifier.public_key_sha256(signature.key_id)
            != request.signing_public_key_sha256
        ):
            raise ValueError("adapter release stage request binding mismatch")
        destination = (
            self.install_root
            / "robots"
            / request.robot_id
            / "staged"
            / f"{request.release_id}-{manifest.release_manifest_sha256[:16]}"
        )
        lock_target = destination.with_suffix(".stage-lock")
        with interprocess_lock(lock_target):
            if destination.is_dir():
                _, existing, existing_signature, _ = load_verified_adapter_release_transfer(
                    destination,
                    verifier,
                )
                if (
                    existing.canonical_sha256() != request.manifest_sha256
                    or existing_signature.key_id != request.signing_key_id
                ):
                    raise ValueError("existing adapter release stage differs from request")
                status = AdapterReleaseStageStatus.ALREADY_STAGED
            else:
                temporary = destination.with_name(
                    f".{destination.name}.staging-{uuid4().hex[:12]}"
                )
                try:
                    temporary.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(resolved, temporary, symlinks=True)
                    load_verified_adapter_release_transfer(temporary, verifier)
                    _make_tree_read_only(temporary)
                    os.replace(temporary, destination)
                except Exception:
                    if temporary.is_dir():
                        _remove_staging_tree(temporary)
                    raise
                status = AdapterReleaseStageStatus.STAGED
        return AdapterReleaseStageResult(
            request_id=request.request_id,
            request_sha256=request.canonical_sha256(),
            target_id=request.target_id,
            robot_id=request.robot_id,
            release_id=request.release_id,
            package_id=request.package_id,
            manifest_sha256=request.manifest_sha256,
            signing_key_id=request.signing_key_id,
            signing_public_key_sha256=request.signing_public_key_sha256,
            status=status,
            staged_root=str(destination),
            release_root=str(destination / "release"),
            runtime_context_path=str(destination / ADAPTER_RUNTIME_CONTEXT),
        )
