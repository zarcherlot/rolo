from __future__ import annotations

import getpass
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path

import pytest

from rolo.core.artifacts import ArtifactStore
from rolo.core.hashing import canonical_json_sha256
from rolo.stages.real_target import SshTargetCommandRunner
from rolo.stages.verify.ssh_provenance import SshTargetProvenanceCollector
from rolo.target_ref import SshTargetRef
from rolo.targets.bootstrap import SubprocessBootstrapTransport
from rolo.targets.profiles import (
    CredentialReference,
    TargetProfileStore,
    known_hosts_fingerprints,
)

pytestmark = [
    pytest.mark.ssh,
    pytest.mark.skipif(
        os.environ.get("ROLO_RUN_SSH_PROFILE_E2E") != "1",
        reason="set ROLO_RUN_SSH_PROFILE_E2E=1 to run the real SSH profile test",
    ),
    pytest.mark.skipif(os.name == "nt", reason="the embedded sshd fixture requires POSIX"),
]


def _free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _wait_for_sshd(process: subprocess.Popen[str], port: int) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stderr = process.stderr.read() if process.stderr is not None else ""
            pytest.fail(f"test sshd exited before accepting connections: {stderr}")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    pytest.fail("test sshd did not start within ten seconds")


def test_real_sshd_uses_profile_pins_for_read_only_stage_transport(tmp_path: Path) -> None:
    sshd = shutil.which("sshd")
    ssh_keygen = shutil.which("ssh-keygen")
    if not sshd or not ssh_keygen:
        pytest.fail("sshd and ssh-keygen must be installed for the SSH profile integration test")

    client_key = tmp_path / "client_ed25519"
    host_key = tmp_path / "host_ed25519"
    subprocess.run(
        [ssh_keygen, "-q", "-t", "ed25519", "-N", "", "-f", str(client_key)],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [ssh_keygen, "-q", "-t", "ed25519", "-N", "", "-f", str(host_key)],
        check=True,
        capture_output=True,
        text=True,
    )
    client_key.chmod(0o600)
    host_key.chmod(0o600)
    authorized_keys = tmp_path / "authorized_keys"
    authorized_keys.write_text(client_key.with_suffix(".pub").read_text(encoding="utf-8"))
    authorized_keys.chmod(0o600)
    port = _free_port()
    username = getpass.getuser()
    workspace = tmp_path / "remote-workspace"
    workspace.mkdir()
    config_file = tmp_path / "sshd_config"
    config_file.write_text(
        "\n".join(
            [
                f"Port {port}",
                "ListenAddress 127.0.0.1",
                f"HostKey {host_key}",
                f"PidFile {tmp_path / 'sshd.pid'}",
                f"AuthorizedKeysFile {authorized_keys}",
                f"AllowUsers {username}",
                "PubkeyAuthentication yes",
                "PasswordAuthentication no",
                "KbdInteractiveAuthentication no",
                "UsePAM no",
                "StrictModes no",
                "UseDNS no",
                "PermitTTY no",
                "AllowTcpForwarding no",
                "X11Forwarding no",
                "LogLevel ERROR",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    process = subprocess.Popen(
        [sshd, "-D", "-e", "-f", str(config_file)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        _wait_for_sshd(process, port)
        host_public = host_key.with_suffix(".pub").read_text(encoding="utf-8").split()
        known_hosts = tmp_path / "known_hosts"
        known_hosts.write_text(
            f"[127.0.0.1]:{port} {host_public[0]} {host_public[1]}\n",
            encoding="utf-8",
        )
        target = SshTargetRef(
            host="127.0.0.1",
            user=username,
            port=port,
            workspace=workspace.as_posix(),
        )
        store = TargetProfileStore(tmp_path / "config")
        profile = store.create(
            robot_id="ssh-e2e",
            target=target,
            credential=CredentialReference(kind="ssh-agent", reference="ssh-agent:default"),
            known_hosts=known_hosts,
            ssh_identity_file=client_key,
        )
        profile = profile.model_copy(
            update={
                "host_key": profile.host_key.model_copy(
                    update={
                        "status": "APPROVED",
                        "fingerprint": next(iter(known_hosts_fingerprints(known_hosts, target))),
                        "decided_by": "integration-test",
                    }
                )
            }
        )
        store.save(profile)
        transport = SubprocessBootstrapTransport(
            target,
            known_hosts=profile.known_hosts,
            identity_file=profile.ssh_identity_file,
        )
        result = SshTargetCommandRunner(transport).run("linux.uname", {}, timeout_s=10)
        assert result["status"] == "READY"
        artifacts = ArtifactStore(tmp_path / "artifacts")
        _, binding_ref, _ = SshTargetProvenanceCollector(target, transport).collect(
            artifacts,
            robot_id="ssh-e2e",
            profile_sha256=canonical_json_sha256(profile.model_dump(mode="json")),
            known_hosts_sha256=profile.known_hosts_sha256,
            host_key_fingerprint=profile.host_key.fingerprint,
        )
        assert binding_ref.startswith("artifact://targets/ssh-e2e/bindings/ssh-")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
