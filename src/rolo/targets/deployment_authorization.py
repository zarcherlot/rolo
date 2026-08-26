from __future__ import annotations

import hashlib
import json
from base64 import b64decode, b64encode
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal, TypeVar
from uuid import uuid4

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from rolo.core.persistence import atomic_write_text, interprocess_lock
from rolo.targets.deployment_jobs import DeploymentJobStore
from rolo.targets.models import ApprovalAction
from rolo.targets.package_signing import _read_bounded_key, ed25519_public_key_sha256

_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"
_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_PRINCIPAL_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,127}$"
_SIGNATURE_PATTERN = r"^[A-Za-z0-9+/]{86}==$"
_MAX_CLOCK_SKEW = timedelta(seconds=30)
_RequestT = TypeVar("_RequestT", bound=BaseModel)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


class DeploymentAuthorizationGrant(BaseModel):
    """Short-lived controller capability verified against a target-local key pin."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-deployment-authorization-grant/v1"] = (
        "rolo-deployment-authorization-grant/v1"
    )
    authorization_id: str = Field(pattern=r"^authorization-[0-9a-f]{32}$")
    approval_id: str = Field(pattern=r"^approval-[0-9a-f]{32}$")
    decision_id: str = Field(pattern=r"^decision-[0-9a-f]{32}$")
    job_id: str = Field(pattern=r"^deployment-[0-9a-f]{32}$")
    target_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    command_sha256: str = Field(pattern=_SHA256_PATTERN)
    action: ApprovalAction
    approver_principal: str = Field(pattern=_PRINCIPAL_PATTERN)
    request_schema_version: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$",
    )
    request_payload_sha256: str = Field(pattern=_SHA256_PATTERN)
    issued_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def require_short_lifetime(self) -> DeploymentAuthorizationGrant:
        if self.issued_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("deployment authorization timestamps must be timezone-aware")
        if self.expires_at <= self.issued_at:
            raise ValueError("deployment authorization expiry must follow issuance")
        if (self.expires_at - self.issued_at).total_seconds() > 600:
            raise ValueError("deployment authorization lifetime exceeds ten minutes")
        return self

    def canonical_json(self) -> str:
        return _canonical_json(self.model_dump(mode="json"))

    def canonical_sha256(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


class DeploymentAuthorizationSignature(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-deployment-authorization-signature/v1"] = (
        "rolo-deployment-authorization-signature/v1"
    )
    key_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    grant_sha256: str = Field(pattern=_SHA256_PATTERN)
    signature_base64: str = Field(pattern=_SIGNATURE_PATTERN)

    @field_validator("signature_base64")
    @classmethod
    def validate_signature(cls, value: str) -> str:
        try:
            signature = b64decode(value, validate=True)
        except ValueError as exc:
            raise ValueError("deployment authorization signature is invalid base64") from exc
        if len(signature) != 64:
            raise ValueError("deployment authorization signature must be 64 bytes")
        return value


class DeploymentAuthorizationProof(BaseModel):
    """Portable proof; the verification key is deliberately not part of the request."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-deployment-authorization-proof/v1"] = (
        "rolo-deployment-authorization-proof/v1"
    )
    grant: DeploymentAuthorizationGrant
    signature: DeploymentAuthorizationSignature

    @model_validator(mode="after")
    def bind_signature_digest(self) -> DeploymentAuthorizationProof:
        if self.signature.grant_sha256 != self.grant.canonical_sha256():
            raise ValueError("deployment authorization proof digest mismatch")
        return self


class DeploymentAuthorizationKeyPin(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-deployment-authorization-key-pin/v1"] = (
        "rolo-deployment-authorization-key-pin/v1"
    )
    target_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    key_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    public_key_base64: str = Field(max_length=32_768)
    public_key_sha256: str = Field(pattern=_SHA256_PATTERN)
    installed_by_approval_id: str = Field(pattern=r"^approval-[0-9a-f]{32}$")
    installed_at: datetime

    @field_validator("public_key_base64")
    @classmethod
    def validate_public_key(cls, value: str) -> str:
        try:
            payload = b64decode(value, validate=True)
        except ValueError as exc:
            raise ValueError("deployment authorization public key is invalid base64") from exc
        if len(payload) != 32:
            raise ValueError("deployment authorization public key must be raw Ed25519")
        return value

    @model_validator(mode="after")
    def require_public_key_digest(self) -> DeploymentAuthorizationKeyPin:
        if self.installed_at.tzinfo is None:
            raise ValueError(
                "deployment authorization key install timestamp must be timezone-aware"
            )
        if ed25519_public_key_sha256(self.public_key_bytes()) != self.public_key_sha256:
            raise ValueError("deployment authorization public key digest mismatch")
        return self

    def public_key_bytes(self) -> bytes:
        return b64decode(self.public_key_base64, validate=True)

    def canonical_sha256(self) -> str:
        return hashlib.sha256(
            _canonical_json(self.model_dump(mode="json")).encode("utf-8")
        ).hexdigest()


def build_deployment_authorization_key_pin(
    *,
    target_id: str,
    key_id: str,
    public_key_path: Path,
    approval_id: str,
    installed_at: datetime | None = None,
) -> DeploymentAuthorizationKeyPin:
    """Load one bounded Ed25519 public key and bind it to an approved target install."""

    payload = _read_bounded_key(public_key_path, private=False)
    try:
        if payload.startswith(b"-----BEGIN"):
            key = serialization.load_pem_public_key(payload)
        else:
            key = Ed25519PublicKey.from_public_bytes(payload)
    except (TypeError, ValueError) as exc:
        raise ValueError("deployment authorization public key is invalid") from exc
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("deployment authorization public key must be Ed25519")
    raw = key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return DeploymentAuthorizationKeyPin(
        target_id=target_id,
        key_id=key_id,
        public_key_base64=b64encode(raw).decode("ascii"),
        public_key_sha256=ed25519_public_key_sha256(raw),
        installed_by_approval_id=approval_id,
        installed_at=installed_at or _utc_now(),
    )


def verify_deployment_authorization_signing_key_pair(
    *,
    public_key_path: Path,
    private_key_path: Path,
) -> str:
    """Fail closed unless the Controller signer matches the target-installed public pin."""

    public_payload = _read_bounded_key(public_key_path, private=False)
    private_payload = _read_bounded_key(private_key_path, private=True)
    try:
        public_key = (
            serialization.load_pem_public_key(public_payload)
            if public_payload.startswith(b"-----BEGIN")
            else Ed25519PublicKey.from_public_bytes(public_payload)
        )
        private_key = serialization.load_pem_private_key(
            private_payload,
            password=None,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("deployment authorization signing key pair is invalid") from exc
    if not isinstance(public_key, Ed25519PublicKey) or not isinstance(
        private_key,
        Ed25519PrivateKey,
    ):
        raise ValueError("deployment authorization signing key pair must be Ed25519")
    public_raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    private_public_raw = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    if public_raw != private_public_raw:
        raise ValueError("deployment authorization signing key pair does not match")
    return hashlib.sha256(public_raw).hexdigest()


class DeploymentAuthorizationKeyConflict(ValueError):
    pass


def deployment_request_payload_sha256(request: BaseModel) -> str:
    """Digest a request while excluding its non-authoritative proof wrapper."""

    return hashlib.sha256(
        _canonical_json(
            request.model_dump(mode="json", exclude={"authorization"})
        ).encode("utf-8")
    ).hexdigest()


def validate_deployment_request_authorization_binding(
    request: BaseModel,
    *,
    authorization: DeploymentAuthorizationProof | None,
    expected_target_id: str,
    expected_approval_id: str | None = None,
) -> None:
    """Reject a structurally detached proof before target-side signature verification."""

    if authorization is None:
        return
    grant = authorization.grant
    schema_version = getattr(request, "schema_version", None)
    if (
        grant.target_id != expected_target_id
        or grant.request_schema_version != schema_version
        or grant.request_payload_sha256 != deployment_request_payload_sha256(request)
        or (
            expected_approval_id is not None
            and grant.approval_id != expected_approval_id
        )
    ):
        raise ValueError("deployment authorization request binding mismatch")


def issue_deployment_authorization(
    store: DeploymentJobStore,
    *,
    approval_id: str,
    request_schema_version: str,
    request_payload_sha256: str,
    signing_key_id: str,
    private_key_path: Path,
    now: datetime | None = None,
    lifetime_s: int = 300,
    authorization_id: str | None = None,
) -> tuple[DeploymentAuthorizationGrant, DeploymentAuthorizationSignature]:
    observed_at = now or _utc_now()
    if not 1 <= lifetime_s <= 600:
        raise ValueError("deployment authorization lifetime is out of bounds")
    request = store.load_approval_request(approval_id)
    if request.authorization_scope_sha256 is None:
        raise ValueError("approval does not contain an authorization scope")
    if request.authorization_scope_sha256 != request_payload_sha256:
        raise ValueError("approval authorization scope does not match the request payload")
    decision = store.verify_approval(
        approval_id,
        job_id=request.job_id,
        target_id=request.target_id,
        command_sha256=request.command_sha256,
        action=request.action,
        now=observed_at,
    )
    expires_at = min(request.expires_at, observed_at + timedelta(seconds=lifetime_s))
    grant = DeploymentAuthorizationGrant(
        authorization_id=authorization_id or f"authorization-{uuid4().hex}",
        approval_id=approval_id,
        decision_id=decision.decision_id,
        job_id=request.job_id,
        target_id=request.target_id,
        command_sha256=request.command_sha256,
        action=request.action,
        approver_principal=decision.principal,
        request_schema_version=request_schema_version,
        request_payload_sha256=request_payload_sha256,
        issued_at=observed_at,
        expires_at=expires_at,
    )
    try:
        private_key = serialization.load_pem_private_key(
            _read_bounded_key(private_key_path, private=True),
            password=None,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("deployment authorization private key is invalid") from exc
    if not isinstance(private_key, Ed25519PrivateKey):
        raise ValueError("deployment authorization private key must be Ed25519")
    signature = private_key.sign(grant.canonical_json().encode("utf-8"))
    return grant, DeploymentAuthorizationSignature(
        key_id=signing_key_id,
        grant_sha256=grant.canonical_sha256(),
        signature_base64=b64encode(signature).decode("ascii"),
    )


def authorize_deployment_request(
    request: _RequestT,
    store: DeploymentJobStore,
    *,
    approval_id: str,
    signing_key_id: str,
    private_key_path: Path,
    now: datetime | None = None,
    lifetime_s: int = 300,
    authorization_id: str | None = None,
) -> _RequestT:
    """Attach a target-verifiable proof to one immutable request payload."""

    if getattr(request, "authorization", None) is not None:
        raise ValueError("deployment request is already authorized")
    schema_version = getattr(request, "schema_version", None)
    if not isinstance(schema_version, str):
        raise ValueError("deployment request schema version is unavailable")
    grant, signature = issue_deployment_authorization(
        store,
        approval_id=approval_id,
        request_schema_version=schema_version,
        request_payload_sha256=deployment_request_payload_sha256(request),
        signing_key_id=signing_key_id,
        private_key_path=private_key_path,
        now=now,
        lifetime_s=lifetime_s,
        authorization_id=authorization_id,
    )
    values = request.model_dump(mode="json")
    values["authorization"] = DeploymentAuthorizationProof(
        grant=grant,
        signature=signature,
    ).model_dump(mode="json")
    return type(request).model_validate(values)


def verify_deployment_authorization(
    grant: DeploymentAuthorizationGrant,
    signature: DeploymentAuthorizationSignature,
    *,
    pin: DeploymentAuthorizationKeyPin,
    expected_target_id: str,
    expected_action: ApprovalAction,
    expected_request_schema_version: str,
    expected_request_payload_sha256: str,
    expected_approval_id: str | None = None,
    now: datetime | None = None,
) -> None:
    observed_at = now or _utc_now()
    if pin.target_id != expected_target_id:
        raise ValueError("deployment authorization key pin target mismatch")
    if signature.key_id != pin.key_id:
        raise ValueError("deployment authorization signing key mismatch")
    if signature.grant_sha256 != grant.canonical_sha256():
        raise ValueError("deployment authorization grant digest mismatch")
    if (
        grant.target_id != expected_target_id
        or grant.action != expected_action
        or grant.request_schema_version != expected_request_schema_version
        or grant.request_payload_sha256 != expected_request_payload_sha256
        or (expected_approval_id is not None and grant.approval_id != expected_approval_id)
    ):
        raise ValueError("deployment authorization grant binding mismatch")
    if observed_at < grant.issued_at - _MAX_CLOCK_SKEW:
        raise ValueError("deployment authorization grant is from the future")
    if observed_at > grant.expires_at + _MAX_CLOCK_SKEW:
        raise ValueError("deployment authorization grant is expired")
    try:
        Ed25519PublicKey.from_public_bytes(pin.public_key_bytes()).verify(
            b64decode(signature.signature_base64, validate=True),
            grant.canonical_json().encode("utf-8"),
        )
    except (ValueError, TypeError) as exc:
        raise ValueError("deployment authorization public key is invalid") from exc
    except InvalidSignature as exc:
        raise ValueError("deployment authorization signature verification failed") from exc


def verify_deployment_request_authorization(
    request: BaseModel,
    *,
    authorization: DeploymentAuthorizationProof | None,
    pin: DeploymentAuthorizationKeyPin,
    expected_target_id: str,
    expected_action: ApprovalAction,
    expected_approval_id: str | None = None,
    now: datetime | None = None,
) -> None:
    if authorization is None:
        raise ValueError("deployment authorization proof is required")
    schema_version = getattr(request, "schema_version", None)
    if not isinstance(schema_version, str):
        raise ValueError("deployment request schema version is unavailable")
    verify_deployment_authorization(
        authorization.grant,
        authorization.signature,
        pin=pin,
        expected_target_id=expected_target_id,
        expected_action=expected_action,
        expected_request_schema_version=schema_version,
        expected_request_payload_sha256=deployment_request_payload_sha256(request),
        expected_approval_id=expected_approval_id,
        now=now,
    )


class DeploymentAuthorizationKeyRegistry:
    """Target-local authorization trust anchor installed during an approved bootstrap."""

    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().absolute()
        if self.root.is_symlink():
            raise ValueError("deployment authorization pin root cannot be a symbolic link")

    def _path(self, target_id: str) -> Path:
        if not target_id or len(target_id) > 128 or not all(
            character.isalnum() or character in "._-" for character in target_id
        ):
            raise ValueError("invalid deployment authorization pin target")
        return self.root / "targets" / target_id / "current.json"

    def install_initial(self, pin: DeploymentAuthorizationKeyPin) -> DeploymentAuthorizationKeyPin:
        path = self._path(pin.target_id)
        if path.is_symlink():
            raise ValueError("deployment authorization pin cannot be a symbolic link")
        atomic_write_text(
            path,
            pin.model_dump_json(indent=2) + "\n",
            require_absent=True,
        )
        return pin

    def load(self, target_id: str) -> DeploymentAuthorizationKeyPin:
        path = self._path(target_id)
        if path.is_symlink() or not path.is_file():
            raise ValueError("deployment authorization key pin is unavailable")
        if path.stat().st_size > 64 * 1024:
            raise ValueError("deployment authorization key pin exceeds its size limit")
        return DeploymentAuthorizationKeyPin.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    def replace(
        self,
        pin: DeploymentAuthorizationKeyPin,
        *,
        expected_current_public_key_sha256: str,
    ) -> DeploymentAuthorizationKeyPin:
        """Bootstrap-only CAS; caller must already hold an independently approved trust path."""

        path = self._path(pin.target_id)
        with interprocess_lock(path):
            current = self.load(pin.target_id)
            if current.public_key_sha256 != expected_current_public_key_sha256:
                raise DeploymentAuthorizationKeyConflict(
                    "deployment authorization key pin CAS mismatch"
                )
            atomic_write_text(
                path,
                pin.model_dump_json(indent=2) + "\n",
                acquire_lock=False,
            )
        return pin

    def assess_bootstrap_update(
        self,
        pin: DeploymentAuthorizationKeyPin,
        *,
        expected_current_public_key_sha256: str | None,
    ) -> Literal["READY", "ALREADY_CURRENT"]:
        """Validate an approved Bootstrap CAS without changing the trust anchor."""

        path = self._path(pin.target_id)
        current = self.load(pin.target_id) if path.exists() else None
        if current == pin:
            return "ALREADY_CURRENT"
        if expected_current_public_key_sha256 is None:
            if current is not None:
                raise DeploymentAuthorizationKeyConflict(
                    "initial deployment authorization key pin already exists"
                )
            return "READY"
        if (
            current is None
            or current.public_key_sha256
            != expected_current_public_key_sha256
        ):
            raise DeploymentAuthorizationKeyConflict(
                "deployment authorization key pin CAS mismatch"
            )
        return "READY"

    def apply_bootstrap_update(
        self,
        pin: DeploymentAuthorizationKeyPin,
        *,
        expected_current_public_key_sha256: str | None,
    ) -> Literal["INSTALLED", "ALREADY_CURRENT"]:
        """Commit one independently approved Bootstrap pin install or rotation."""

        path = self._path(pin.target_id)
        if path.is_symlink():
            raise ValueError("deployment authorization pin cannot be a symbolic link")
        with interprocess_lock(path):
            disposition = self.assess_bootstrap_update(
                pin,
                expected_current_public_key_sha256=(
                    expected_current_public_key_sha256
                ),
            )
            if disposition == "ALREADY_CURRENT":
                return disposition
            atomic_write_text(
                path,
                pin.model_dump_json(indent=2) + "\n",
                acquire_lock=False,
                require_absent=expected_current_public_key_sha256 is None,
            )
        return "INSTALLED"
