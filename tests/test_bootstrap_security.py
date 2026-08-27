import os

import pytest

from rolo.targets.security import validate_bootstrap_file, validate_bootstrap_security


def test_bootstrap_security_requires_non_empty_inputs(tmp_path):
    known_hosts = tmp_path / "known_hosts"
    key = tmp_path / "key"
    known_hosts.write_text("host ssh-ed25519 AAAA\n", encoding="utf-8")
    key.write_bytes(b"key")
    if os.name != "nt":
        key.chmod(0o600)
    assert validate_bootstrap_security(known_hosts, key) == (known_hosts.resolve(), key.resolve())


def test_bootstrap_security_rejects_empty_file(tmp_path):
    empty = tmp_path / "empty"
    empty.write_bytes(b"")
    with pytest.raises(ValueError, match="must not be empty"):
        validate_bootstrap_file(empty, label="known_hosts", max_mode=0o644)


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission checks do not apply on Windows")
def test_bootstrap_security_rejects_world_writable_key(tmp_path):
    key = tmp_path / "key"
    key.write_bytes(b"key")
    key.chmod(0o644)
    with pytest.raises(ValueError, match="permissions are too broad"):
        validate_bootstrap_file(key, label="verification key", max_mode=0o600)
