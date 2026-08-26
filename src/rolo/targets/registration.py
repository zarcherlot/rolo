from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rolo.core.persistence import atomic_write_text, interprocess_lock
from rolo.targets.models import (
    TargetConnectionProfile,
    TargetProfile,
    TargetTransport,
)
from rolo.targets.registry import TargetProfileRegistry

_IDEMPOTENCY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{7,127}$")
_PRINCIPAL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,127}$")


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


class TargetRegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-registration-request/v1"] = (
        "rolo-target-registration-request/v1"
    )
    target: TargetProfile
    connection: TargetConnectionProfile | None = None

    @model_validator(mode="after")
    def bind_transport(self) -> TargetRegistrationRequest:
        if self.target.transport == TargetTransport.SSH:
            if self.connection is None:
                raise ValueError("SSH target registration requires a connection profile")
            if self.target.connection_profile_id != self.connection.connection_profile_id:
                raise ValueError("target registration connection identity mismatch")
            if self.target.trust_level != self.connection.trust_level:
                raise ValueError("target registration trust level mismatch")
        elif self.connection is not None:
            raise ValueError("LOCAL target registration rejects a connection profile")
        return self

    def canonical_sha256(self) -> str:
        return hashlib.sha256(
            _canonical_json(self.model_dump(mode="json")).encode("utf-8")
        ).hexdigest()


class TargetRegistrationStatus(str, Enum):
    CREATED = "CREATED"
    ALREADY_REGISTERED = "ALREADY_REGISTERED"


class TargetRegistrationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-registration-result/v1"] = (
        "rolo-target-registration-result/v1"
    )
    target_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: TargetRegistrationStatus
    target: TargetProfile
    connection: TargetConnectionProfile | None = None
    registered_at: datetime

    @model_validator(mode="after")
    def bind_result(self) -> TargetRegistrationResult:
        request = TargetRegistrationRequest(
            target=self.target,
            connection=self.connection,
        )
        if self.target_id != self.target.target_id:
            raise ValueError("target registration result identity mismatch")
        if request.canonical_sha256() != self.request_sha256:
            raise ValueError("target registration result request digest mismatch")
        return self


class TargetRegistrationReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-registration-receipt/v1"] = (
        "rolo-target-registration-receipt/v1"
    )
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{7,127}$")
    principal: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,127}$")
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    result: TargetRegistrationResult


class TargetRegistrationConflict(ValueError):
    pass


def target_connection_binding_sha256(
    target: TargetProfile,
    connection: TargetConnectionProfile | None,
) -> str:
    request = TargetRegistrationRequest(target=target, connection=connection)
    return request.canonical_sha256()


class TargetRegistrationService:
    """Secret-free, idempotent registration over the existing profile registry."""

    def __init__(self, registry: TargetProfileRegistry) -> None:
        self.registry = registry
        self.root = registry.root / "registration-control"

    def _receipt_path(self, idempotency_key: str) -> Path:
        if _IDEMPOTENCY.fullmatch(idempotency_key) is None:
            raise ValueError("invalid target registration idempotency key")
        digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
        return self.root / "receipts" / f"{digest}.json"

    def _load_receipt(self, path: Path) -> TargetRegistrationReceipt | None:
        if path.is_symlink():
            raise ValueError("target registration receipt cannot be a symbolic link")
        if not path.exists():
            return None
        if not path.is_file() or path.stat().st_size > 256 * 1024:
            raise ValueError("target registration receipt is invalid")
        return TargetRegistrationReceipt.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    @staticmethod
    def _optional_target(
        registry: TargetProfileRegistry,
        target_id: str,
    ) -> TargetProfile | None:
        try:
            return registry.get_target(target_id)
        except FileNotFoundError:
            return None

    @staticmethod
    def _optional_connection(
        registry: TargetProfileRegistry,
        connection_id: str,
    ) -> TargetConnectionProfile | None:
        try:
            return registry.get_connection(connection_id)
        except FileNotFoundError:
            return None

    def register(
        self,
        request: TargetRegistrationRequest,
        *,
        principal: str,
        idempotency_key: str,
        now: datetime | None = None,
    ) -> TargetRegistrationResult:
        if _PRINCIPAL.fullmatch(principal) is None:
            raise ValueError("invalid target registration principal")
        receipt_path = self._receipt_path(idempotency_key)
        request_sha256 = request.canonical_sha256()
        with interprocess_lock(receipt_path):
            receipt = self._load_receipt(receipt_path)
            if receipt is not None:
                if (
                    receipt.idempotency_key != idempotency_key
                    or receipt.principal != principal
                    or receipt.request_sha256 != request_sha256
                ):
                    raise TargetRegistrationConflict(
                        "target registration idempotency key was reused"
                    )
                return receipt.result

            target_lock = self.root / "target-locks" / f"{request.target.target_id}.lock"
            with interprocess_lock(target_lock):
                current_target = self._optional_target(
                    self.registry,
                    request.target.target_id,
                )
                current_connection = (
                    self._optional_connection(
                        self.registry,
                        request.connection.connection_profile_id,
                    )
                    if request.connection is not None
                    else None
                )
                if current_target is not None and current_target != request.target:
                    raise TargetRegistrationConflict(
                        "target ID is already registered with a different profile"
                    )
                if (
                    request.connection is not None
                    and current_connection is not None
                    and current_connection != request.connection
                ):
                    raise TargetRegistrationConflict(
                        "connection profile ID is already registered differently"
                    )
                if request.connection is not None and current_connection is None:
                    self.registry.save_connection(request.connection)
                if current_target is None:
                    self.registry.save_target(request.target)
                result = TargetRegistrationResult(
                    target_id=request.target.target_id,
                    request_sha256=request_sha256,
                    status=(
                        TargetRegistrationStatus.ALREADY_REGISTERED
                        if current_target is not None
                        else TargetRegistrationStatus.CREATED
                    ),
                    target=request.target,
                    connection=request.connection,
                    registered_at=now or datetime.now(timezone.utc),
                )
                receipt = TargetRegistrationReceipt(
                    idempotency_key=idempotency_key,
                    principal=principal,
                    request_sha256=request_sha256,
                    result=result,
                )
                atomic_write_text(
                    receipt_path,
                    receipt.model_dump_json(indent=2) + "\n",
                    acquire_lock=False,
                    require_absent=True,
                )
                return result

    def load(self, target_id: str) -> TargetRegistrationRequest:
        target = self.registry.get_target(target_id)
        connection = (
            self.registry.get_connection(target.connection_profile_id or "")
            if target.transport == TargetTransport.SSH
            else None
        )
        return TargetRegistrationRequest(target=target, connection=connection)
