from __future__ import annotations

import csv
import getpass
import hashlib
import json
import os
import platform
import re
import shutil
import stat
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from rolo.core.hashing import sha256_file
from rolo.core.models import ToolDescriptor
from rolo.stages.artifact_paths import resolve_artifact_ref


class InvocationRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed_users: list[str] = Field(default_factory=list)
    allowed_groups: list[str] = Field(default_factory=list)


class WriteInvocationRule(InvocationRule):
    allowed_operations: list[str] = Field(default_factory=list)


class ContentResourceRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: str = Field(min_length=1)
    classification: Literal["SENSITIVE"]
    allowed_roots: list[str] = Field(default_factory=list)
    allowed_resources: list[str] = Field(default_factory=list)
    max_bytes: int = Field(gt=0, le=100_000_000)

    @model_validator(mode="after")
    def require_scope(self) -> ContentResourceRule:
        if not self.allowed_roots and not self.allowed_resources:
            raise ValueError("content resource rule requires roots or resource identities")
        return self


class InvocationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-invocation-policy/v1"] = "rolo-invocation-policy/v1"
    sensitive: InvocationRule = Field(default_factory=InvocationRule)
    writes: WriteInvocationRule = Field(default_factory=WriteInvocationRule)
    content_resources: list[ContentResourceRule] = Field(default_factory=list)


class R3AuthorizationCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-r3-authorization-capability/v1"]
    decision: Literal["ALLOW", "DENY"]
    authorization_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    robot_id: str = Field(min_length=1)
    operation: str = Field(min_length=1)
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expires_at: datetime


class R3AuthorizationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-r3-authorization-request/v1"]
    request_id: str = Field(min_length=1)
    observed_at: datetime
    principal: str = Field(min_length=1)
    robot_id: str = Field(min_length=1)
    operation: str = Field(min_length=1)
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ExecutionQuiescenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-execution-quiescence-request/v1"]
    request_id: str = Field(min_length=1)
    observed_at: datetime
    principal: str = Field(min_length=1)
    robot_id: str = Field(min_length=1)
    operation: str = Field(min_length=1)
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    requested_lease_s: float = Field(gt=0, le=120)


class ExecutionQuiescenceLease(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-execution-quiescence-lease/v1"]
    decision: Literal["ALLOW", "DENY"]
    lease_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    robot_id: str = Field(min_length=1)
    operation: str = Field(min_length=1)
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    scope: Literal["robot_execution"]
    state_revision: str = Field(min_length=1)
    quiescent_since: datetime
    expires_at: datetime


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _identity() -> tuple[str, set[str], set[str]]:
    user = getpass.getuser()
    user_aliases = {user}
    groups: set[str] = set()
    if os.name == "posix":
        try:
            import grp

            groups = {grp.getgrgid(group_id).gr_name for group_id in os.getgroups()}
        except (ImportError, KeyError, OSError):
            groups = set()
    elif platform.system() == "Windows":
        try:
            principal = subprocess.run(
                ["whoami.exe"],
                capture_output=True,
                check=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
            ).stdout.strip()
            if principal:
                user_aliases.add(principal)
            group_output = subprocess.run(
                ["whoami.exe", "/groups", "/fo", "csv", "/nh"],
                capture_output=True,
                check=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
            ).stdout.splitlines()
            for row in csv.reader(group_output):
                if row:
                    groups.add(row[0])
                if len(row) > 2:
                    groups.add(row[2])
        except (OSError, subprocess.SubprocessError):
            groups = set()
    return user, user_aliases, groups


def _powershell() -> str | None:
    return shutil.which("pwsh.exe") or shutil.which("powershell.exe")


def _windows_policy_is_protected(path: Path) -> bool:
    escaped = str(path).replace("'", "''")
    script = (
        f"(Get-Acl -LiteralPath '{escaped}').Access | ForEach-Object {{ "
        "$sid=$_.IdentityReference.Translate("
        "[System.Security.Principal.SecurityIdentifier]).Value; "
        "[PSCustomObject]@{Sid=$sid;Rights=$_.FileSystemRights.ToString();"
        "Type=$_.AccessControlType.ToString()} } | ConvertTo-Json -Compress"
    )
    powershell = _powershell()
    if powershell is None:
        return False
    completed = subprocess.run(
        [powershell, "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=5,
    )
    if completed.returncode != 0:
        return False
    try:
        entries = json.loads(completed.stdout or "[]")
    except json.JSONDecodeError:
        return False
    if isinstance(entries, dict):
        entries = [entries]
    if not isinstance(entries, list):
        return False
    broad_sids = {"S-1-1-0", "S-1-5-11", "S-1-5-32-545"}
    write_rights = {
        "AppendData",
        "ChangePermissions",
        "CreateDirectories",
        "CreateFiles",
        "Delete",
        "DeleteSubdirectoriesAndFiles",
        "FullControl",
        "Modify",
        "TakeOwnership",
        "Write",
        "WriteAttributes",
        "WriteData",
        "WriteExtendedAttributes",
    }
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("Type") != "Allow":
            continue
        rights = {value.strip() for value in str(entry.get("Rights", "")).split(",")}
        if entry.get("Sid") in broad_sids and rights & write_rights:
            return False
    return True


def _windows_owner_is_admin(path: Path) -> bool:
    powershell = _powershell()
    if powershell is None:
        return False
    escaped = str(path).replace("'", "''")
    script = (
        f"$acl=Get-Acl -LiteralPath '{escaped}'; "
        "$acl.Owner | ForEach-Object { "
        "([System.Security.Principal.NTAccount]$_).Translate("
        "[System.Security.Principal.SecurityIdentifier]).Value }"
    )
    completed = subprocess.run(
        [powershell, "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=5,
    )
    return completed.returncode == 0 and completed.stdout.strip() in {
        "S-1-5-18",
        "S-1-5-32-544",
    }


def validate_protected_file(
    path: Path, *, label: str, require_admin_owner: bool = False
) -> Path:
    expanded = path.expanduser().absolute()
    if expanded.is_symlink() or not expanded.is_file():
        raise ValueError(f"{label} is missing or is not a regular file")
    metadata = expanded.stat()
    if os.name == "posix":
        trusted_owners = {0} if require_admin_owner else {0, os.geteuid()}
        if metadata.st_uid not in trusted_owners:
            raise ValueError(f"{label} has an untrusted owner")
        if stat.S_IMODE(metadata.st_mode) & 0o022:
            raise ValueError(f"{label} is writable by group or other users")
    elif platform.system() == "Windows":
        if not _windows_policy_is_protected(expanded):
            raise ValueError(f"{label} ACL permits untrusted modification")
        if require_admin_owner and not _windows_owner_is_admin(expanded):
            raise ValueError(f"{label} must be owned by Administrators or SYSTEM")
    return expanded


def validate_policy_file(path: Path) -> Path:
    return validate_protected_file(path, label="invocation policy")


def load_invocation_policy(path: Path) -> InvocationPolicy:
    protected = validate_policy_file(path)
    payload = yaml.safe_load(protected.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("invocation policy must be a YAML object")
    return InvocationPolicy.model_validate(payload)


def _write_audit(
    audit_path: Path,
    *,
    robot_id: str,
    operation: str,
    classification: str,
    policy_domain: Literal["data", "content", "write", "r3", "quiescence"],
    user: str,
    outcome: str,
    reason: str,
    authorization_id: str | None = None,
    lease_id: str | None = None,
) -> None:
    try:
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "schema_version": "rolo-invocation-audit/v1",
            "observed_at": _now(),
            "robot_id": robot_id,
            "operation": operation,
            "data_classification": classification,
            "policy_domain": policy_domain,
            "principal": user,
            "outcome": outcome,
            "reason": reason,
        }
        if authorization_id is not None:
            record["authorization_id"] = authorization_id
        if lease_id is not None:
            record["lease_id"] = lease_id
        with audit_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            stream.write("\n")
    except OSError as exc:
        raise ValueError(f"invocation audit failed: {exc}") from exc


def authorize_invocation(
    descriptor: ToolDescriptor,
    *,
    robot_id: str,
    policy_path: Path | None,
    audit_path: Path | None,
    payload: dict[str, object],
    r3_authorizer_path: Path | None,
    quiescence_provider_path: Path | None = None,
    required_quiescence_s: float = 30.0,
) -> None:
    authorize_data_access(
        descriptor.data_classification,
        robot_id=robot_id,
        operation=descriptor.operation,
        policy_path=policy_path,
        audit_path=audit_path,
    )
    authorize_content_resource(
        descriptor,
        robot_id=robot_id,
        payload=payload,
        policy_path=policy_path,
        audit_path=audit_path,
    )
    if descriptor.access == "write":
        authorize_write_access(
            descriptor,
            robot_id=robot_id,
            payload=payload,
            policy_path=policy_path,
            audit_path=audit_path,
            r3_authorizer_path=r3_authorizer_path,
        )
    authorize_execution_quiescence(
        descriptor,
        robot_id=robot_id,
        payload=payload,
        audit_path=audit_path,
        provider_path=quiescence_provider_path,
        required_lease_s=required_quiescence_s,
    )


def authorize_data_access(
    classification: str | None,
    *,
    robot_id: str,
    operation: str,
    policy_path: Path | None,
    audit_path: Path | None,
) -> None:
    if classification is None:
        raise ValueError("operation lacks data classification and is denied")
    if classification == "SECRET":
        raise ValueError("SECRET operations are prohibited by the generic runtime")
    if classification != "SENSITIVE":
        return
    user, user_aliases, groups = _identity()
    outcome = "DENIED"
    reason = "SENSITIVE invocation policy is missing"
    try:
        if policy_path is None:
            raise ValueError(reason)
        policy = load_invocation_policy(policy_path)
        allowed_users = {value.casefold() for value in policy.sensitive.allowed_users}
        allowed_groups = {value.casefold() for value in policy.sensitive.allowed_groups}
        authorized = bool(
            {value.casefold() for value in user_aliases} & allowed_users
        ) or bool(
            {value.casefold() for value in groups} & allowed_groups
        )
        if not authorized:
            reason = "host principal is not authorized for SENSITIVE operations"
            raise ValueError(reason)
        outcome = "ALLOWED"
        reason = "host principal matched protected invocation policy"
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        reason = str(exc)
        if audit_path is not None:
            _write_audit(
                audit_path,
                robot_id=robot_id,
                operation=operation,
                classification=classification,
                policy_domain="data",
                user=user,
                outcome=outcome,
                reason=reason,
            )
        raise ValueError(reason) from exc
    if audit_path is None:
        raise ValueError("SENSITIVE invocation requires an audit log path")
    _write_audit(
        audit_path,
        robot_id=robot_id,
        operation=operation,
        classification=classification,
        policy_domain="data",
        user=user,
        outcome=outcome,
        reason=reason,
    )


def _principal_is_allowed(
    rule: InvocationRule, user_aliases: set[str], groups: set[str]
) -> bool:
    allowed_users = {value.casefold() for value in rule.allowed_users}
    allowed_groups = {value.casefold() for value in rule.allowed_groups}
    return bool({value.casefold() for value in user_aliases} & allowed_users) or bool(
        {value.casefold() for value in groups} & allowed_groups
    )


def _payload_sha256(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


_CONTENT_OPERATIONS = {
    "linux.file.read",
    "linux.config.inspect",
    "linux.config.validate",
    "linux.config.diff",
    "linux.process.logs",
    "linux.service.logs",
    "linux.container.logs",
    "linux.log.query",
    "linux.log.follow",
}

_ROLLBACK_TOKEN_INPUT_OPERATIONS = {
    "linux.config.rollback",
    "app.parameter.rollback",
    "app.tuning.rollback",
}
_ROLLBACK_TOKEN_OUTPUT_OPERATIONS = {
    "linux.config.apply",
    "app.parameter.set",
    "app.tuning.commit",
}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _policy_relative_path(path: str, policy_path: Path) -> Path:
    candidate = Path(path).expanduser()
    return candidate if candidate.is_absolute() else policy_path.parent / candidate


def _path_is_allowed(path: str, roots: list[str], policy_path: Path) -> bool:
    candidate = _policy_relative_path(path, policy_path)
    if candidate.is_symlink() or not candidate.is_file():
        return False
    resolved = candidate.resolve()
    for value in roots:
        root_candidate = _policy_relative_path(value, policy_path)
        if root_candidate.is_symlink() or not root_candidate.is_dir():
            continue
        root = root_candidate.resolve()
        try:
            resolved.relative_to(root)
            relative = candidate.absolute().relative_to(root_candidate.absolute())
        except ValueError:
            continue
        cursor = root_candidate.absolute()
        contains_symlink = False
        for part in relative.parts:
            cursor /= part
            if cursor.is_symlink():
                contains_symlink = True
                break
        if contains_symlink:
            continue
        return True
    return False


def _content_rule_matches(
    rule: ContentResourceRule,
    *,
    payload: dict[str, object],
    policy_path: Path,
) -> bool:
    requested_bytes = payload.get("max_bytes")
    if not isinstance(requested_bytes, int) or isinstance(requested_bytes, bool):
        return False
    if requested_bytes <= 0 or requested_bytes > rule.max_bytes:
        return False
    paths = [
        value
        for name in ("path", "left_path", "right_path")
        if isinstance((value := payload.get(name)), str)
    ]
    if paths and (
        not rule.allowed_roots
        or not all(_path_is_allowed(path, rule.allowed_roots, policy_path) for path in paths)
    ):
        return False
    resource_id = payload.get("resource_id")
    if resource_id is not None and (
        not isinstance(resource_id, str) or resource_id not in rule.allowed_resources
    ):
        return False
    return bool(paths or resource_id is not None)


def authorize_content_resource(
    descriptor: ToolDescriptor,
    *,
    robot_id: str,
    payload: dict[str, object],
    policy_path: Path | None,
    audit_path: Path | None,
) -> None:
    if descriptor.operation not in _CONTENT_OPERATIONS:
        return
    if descriptor.data_classification != "SENSITIVE":
        raise ValueError("content resource operation must remain classified SENSITIVE")
    user, _, _ = _identity()
    if audit_path is None:
        raise ValueError("content resource invocation requires an audit log path")
    outcome = "DENIED"
    reason = "protected content resource policy is missing"
    try:
        if policy_path is None:
            raise ValueError(reason)
        policy = load_invocation_policy(policy_path)
        rules = [
            rule
            for rule in policy.content_resources
            if rule.operation == descriptor.operation
        ]
        if not rules:
            raise ValueError("content resource has no protected classification rule")
        if not any(
            _content_rule_matches(rule, payload=payload, policy_path=policy_path)
            for rule in rules
        ):
            raise ValueError("content resource is outside protected scope or byte limits")
        outcome = "ALLOWED"
        reason = "content resource matched a protected SENSITIVE classification rule"
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        reason = str(exc)
        _write_audit(
            audit_path,
            robot_id=robot_id,
            operation=descriptor.operation,
            classification=descriptor.data_classification or "UNCLASSIFIED",
            policy_domain="content",
            user=user,
            outcome=outcome,
            reason=reason,
        )
        raise ValueError(reason) from exc
    _write_audit(
        audit_path,
        robot_id=robot_id,
        operation=descriptor.operation,
        classification=descriptor.data_classification or "UNCLASSIFIED",
        policy_domain="content",
        user=user,
        outcome=outcome,
        reason=reason,
    )


def validate_content_result(
    descriptor: ToolDescriptor,
    *,
    payload: dict[str, object],
    result: dict[str, object],
) -> None:
    if descriptor.operation not in _CONTENT_OPERATIONS:
        return
    if descriptor.operation == "linux.config.validate":
        return
    artifact_ref = result.get("artifact_ref")
    if not isinstance(artifact_ref, str) or not artifact_ref.startswith("artifact://"):
        raise ValueError("content operation must return a protected artifact:// reference")
    requested_bytes = payload.get("max_bytes")
    observed_bytes = result.get("bytes")
    if (
        not isinstance(requested_bytes, int)
        or isinstance(requested_bytes, bool)
        or not isinstance(observed_bytes, int)
        or isinstance(observed_bytes, bool)
        or observed_bytes < 0
        or observed_bytes > requested_bytes
    ):
        raise ValueError("content artifact exceeds the authorized byte limit")


def _validate_digest_pinned_artifact(
    payload: dict[str, object], *, artifact_root: Path | None, label: str
) -> None:
    reference = payload.get("artifact_ref")
    expected_sha256 = payload.get("artifact_sha256")
    max_bytes = payload.get("max_bytes")
    if not isinstance(reference, str) or not reference.startswith("artifact://"):
        raise ValueError(f"{label} requires an artifact:// reference")
    if not isinstance(expected_sha256, str) or not _SHA256.fullmatch(expected_sha256):
        raise ValueError(f"{label} requires a lowercase SHA-256 digest")
    if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes <= 0:
        raise ValueError(f"{label} requires a positive max_bytes bound")
    if artifact_root is None:
        raise ValueError(f"{label} requires the protected artifact root")
    relative = Path(reference.removeprefix("artifact://"))
    artifact = resolve_artifact_ref(artifact_root, reference)
    cursor = artifact_root
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"{label} artifact path must not contain symbolic links")
    if not artifact.is_file():
        raise ValueError(f"{label} artifact is missing or not a regular file")
    if artifact.stat().st_size > max_bytes:
        raise ValueError(f"{label} artifact exceeds the authorized byte limit")
    if sha256_file(artifact) != expected_sha256:
        raise ValueError(f"{label} artifact SHA-256 mismatch")


def validate_config_mutation_input(
    descriptor: ToolDescriptor,
    *,
    payload: dict[str, object],
    artifact_root: Path | None,
) -> None:
    if descriptor.operation in _ROLLBACK_TOKEN_INPUT_OPERATIONS:
        token = payload.get("rollback_token")
        if (
            not isinstance(token, str)
            or not token.startswith("rollback://")
            or len(token) <= len("rollback://")
        ):
            raise ValueError("rollback requires a system-issued rollback:// token")
        return
    if descriptor.operation != "linux.config.apply":
        return
    _validate_digest_pinned_artifact(
        payload,
        artifact_root=artifact_root,
        label="config apply",
    )


def validate_map_import_input(
    descriptor: ToolDescriptor,
    *,
    payload: dict[str, object],
    artifact_root: Path | None,
) -> None:
    if descriptor.operation != "app.map.import":
        return
    _validate_digest_pinned_artifact(
        payload,
        artifact_root=artifact_root,
        label="map import",
    )


def validate_tuning_candidate_input(
    descriptor: ToolDescriptor,
    *,
    payload: dict[str, object],
    artifact_root: Path | None,
) -> None:
    if descriptor.operation != "app.tuning.candidate.create":
        return
    _validate_digest_pinned_artifact(
        payload,
        artifact_root=artifact_root,
        label="tuning candidate",
    )


def validate_config_mutation_result(
    descriptor: ToolDescriptor, *, result: dict[str, object]
) -> None:
    if descriptor.operation not in _ROLLBACK_TOKEN_OUTPUT_OPERATIONS:
        return
    token = result.get("rollback_token")
    if (
        not isinstance(token, str)
        or not token.startswith("rollback://")
        or len(token) <= len("rollback://")
    ):
        raise ValueError("mutation must return a system-issued rollback:// token")


def _request_quiescence_lease(
    provider_path: Path,
    *,
    robot_id: str,
    operation: str,
    payload: dict[str, object],
    principal: str,
    required_lease_s: float,
) -> ExecutionQuiescenceLease:
    if required_lease_s <= 0 or required_lease_s > 120:
        raise ValueError("quiescence lease duration must be within 120 seconds")
    provider = validate_protected_file(
        provider_path,
        label="execution quiescence provider",
        require_admin_owner=True,
    )
    if os.name == "posix" and not os.access(provider, os.X_OK):
        raise ValueError("execution quiescence provider is not executable")
    request_id = str(uuid4())
    input_sha256 = _payload_sha256(payload)
    request = ExecutionQuiescenceRequest(
        schema_version="rolo-execution-quiescence-request/v1",
        request_id=request_id,
        observed_at=datetime.now(timezone.utc),
        principal=principal,
        robot_id=robot_id,
        operation=operation,
        input_sha256=input_sha256,
        requested_lease_s=required_lease_s,
    )
    completed = subprocess.run(
        [str(provider), "lease"],
        input=request.model_dump_json(),
        capture_output=True,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=5,
    )
    if completed.returncode != 0:
        raise ValueError("execution quiescence provider rejected or failed the request")
    try:
        lease = ExecutionQuiescenceLease.model_validate_json(completed.stdout)
    except ValueError as exc:
        raise ValueError("execution quiescence provider returned an invalid lease") from exc
    now = datetime.now(timezone.utc)
    if lease.expires_at.tzinfo is None or lease.quiescent_since.tzinfo is None:
        raise ValueError("execution quiescence timestamps must include a timezone")
    if lease.decision != "ALLOW":
        raise ValueError("execution quiescence provider denied the invocation")
    if (
        lease.request_id != request_id
        or lease.robot_id != robot_id
        or lease.operation != operation
        or lease.input_sha256 != input_sha256
    ):
        raise ValueError("execution quiescence lease is not bound to this invocation")
    lifetime_s = (lease.expires_at.astimezone(timezone.utc) - now).total_seconds()
    if lifetime_s < required_lease_s or lifetime_s > 120:
        raise ValueError("execution quiescence lease does not cover the invocation timeout")
    if lease.quiescent_since.astimezone(timezone.utc) > now:
        raise ValueError("execution quiescence lease has a future observation time")
    return lease


def authorize_execution_quiescence(
    descriptor: ToolDescriptor,
    *,
    robot_id: str,
    payload: dict[str, object],
    audit_path: Path | None,
    provider_path: Path | None,
    required_lease_s: float,
) -> None:
    if not descriptor.requires_quiescence:
        return
    if descriptor.access != "write" or descriptor.risk != "R2":
        raise ValueError("execution quiescence is only valid for R2 write operations")
    user, _, _ = _identity()
    if audit_path is None:
        raise ValueError("execution quiescence requires an audit log path")
    outcome = "DENIED"
    reason = "execution quiescence provider is missing"
    lease_id: str | None = None
    try:
        if provider_path is None:
            raise ValueError(reason)
        lease = _request_quiescence_lease(
            provider_path,
            robot_id=robot_id,
            operation=descriptor.operation,
            payload=payload,
            principal=user,
            required_lease_s=required_lease_s,
        )
        outcome = "ALLOWED"
        lease_id = lease.lease_id
        reason = "execution supervisor returned a bound quiescence lease"
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        reason = str(exc)
        _write_audit(
            audit_path,
            robot_id=robot_id,
            operation=descriptor.operation,
            classification=descriptor.data_classification or "UNCLASSIFIED",
            policy_domain="quiescence",
            user=user,
            outcome=outcome,
            reason=reason,
        )
        raise ValueError(reason) from exc
    _write_audit(
        audit_path,
        robot_id=robot_id,
        operation=descriptor.operation,
        classification=descriptor.data_classification or "UNCLASSIFIED",
        policy_domain="quiescence",
        user=user,
        outcome=outcome,
        reason=reason,
        lease_id=lease_id,
    )


def _request_r3_authorization(
    authorizer_path: Path,
    *,
    robot_id: str,
    operation: str,
    payload: dict[str, object],
    principal: str,
) -> R3AuthorizationCapability:
    authorizer = validate_protected_file(
        authorizer_path,
        label="R3 authorization provider",
        require_admin_owner=True,
    )
    if os.name == "posix" and not os.access(authorizer, os.X_OK):
        raise ValueError("R3 authorization provider is not executable")
    request_id = str(uuid4())
    input_sha256 = _payload_sha256(payload)
    request = R3AuthorizationRequest(
        schema_version="rolo-r3-authorization-request/v1",
        request_id=request_id,
        observed_at=datetime.now(timezone.utc),
        principal=principal,
        robot_id=robot_id,
        operation=operation,
        input_sha256=input_sha256,
    )
    completed = subprocess.run(
        [str(authorizer), "authorize"],
        input=request.model_dump_json(),
        capture_output=True,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=5,
    )
    if completed.returncode != 0:
        raise ValueError("R3 authorization provider rejected or failed the request")
    try:
        capability = R3AuthorizationCapability.model_validate_json(completed.stdout)
    except ValueError as exc:
        raise ValueError("R3 authorization provider returned an invalid capability") from exc
    now = datetime.now(timezone.utc)
    expires_at = capability.expires_at
    if expires_at.tzinfo is None:
        raise ValueError("R3 authorization capability expiry must include a timezone")
    if capability.decision != "ALLOW":
        raise ValueError("R3 authorization provider denied the invocation")
    if (
        capability.request_id != request_id
        or capability.robot_id != robot_id
        or capability.operation != operation
        or capability.input_sha256 != input_sha256
    ):
        raise ValueError("R3 authorization capability is not bound to this invocation")
    lifetime_s = (expires_at.astimezone(timezone.utc) - now).total_seconds()
    if lifetime_s <= 0 or lifetime_s > 300:
        raise ValueError("R3 authorization capability is expired or exceeds five minutes")
    return capability


def authorize_write_access(
    descriptor: ToolDescriptor,
    *,
    robot_id: str,
    payload: dict[str, object],
    policy_path: Path | None,
    audit_path: Path | None,
    r3_authorizer_path: Path | None,
) -> None:
    user, user_aliases, groups = _identity()
    if audit_path is None:
        raise ValueError("write invocation requires an audit log path")
    if descriptor.risk == "R3":
        outcome = "DENIED"
        reason = "R3 authorization provider is missing"
        authorization_id: str | None = None
        try:
            if r3_authorizer_path is None:
                raise ValueError(reason)
            capability = _request_r3_authorization(
                r3_authorizer_path,
                robot_id=robot_id,
                operation=descriptor.operation,
                payload=payload,
                principal=user,
            )
            outcome = "ALLOWED"
            authorization_id = capability.authorization_id
            reason = "R3 provider returned a short-lived bound capability"
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            reason = str(exc)
            _write_audit(
                audit_path,
                robot_id=robot_id,
                operation=descriptor.operation,
                classification=descriptor.data_classification or "UNCLASSIFIED",
                policy_domain="r3",
                user=user,
                outcome=outcome,
                reason=reason,
            )
            raise ValueError(reason) from exc
        _write_audit(
            audit_path,
            robot_id=robot_id,
            operation=descriptor.operation,
            classification=descriptor.data_classification or "UNCLASSIFIED",
            policy_domain="r3",
            user=user,
            outcome=outcome,
            reason=reason,
            authorization_id=authorization_id,
        )
        return

    outcome = "DENIED"
    reason = "write invocation policy is missing"
    try:
        if policy_path is None:
            raise ValueError(reason)
        policy = load_invocation_policy(policy_path)
        if not _principal_is_allowed(policy.writes, user_aliases, groups):
            raise ValueError("host principal is not authorized for write operations")
        if descriptor.operation not in policy.writes.allowed_operations:
            raise ValueError("write operation is not present in the protected allowlist")
        outcome = "ALLOWED"
        reason = "host principal and operation matched protected write policy"
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        reason = str(exc)
        _write_audit(
            audit_path,
            robot_id=robot_id,
            operation=descriptor.operation,
            classification=descriptor.data_classification or "UNCLASSIFIED",
            policy_domain="write",
            user=user,
            outcome=outcome,
            reason=reason,
        )
        raise ValueError(reason) from exc
    _write_audit(
        audit_path,
        robot_id=robot_id,
        operation=descriptor.operation,
        classification=descriptor.data_classification or "UNCLASSIFIED",
        policy_domain="write",
        user=user,
        outcome=outcome,
        reason=reason,
    )
