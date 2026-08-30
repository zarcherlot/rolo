"""Local user and session identity helpers for stage authorization.

The values returned here are non-secret binding material.  A session id is
persisted below the artifact root so CLI/API processes for the same local
Rolo installation agree on the authorization session without exposing a
credential or relying on a volatile process id.
"""

from __future__ import annotations

import getpass
import hashlib
import os
import re
from pathlib import Path
from uuid import uuid4

from rolo.core.persistence import atomic_write_text

_SESSION_PATTERN = re.compile(r"^session-[0-9a-f]{32}$")


def current_user_principal() -> str:
    """Return a stable, non-secret OS-user principal for this Rolo process."""

    principal = getpass.getuser().strip()
    if not principal or any(character.isspace() for character in principal):
        raise ValueError("current OS user principal is unavailable")
    return principal


def current_user_session_id(state_root: Path) -> str:
    """Return the durable local session id shared by same-user processes."""

    configured = os.environ.get("ROLO_SESSION_ID", "").strip()
    if configured:
        if not _SESSION_PATTERN.fullmatch(configured):
            raise ValueError("ROLO_SESSION_ID must match session-<32 hex characters>")
        return configured
    path = state_root.expanduser().resolve() / ".rolo-session-id"
    try:
        session_id = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        session_id = ""
    if session_id and _SESSION_PATTERN.fullmatch(session_id):
        return session_id
    candidate = f"session-{uuid4().hex}"
    try:
        atomic_write_text(path, candidate + "\n", require_absent=True)
    except FileExistsError:
        session_id = path.read_text(encoding="utf-8").strip()
        if _SESSION_PATTERN.fullmatch(session_id):
            return session_id
        raise ValueError("local Rolo session id is invalid") from None
    return candidate


def current_user_session_fingerprint(state_root: Path) -> str:
    """Return the SHA256 fingerprint persisted in StageActorIdentity.session_id."""

    return hashlib.sha256(current_user_session_id(state_root).encode("utf-8")).hexdigest()
