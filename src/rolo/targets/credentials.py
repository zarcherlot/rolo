"""Cross-platform, non-secret SSH credential resolution."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from rolo.targets.profiles import CredentialReference


class CredentialResolutionError(ValueError):
    """A typed credential reference cannot be resolved safely."""


@dataclass(frozen=True)
class ResolvedCredential:
    """Redacted transport intent; no secret material is retained."""

    reference: str
    mode: Literal["ssh-agent", "identity-file"]
    identity_file: Path | None = None


class CredentialBroker(Protocol):
    def resolve(
        self,
        reference: CredentialReference,
        *,
        identity_file: Path | None = None,
    ) -> ResolvedCredential: ...


class PinnedCredentialBroker:
    """Resolve portable Rolo enrollment credentials on any controller OS.

    ``ssh-agent`` references resolve to agent transport and do not inspect or
    export agent keys. Keychain/secret-store references require the
    installation-resolved pinned identity path supplied by the caller.
    """

    def resolve(
        self,
        reference: CredentialReference,
        *,
        identity_file: Path | None = None,
    ) -> ResolvedCredential:
        if reference.kind == "ssh-agent":
            if identity_file is not None:
                raise CredentialResolutionError(
                    "ssh-agent credentials must not be combined with an identity file"
                )
            if os.name != "nt" and not os.environ.get("SSH_AUTH_SOCK"):
                raise CredentialResolutionError(
                    "SSH_AUTH_SOCK is unavailable for the configured ssh-agent reference"
                )
            return ResolvedCredential(reference=reference.reference, mode="ssh-agent")

        if identity_file is None:
            raise CredentialResolutionError(
                f"{reference.kind} reference requires an installation-resolved identity file"
            )
        path = identity_file.expanduser().resolve()
        if not path.is_file() or path.is_symlink():
            raise CredentialResolutionError("pinned SSH identity file is unavailable")
        if os.name != "nt" and stat.S_IMODE(path.stat().st_mode) & 0o077:
            raise CredentialResolutionError(
                "pinned SSH identity permissions allow group or other access"
            )
        return ResolvedCredential(
            reference=reference.reference,
            mode="identity-file",
            identity_file=path,
        )
