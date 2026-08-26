from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Protocol
from urllib.parse import unquote, urlsplit

from rolo.targets.models import validate_credential_reference


class CredentialPurpose(str, Enum):
    SSH_PROVISIONING = "SSH_PROVISIONING"
    SSH_BOOTSTRAP = "SSH_BOOTSTRAP"
    SSH_RUNTIME = "SSH_RUNTIME"
    SSH_CA = "SSH_CA"
    LEGACY_COLLECTOR_VERIFICATION = "LEGACY_COLLECTOR_VERIFICATION"


@dataclass(frozen=True)
class ResolvedCredential:
    """Executor-only material. Its representations are deliberately always redacted."""

    reference: str
    purpose: CredentialPurpose
    secret_path: Path | None = field(default=None, repr=False)
    secret_text: str | None = field(default=None, repr=False)

    def __repr__(self) -> str:
        return (
            "ResolvedCredential(reference="
            f"{self.reference!r}, purpose={self.purpose.value!r}, material='<redacted>')"
        )

    def __str__(self) -> str:
        return f"{self.reference} (<redacted>)"


class CredentialProvider(Protocol):
    @property
    def schemes(self) -> frozenset[str]: ...

    def resolve(
        self,
        reference: str,
        *,
        purpose: CredentialPurpose,
    ) -> ResolvedCredential: ...


class CredentialResolver:
    """Route opaque references to providers without exposing provider material to callers."""

    def __init__(self, providers: tuple[CredentialProvider, ...] = ()) -> None:
        self._providers: dict[str, CredentialProvider] = {}
        for provider in providers:
            self.register(provider)

    def register(self, provider: CredentialProvider) -> None:
        for scheme in provider.schemes:
            if scheme in self._providers:
                raise ValueError(f"credential provider scheme already registered: {scheme}")
            self._providers[scheme] = provider

    def resolve(
        self,
        reference: str,
        *,
        purpose: CredentialPurpose,
    ) -> ResolvedCredential:
        reference = validate_credential_reference(reference)
        scheme = urlsplit(reference).scheme
        try:
            provider = self._providers[scheme]
        except KeyError as exc:
            raise ValueError(f"no credential provider registered for scheme: {scheme}") from exc
        credential = provider.resolve(reference, purpose=purpose)
        if credential.reference != reference or credential.purpose != purpose:
            raise ValueError(
                "credential provider returned material for a different reference or purpose"
            )
        return credential


class FileCredentialProvider:
    """Compatibility provider for an explicitly referenced local secret file."""

    schemes = frozenset({"file-credential"})

    def resolve(
        self,
        reference: str,
        *,
        purpose: CredentialPurpose,
    ) -> ResolvedCredential:
        parsed = urlsplit(validate_credential_reference(reference))
        if parsed.netloc not in {"", "localhost"}:
            raise ValueError("file-credential references must be local")
        raw_path = unquote(parsed.path)
        if len(raw_path) >= 3 and raw_path[0] == "/" and raw_path[2] == ":":
            raw_path = raw_path[1:]
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            raise ValueError("file-credential reference must identify an absolute path")
        return ResolvedCredential(reference=reference, purpose=purpose, secret_path=path)


def file_credential_reference(path: Path) -> str:
    resolved = path.expanduser().resolve()
    normalized = resolved.as_posix()
    if len(normalized) >= 2 and normalized[1] == ":":
        normalized = f"/{normalized}"
    return validate_credential_reference(f"file-credential://{normalized}")


def file_credential_path(reference: str) -> Path:
    credential = FileCredentialProvider().resolve(
        reference,
        purpose=CredentialPurpose.LEGACY_COLLECTOR_VERIFICATION,
    )
    if credential.secret_path is None:
        raise ValueError("file credential provider did not return a path")
    return credential.secret_path
