"""Producer-side export for the sanitized device hardening evidence contract.

The producer deliberately defaults every real-device scenario to
``PENDING_EXTERNAL``.  A scenario can only become ``VERIFIED`` when an audited
input record supplies all bounded evidence fields; fixture data is never
silently promoted.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from rolo.core.hashing import canonical_json_sha256
from rolo.core.persistence import atomic_write_text
from rolo.targets.profiles import TargetProfileStore

DEVICE_HARDENING_SCHEMA = "rolo-vis-device-hardening-evidence/v1"
DEVICE_HARDENING_SCENARIOS = (
    "linux-arm64",
    "linux-x86_64",
    "offline-install",
    "non-root-sudo",
    "ssh-jump-host",
    "host-key-rotation",
    "network-interruption",
    "restart-resume",
    "upgrade-rollback",
    "enrollment-rotation",
)
ScenarioId = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_-]{2,63}$")]
Revision = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{7,64}$")]
OpaqueId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")]
SafeText = Annotated[str, StringConstraints(min_length=1, max_length=240)]
Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{8,64}(?:…[0-9a-f]{8,64})?$")]

_UNSAFE_TERMS = (
    "artifact://",
    "ssh://",
    "http://",
    "https://",
    "known_hosts",
    "private key",
    "credential",
    "password",
    "secret",
    "token",
    "command",
    "shell",
    "argv",
    "raw_path",
    "local_path",
    "remote_path",
    "c:\\",
    "/home/",
)


def _safe_text(value: str) -> str:
    value = value.strip()
    if not value or any(term in value.casefold() for term in _UNSAFE_TERMS):
        raise ValueError("device hardening evidence contains a restricted reference")
    return value


class DeviceHardeningEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    os: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    architecture: Annotated[str, StringConstraints(min_length=1, max_length=40)]
    package_digest: Digest
    job_id: OpaqueId
    gate_result: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    observed_at: datetime
    summary: SafeText

    @field_validator("os", "architecture", "gate_result", "summary")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _safe_text(value)


class DeviceHardeningEvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: ScenarioId
    status: Literal["PENDING_EXTERNAL", "BLOCKED", "VERIFIED"]
    evidence: DeviceHardeningEvidence | None = None

    @model_validator(mode="after")
    def validate_status_evidence(self) -> DeviceHardeningEvidenceItem:
        if self.status == "VERIFIED" and self.evidence is None:
            raise ValueError("verified hardening evidence requires evidence")
        return self


class DeviceHardeningEvidenceBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-vis-device-hardening-evidence/v1"] = DEVICE_HARDENING_SCHEMA
    release_line: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    rolo_revision: Revision
    producer_revision: Revision
    target_id: OpaqueId
    target_kind: Literal["local", "ssh"]
    evidence: list[DeviceHardeningEvidenceItem] = Field(
        min_length=1, max_length=len(DEVICE_HARDENING_SCENARIOS)
    )

    @field_validator("release_line")
    @classmethod
    def validate_release_line(cls, value: str) -> str:
        return _safe_text(value)

    @model_validator(mode="after")
    def validate_scenarios(self) -> DeviceHardeningEvidenceBundle:
        ids = [item.scenario_id for item in self.evidence]
        if len(ids) != len(set(ids)):
            raise ValueError("device hardening scenarios must be unique")
        unknown = set(ids) - set(DEVICE_HARDENING_SCENARIOS)
        if unknown:
            raise ValueError(f"unknown device hardening scenario: {sorted(unknown)}")
        return self


class ReleaseLedgerEntry(BaseModel):
    """Auditable scenario index; it contains no raw transport or file data."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-release-ledger-entry/v1"] = "rolo-release-ledger-entry/v1"
    release_line: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    rolo_revision: Revision
    producer_revision: Revision
    target_id: OpaqueId
    target_kind: Literal["local", "ssh"]
    scenario_id: ScenarioId
    status: Literal["PENDING_EXTERNAL", "BLOCKED", "VERIFIED"]
    job_id: OpaqueId | None = None
    package_digest: Digest | None = None
    gate_result: SafeText | None = None
    observed_at: datetime | None = None
    limitations: list[SafeText] = Field(default_factory=list, max_length=8)
    review_status: Literal["UNREVIEWED", "REVIEWED"] = "UNREVIEWED"
    review_note: SafeText | None = None

    @field_validator("release_line", "gate_result", "review_note")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        return None if value is None else _safe_text(value)

    @field_validator("limitations")
    @classmethod
    def validate_limitations(cls, values: list[str]) -> list[str]:
        return [_safe_text(value) for value in values]

    @model_validator(mode="after")
    def validate_entry(self) -> ReleaseLedgerEntry:
        if self.status == "VERIFIED":
            if not all((self.job_id, self.package_digest, self.gate_result, self.observed_at)):
                raise ValueError("verified ledger entry is missing evidence fields")
        if self.review_status == "REVIEWED" and self.review_note is None:
            raise ValueError("reviewed ledger entry requires a review note")
        return self


class ReleaseLedger(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-release-ledger/v1"] = "rolo-release-ledger/v1"
    entries: list[ReleaseLedgerEntry] = Field(
        min_length=1, max_length=len(DEVICE_HARDENING_SCENARIOS)
    )

    @model_validator(mode="after")
    def validate_entries(self) -> ReleaseLedger:
        identities = [(entry.target_id, entry.scenario_id) for entry in self.entries]
        if len(identities) != len(set(identities)):
            raise ValueError("release ledger scenario identities must be unique")
        return self


class StagingHarnessManifest(BaseModel):
    """Stable, sanitized metadata emitted by the local staging harness."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-staging-harness-manifest/v1"] = "rolo-staging-harness-manifest/v1"
    release_line: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    rolo_revision: Revision
    producer_revisions: dict[str, Revision] = Field(min_length=1, max_length=8)
    target_ids: list[OpaqueId] = Field(min_length=1, max_length=100)
    job_ids: list[OpaqueId] = Field(min_length=1, max_length=100)
    gate_results: dict[str, Literal["PASS", "BLOCKED", "PENDING_EXTERNAL"]] = Field(
        min_length=1, max_length=16
    )
    failure_semantics: dict[str, Literal["BLOCKED", "PENDING", "PENDING_EXTERNAL"]] = Field(
        min_length=1, max_length=16
    )
    limitations: list[SafeText] = Field(min_length=1, max_length=8)

    @field_validator("release_line")
    @classmethod
    def validate_release_line(cls, value: str) -> str:
        return _safe_text(value)

    @field_validator("limitations")
    @classmethod
    def validate_limitations(cls, values: list[str]) -> list[str]:
        return [_safe_text(value) for value in values]


def producer_revision() -> str:
    """Return the stable revision of this producer contract implementation."""

    return canonical_json_sha256(
        {
            "schema": DEVICE_HARDENING_SCHEMA,
            "scenarios": DEVICE_HARDENING_SCENARIOS,
            "unsafe_terms": _UNSAFE_TERMS,
        }
    )


def _load_input(path: Path | None) -> dict[str, object]:
    if path is None:
        return {}
    if path.is_symlink() or not path.is_file():
        raise ValueError("device hardening input must be a regular file")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("device hardening input is invalid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("device hardening input must be an object")
    return payload


def build_device_hardening_bundle(
    config_root: Path,
    *,
    target_id: str,
    release_line: str,
    rolo_revision: str,
    evidence_input: Path | None = None,
    observed_at: datetime | None = None,
) -> DeviceHardeningEvidenceBundle:
    """Build a bounded bundle, defaulting to explicit external blockers."""

    try:
        profile = TargetProfileStore(config_root).load(target_id)
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise ValueError("target profile is unavailable for evidence export") from exc
    raw = _load_input(evidence_input)
    unknown_fields = set(raw) - {"evidence"}
    if unknown_fields:
        raise ValueError(f"device hardening input has unknown fields: {sorted(unknown_fields)}")
    candidates = raw.get("evidence", [])
    if not isinstance(candidates, list):
        raise ValueError("device hardening evidence input must contain an evidence list")
    supplied: dict[str, DeviceHardeningEvidenceItem] = {}
    for candidate in candidates:
        item = DeviceHardeningEvidenceItem.model_validate(candidate)
        if item.scenario_id in supplied:
            raise ValueError("device hardening evidence scenarios must be unique")
        supplied[item.scenario_id] = item
    unknown = set(supplied) - set(DEVICE_HARDENING_SCENARIOS)
    if unknown:
        raise ValueError(f"unknown device hardening scenario: {sorted(unknown)}")
    items = [
        supplied.get(
            scenario, DeviceHardeningEvidenceItem(scenario_id=scenario, status="PENDING_EXTERNAL")
        )
        for scenario in DEVICE_HARDENING_SCENARIOS
    ]
    if any(item.status == "VERIFIED" for item in items) and evidence_input is None:
        raise ValueError("verified evidence requires an audited input file")
    return DeviceHardeningEvidenceBundle(
        release_line=release_line,
        rolo_revision=rolo_revision,
        producer_revision=producer_revision(),
        target_id=target_id,
        target_kind=profile.target.kind,
        evidence=items,
    )


def build_release_ledger(bundle: DeviceHardeningEvidenceBundle) -> ReleaseLedger:
    entries = []
    for item in bundle.evidence:
        evidence = item.evidence
        entries.append(
            ReleaseLedgerEntry(
                release_line=bundle.release_line,
                rolo_revision=bundle.rolo_revision,
                producer_revision=bundle.producer_revision,
                target_id=bundle.target_id,
                target_kind=bundle.target_kind,
                scenario_id=item.scenario_id,
                status=item.status,
                job_id=evidence.job_id if evidence else None,
                package_digest=evidence.package_digest if evidence else None,
                gate_result=evidence.gate_result if evidence else None,
                observed_at=evidence.observed_at if evidence else None,
                limitations=[
                    "External device execution is required before VERIFIED.",
                    "Public bundle contains a bounded summary only.",
                ],
            )
        )
    return ReleaseLedger(entries=entries)


def write_device_hardening_bundle(
    bundle: DeviceHardeningEvidenceBundle,
    output: Path,
    *,
    ledger_output: Path | None = None,
) -> tuple[Path, Path | None]:
    if output.is_symlink() or (ledger_output is not None and ledger_output.is_symlink()):
        raise ValueError("device hardening output must not be a symlink")
    if ledger_output is not None and output.resolve() == ledger_output.resolve():
        raise ValueError("device hardening bundle and ledger outputs must differ")
    output.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(output, bundle.model_dump_json(indent=2) + "\n")
    ledger_path = None
    if ledger_output is not None:
        ledger = build_release_ledger(bundle)
        ledger_output.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(ledger_output, ledger.model_dump_json(indent=2) + "\n")
        ledger_path = ledger_output
    return output, ledger_path
