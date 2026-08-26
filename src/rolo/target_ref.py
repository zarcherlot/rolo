"""User-facing references to local and SSH robot workspaces."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Literal
from urllib.parse import unquote, urlsplit

from pydantic import BaseModel


class LocalTargetRef(BaseModel):
    kind: Literal["local"] = "local"
    workspace: Path


class SshTargetRef(BaseModel):
    kind: Literal["ssh"] = "ssh"
    host: str
    workspace: PurePosixPath
    user: str | None = None
    port: int | None = None


TargetRef = LocalTargetRef | SshTargetRef


def parse_target_ref(value: str, *, cwd: Path | None = None) -> TargetRef:
    """Parse a local workspace path or a credential-free ``ssh://`` target URI."""
    raw = value.strip()
    if not raw:
        raise ValueError("target workspace must not be empty")
    if not raw.casefold().startswith("ssh://"):
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
