"""Sanitized, read-only target readiness projection for the R1 producer contract."""

from __future__ import annotations

import hashlib
import os
import platform as host_platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from rolo.target_ref import LocalTargetRef, SshTargetRef
from rolo.targets.profiles import TargetProfile, TargetProfileStore

TARGET_READINESS_API_FEATURES = ("workbench.target-readiness/v1",)

TargetId = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_-]{2,63}$")]
SafeText = Annotated[str, StringConstraints(min_length=1, max_length=256)]
TargetKind = Literal["local", "ssh"]
TargetState = Literal[
    "READY", "HOST_KEY_REQUIRED", "UNREACHABLE", "WORKSPACE_MISSING", "UNSUPPORTED"
]
CompanionState = Literal["NOT_REQUIRED", "AVAILABLE", "MISSING", "UNKNOWN"]
Freshness = Literal["fresh", "stale", "unknown"]

_UNSAFE_TERMS = (
    "ssh://",
    "credential",
    "password",
    "secret",
    "token",
    "known_hosts",
    "private key",
    "command",
    "shell",
    "artifact",
    "local_path",
    "remote_path",
    "workspace/",
    "c:\\",
    "/home/",
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_text(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("readiness text must not be empty")
    if any(term in normalized.casefold() for term in _UNSAFE_TERMS):
        raise ValueError("readiness text contains a restricted reference")
    return normalized[:256]


class TargetReadinessSummary(BaseModel):
    """Public R1 facts; target references and credentials are intentionally absent."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-readiness-summary/v1"] = (
        "rolo-target-readiness-summary/v1"
    )
    target_id: TargetId
    target_kind: TargetKind
    state: TargetState
    reachable: bool
    host_key_pinned: bool | None
    platform: str | None = Field(default=None, max_length=256)
    architecture: str | None = Field(default=None, max_length=256)
    workspace_accessible: bool
    companion: CompanionState
    blockers: list[SafeText] = Field(default_factory=list, max_length=10)
    diagnostics: list[SafeText] = Field(default_factory=list, max_length=10)
    limitations: list[SafeText] = Field(default_factory=list, max_length=10)
    observed_at: datetime
    freshness: Freshness
    producer_revision: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
    contains_secret_payloads: Literal[False] = False

    @field_validator("platform", "architecture")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        return None if value is None else _safe_text(value)

    @field_validator("blockers", "diagnostics", "limitations")
    @classmethod
    def validate_safe_texts(cls, values: list[str]) -> list[str]:
        return [_safe_text(value) for value in values]


class TargetReadinessCollection(BaseModel):
    """Paginated collection returned by the R1 list endpoint."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-readiness-collection/v1"] = (
        "rolo-target-readiness-collection/v1"
    )
    items: list[TargetReadinessSummary] = Field(default_factory=list)
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    next_offset: int | None = Field(default=None, ge=0)
    observed_at: datetime
    freshness: Freshness
    producer_revision: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
    contains_secret_payloads: Literal[False] = False


def _revision(profile: TargetProfile, state: str, *, workspace_accessible: bool) -> str:
    # The revision is opaque and contains no target reference or credential material.
    material = "|".join(
        [
            profile.profile_id,
            profile.updated_at.isoformat(),
            profile.target.kind,
            state,
            str(workspace_accessible),
            profile.host_key.status if profile.host_key else "NONE",
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _local_summary(
    profile: TargetProfile, target: LocalTargetRef, observed_at: datetime
) -> TargetReadinessSummary:
    workspace = target.workspace
    accessible = workspace.is_dir() and os.access(workspace, os.R_OK | os.X_OK)
    state: TargetState = "READY" if accessible else "WORKSPACE_MISSING"
    blockers = [] if accessible else ["WORKSPACE_MISSING"]
    diagnostics = ["Local workspace is readable and accessible."] if accessible else [
        "Local workspace is missing or inaccessible."
    ]
    return TargetReadinessSummary(
        target_id=profile.profile_id,
        target_kind="local",
        state=state,
        reachable=accessible,
        host_key_pinned=None,
        platform=host_platform.system().lower() or "unknown",
        architecture=host_platform.machine().lower() or "unknown",
        workspace_accessible=accessible,
        companion="NOT_REQUIRED",
        blockers=blockers,
        diagnostics=diagnostics,
        limitations=["Local readiness checks inspect workspace metadata only."],
        observed_at=observed_at,
        freshness="fresh",
        producer_revision=_revision(profile, state, workspace_accessible=accessible),
    )


def _ssh_summary(
    profile: TargetProfile, target: SshTargetRef, observed_at: datetime
) -> TargetReadinessSummary:
    approved = bool(
        profile.host_key
        and profile.host_key.status == "APPROVED"
        and profile.host_key.fingerprint
    )
    if not approved:
        state: TargetState = "HOST_KEY_REQUIRED"
        blockers = ["HOST_KEY_REQUIRED"]
        diagnostics = ["Target host key approval is required before readiness probing."]
    else:
        state = "UNREACHABLE"
        blockers = ["UNREACHABLE"]
        diagnostics = ["SSH readiness probe is unavailable in this read-only projection."]
    return TargetReadinessSummary(
        target_id=profile.profile_id,
        target_kind="ssh",
        state=state,
        reachable=False,
        host_key_pinned=approved,
        platform=None,
        architecture=None,
        workspace_accessible=False,
        companion="UNKNOWN",
        blockers=blockers,
        diagnostics=diagnostics,
        limitations=["A paired producer probe is required to report live SSH reachability."],
        observed_at=observed_at,
        freshness="unknown",
        producer_revision=_revision(profile, state, workspace_accessible=False),
    )


def build_target_readiness_summary(
    profile: TargetProfile, *, observed_at: datetime | None = None
) -> TargetReadinessSummary:
    timestamp = observed_at or _utc_now()
    if isinstance(profile.target, LocalTargetRef):
        return _local_summary(profile, profile.target, timestamp)
    if isinstance(profile.target, SshTargetRef):
        return _ssh_summary(profile, profile.target, timestamp)
    return TargetReadinessSummary(
        target_id=profile.profile_id,
        target_kind="local",
        state="UNSUPPORTED",
        reachable=False,
        host_key_pinned=None,
        platform=None,
        architecture=None,
        workspace_accessible=False,
        companion="UNKNOWN",
        blockers=["UNSUPPORTED"],
        diagnostics=["Target kind is not supported by the readiness producer."],
        limitations=["Producer support is limited to local and SSH target kinds."],
        observed_at=timestamp,
        freshness="unknown",
        producer_revision=_revision(profile, "UNSUPPORTED", workspace_accessible=False),
    )


def _load_profiles(config_root: Path) -> list[TargetProfile]:
    try:
        return TargetProfileStore(config_root).list_profiles()
    except (OSError, ValueError) as exc:
        raise ValueError(f"target readiness facts are unavailable: {exc}") from exc


def build_target_readiness_collection(
    config_root: Path,
    *,
    limit: int = 50,
    offset: int = 0,
    observed_at: datetime | None = None,
) -> TargetReadinessCollection:
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    if offset < 0:
        raise ValueError("offset must be non-negative")
    timestamp = observed_at or _utc_now()
    summaries = [
        build_target_readiness_summary(profile, observed_at=timestamp)
        for profile in _load_profiles(config_root)
    ]
    summaries.sort(key=lambda item: item.target_id)
    total = len(summaries)
    items = summaries[offset : offset + limit]
    next_offset = offset + limit if offset + limit < total else None
    freshness: Freshness = (
        "fresh" if all(item.freshness == "fresh" for item in summaries) else "unknown"
    )
    revision = hashlib.sha256(
        "|".join(item.producer_revision for item in summaries).encode("ascii")
    ).hexdigest()
    return TargetReadinessCollection(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        next_offset=next_offset,
        observed_at=timestamp,
        freshness=freshness,
        producer_revision=revision,
    )


def get_target_readiness_summary(
    config_root: Path, target_id: str
) -> TargetReadinessSummary | None:
    try:
        profile = TargetProfileStore(config_root).load(target_id)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        raise ValueError(f"target readiness facts are unavailable: {exc}") from exc
    return build_target_readiness_summary(profile)
