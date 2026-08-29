"""Collect a canonical main-line target binding over a pinned SSH transport."""

from __future__ import annotations

import hashlib
import re
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from rolo.core.artifacts import ArtifactStore
from rolo.core.hashing import sha256_file
from rolo.stages.artifact_paths import ArtifactLayout
from rolo.stages.real_target import TargetBinding
from rolo.target_ref import SshTargetRef

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_INTS = re.compile(r"^(\d+)\s+(\d+)\s+(\d+)$")


class SshReadOnlyTransport(Protocol):
    target: SshTargetRef

    def execute(self, remote_argv: list[str], *, timeout_s: float): ...


class SshTargetProvenanceCollector:
    """Freeze remote identity facts without invoking a shell or mutating the host."""

    def __init__(self, target: SshTargetRef, transport: SshReadOnlyTransport) -> None:
        if transport.target != target:
            raise ValueError("SSH provenance transport target does not match target")
        self.target = target
        self.transport = transport

    def collect(
        self,
        artifacts: ArtifactStore,
        *,
        robot_id: str,
        profile_sha256: str,
        run_id: str | None = None,
        timeout_s: float = 30.0,
        clock: Callable[[], datetime] | None = None,
    ) -> tuple[TargetBinding, str, str]:
        if not _SHA256.fullmatch(profile_sha256):
            raise ValueError("profile digest must be a lowercase SHA256")
        if not 1.0 <= timeout_s <= 600.0:
            raise ValueError("SSH provenance timeout must be between 1 and 600 seconds")
        selected_run = run_id or f"ssh-provenance-{uuid4().hex}"
        stat = self._required(["stat", "-c", "%d %i %Z", str(self.target.workspace)], timeout_s)
        match = _INTS.fullmatch(stat)
        if match is None:
            raise ValueError("remote workspace stat has an invalid shape")
        device, inode, ctime_s = (int(value) for value in match.groups())
        machine_id = self._machine_id(timeout_s)
        os_user = self._required(["id", "-un"], timeout_s)
        os_uid_text = self._required(["id", "-u"], timeout_s)
        if not os_uid_text.isdecimal():
            raise ValueError("remote uid is not a decimal integer")
        ros_domain_id = self._optional(["printenv", "ROS_DOMAIN_ID"], timeout_s)
        rmw_implementation = self._optional(["printenv", "RMW_IMPLEMENTATION"], timeout_s)
        now = (clock or (lambda: datetime.now(timezone.utc)))().astimezone(timezone.utc)
        binding = TargetBinding(
            robot_id=robot_id,
            profile_sha256=profile_sha256,
            workspace=str(self.target.workspace),
            workspace_device=device,
            workspace_inode=inode,
            workspace_ctime_ns=ctime_s * 1_000_000_000,
            machine_id_sha256=hashlib.sha256(machine_id.encode("utf-8")).hexdigest(),
            os_user=os_user,
            os_uid=int(os_uid_text),
            ros_domain_id=ros_domain_id,
            rmw_implementation=rmw_implementation,
            captured_at=now,
        )
        path = artifacts.write_json(
            f"targets/{robot_id}/bindings/ssh-{selected_run}.json",
            binding.model_dump(mode="json"),
        )
        return binding, ArtifactLayout(artifacts.root).ref(path), sha256_file(path)

    def _machine_id(self, timeout_s: float) -> str:
        for candidate in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
            result = self.transport.execute(["cat", candidate], timeout_s=timeout_s)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        raise ValueError("remote machine-id is unavailable")

    def _optional(self, argv: list[str], timeout_s: float) -> str | None:
        result = self.transport.execute(argv, timeout_s=timeout_s)
        if result.returncode != 0:
            return None
        value = result.stdout.strip()
        return value or None

    def _required(self, argv: list[str], timeout_s: float) -> str:
        result = self.transport.execute(argv, timeout_s=timeout_s)
        if result.returncode != 0:
            raise ValueError(f"remote read-only identity command failed: {argv[0]}")
        value = result.stdout.strip()
        if not value:
            raise ValueError(f"remote read-only identity command returned no output: {argv[0]}")
        return value


__all__ = ["SshReadOnlyTransport", "SshTargetProvenanceCollector"]
