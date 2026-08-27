"""User-facing references to local and SSH robot workspaces."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Literal
from urllib.parse import unquote, urlsplit

from pydantic import BaseModel, field_validator

_SAFE_SSH_WORKSPACE = re.compile(r"/[A-Za-z0-9._~+@%/-]+")
_SAFE_SSH_HOST = re.compile(r"[A-Za-z0-9._:%-]+")
_SAFE_SSH_USER = re.compile(r"[A-Za-z0-9._-]+")


class LocalTargetRef(BaseModel):
    kind: Literal["local"] = "local"
    workspace: Path


class SshTargetRef(BaseModel):
    kind: Literal["ssh"] = "ssh"
    host: str
    workspace: PurePosixPath
    user: str | None = None
    port: int | None = None

    @field_validator("host")
    @classmethod
    def validate_host(cls, value: str) -> str:
        if not value or value.startswith("-") or not _SAFE_SSH_HOST.fullmatch(value):
            raise ValueError("SSH host contains unsupported characters")
        return value

    @field_validator("user")
    @classmethod
    def validate_user(cls, value: str | None) -> str | None:
        if value is not None and not _SAFE_SSH_USER.fullmatch(value):
            raise ValueError("SSH user contains unsupported characters")
        return value

    @field_validator("port")
    @classmethod
    def validate_port(cls, value: int | None) -> int | None:
        if value is not None and not 1 <= value <= 65535:
            raise ValueError("SSH port must be between 1 and 65535")
        return value

    @field_validator("workspace")
    @classmethod
    def validate_workspace(cls, value: PurePosixPath) -> PurePosixPath:
        text = str(value)
        if (
            not value.is_absolute()
            or value == PurePosixPath("/")
            or not _SAFE_SSH_WORKSPACE.fullmatch(text)
            or ".." in value.parts
        ):
            raise ValueError("SSH workspace path contains unsupported characters or traversal")
        return value


TargetRef = LocalTargetRef | SshTargetRef


def parse_target_ref(value: str, *, cwd: Path | None = None) -> TargetRef:
    """Parse a local workspace path or a credential-free ``ssh://`` target URI."""
    raw = value.strip()
    if not raw:
        raise ValueError("target workspace must not be empty")
    if not raw.casefold().startswith("ssh://"):
        if "://" in raw:
            raise ValueError("remote target must use an ssh:// URI")
        workspace = Path(raw).expanduser()
        if not workspace.is_absolute():
            workspace = (cwd or Path.cwd()) / workspace
        return LocalTargetRef(workspace=workspace.resolve())

    parsed = urlsplit(raw)
    if parsed.scheme.casefold() != "ssh":
        raise ValueError("remote target must use an ssh:// URI")
    if parsed.password is not None:
        raise ValueError("SSH target URI must not contain a password")
    if parsed.query or parsed.fragment:
        raise ValueError("SSH target URI must not contain query parameters or a fragment")
    if not parsed.hostname:
        raise ValueError("SSH target URI must include a host")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"invalid SSH target port: {exc}") from exc
    workspace_text = unquote(parsed.path)
    workspace = PurePosixPath(workspace_text)
    if not workspace_text or not workspace.is_absolute() or workspace == PurePosixPath("/"):
        raise ValueError("SSH target URI must include an absolute workspace path")
    return SshTargetRef(
        host=parsed.hostname,
        user=unquote(parsed.username) if parsed.username else None,
        port=port,
        workspace=workspace,
    )
