from __future__ import annotations

import os
from pathlib import Path

import pytest

from rolo.targets.credentials import CredentialResolutionError, PinnedCredentialBroker
from rolo.targets.profiles import CredentialReference


def test_agent_reference_is_cross_platform_and_does_not_accept_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SSH_AUTH_SOCK", "agent-socket")
    broker = PinnedCredentialBroker()
    reference = CredentialReference(kind="ssh-agent", reference="ssh-agent:default")

    resolved = broker.resolve(reference)

    assert resolved.mode == "ssh-agent"
    assert resolved.identity_file is None
    with pytest.raises(CredentialResolutionError, match="must not be combined"):
        broker.resolve(reference, identity_file=Path("id_ed25519"))


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission checks do not apply on Windows")
def test_pinned_identity_requires_private_permissions(tmp_path: Path) -> None:
    identity = tmp_path / "id_ed25519"
    identity.write_text("key", encoding="utf-8")
    identity.chmod(0o644)
    broker = PinnedCredentialBroker()
    reference = CredentialReference(
        kind="platform-keychain", reference="platform-keychain:robot"
    )

    with pytest.raises(CredentialResolutionError, match="permissions"):
        broker.resolve(reference, identity_file=identity)

    identity.chmod(0o600)
    resolved = broker.resolve(reference, identity_file=identity)
    assert resolved.mode == "identity-file"
    assert resolved.identity_file == identity.resolve()
