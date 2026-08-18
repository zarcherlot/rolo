"""Bounded, chunked, read-only host package inventory collection."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import selectors
import signal
import subprocess
import time
from collections import Counter
from collections.abc import Iterable, Iterator
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from rolo.core.config import load_yaml


class CollectorStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_PROBED = "NOT_PROBED"
    BLOCKED_BY_POLICY = "BLOCKED_BY_POLICY"


class SoftwareInventoryPolicy(BaseModel):
    """Effective limits for package collection, separate from general discovery limits."""

    model_config = ConfigDict(extra="forbid")

    collector_timeout_s: float = Field(default=30.0, gt=0)
    max_raw_bytes_per_collector: int = Field(default=50 * 1024 * 1024, gt=0)
    max_record_bytes: int = Field(default=64 * 1024, gt=0)
    records_per_chunk: int = Field(default=1_000, gt=0)
    bytes_per_chunk: int = Field(default=2 * 1024 * 1024, gt=0)

    def sha256(self) -> str:
        encoded = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class PackageRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-software-package/v1"] = "robot-software-package/v1"
    package_id: str
    name: str
    version: str | None = None
    architecture: str | None = None
    status: str
    manager: str
    origin: str | None = None
    install_root: str | None = None
    collector: str
    collector_provenance: str
    collected_at: datetime

    def canonical_content_bytes(self) -> bytes:
        """Return stable content bytes, excluding volatile collection time."""
        content = self.model_dump(mode="json", exclude={"collected_at"})
        return (
            json.dumps(
                content,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            + b"\n"
        )


class InventoryChunk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence: int = Field(ge=1)
    artifact_ref: str
    record_count: int = Field(ge=0)
    byte_count: int = Field(ge=0)
    sha256: str
    first_package_id: str | None = None
    last_package_id: str | None = None


class PackageCollectorState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    collector: str
    status: CollectorStatus
    record_count: int = Field(ge=0)
    complete: bool
    truncated: bool
    reason: str | None = None
    limit_name: str | None = None
    raw_bytes: int = Field(default=0, ge=0)
    malformed_records: int = Field(default=0, ge=0)
    duration_s: float = Field(default=0.0, ge=0)


class PackageInventoryIndex(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-software-inventory-index/v1"] = (
        "robot-software-inventory-index/v1"
    )
    discovery_id: str
    inventory_sha256: str
    policy_sha256: str
    record_count: int = Field(ge=0)
    complete: bool
    counts_by_manager: dict[str, int] = Field(default_factory=dict)
    counts_by_architecture: dict[str, int] = Field(default_factory=dict)
    counts_by_status: dict[str, int] = Field(default_factory=dict)
    collectors: list[PackageCollectorState]
    chunks: list[InventoryChunk] = Field(default_factory=list)
    created_at: datetime


class SoftwareSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-software-summary/v1"] = "robot-software-summary/v1"
    discovery_id: str
    status: CollectorStatus
    complete: bool
    package_count: int = Field(ge=0)
    inventory_sha256: str
    policy_sha256: str
    package_inventory_ref: str
    counts_by_manager: dict[str, int] = Field(default_factory=dict)
    counts_by_architecture: dict[str, int] = Field(default_factory=dict)
    counts_by_status: dict[str, int] = Field(default_factory=dict)
    relevance_resolution_status: str = "PENDING"
    warnings: list[str] = Field(default_factory=list)

    @classmethod
    def from_index(cls, index: PackageInventoryIndex, inventory_ref: str) -> SoftwareSummary:
        states = index.collectors
        warnings = [
            f"{state.collector} inventory is incomplete: {state.reason or state.status.value}"
            for state in states
            if not state.complete
        ]
        if states and all(state.status == CollectorStatus.NOT_APPLICABLE for state in states):
            status = CollectorStatus.NOT_APPLICABLE
        elif index.complete:
            status = CollectorStatus.SUCCEEDED
        elif any(state.status == CollectorStatus.PARTIAL for state in states) or index.record_count:
            status = CollectorStatus.PARTIAL
        elif any(state.status == CollectorStatus.FAILED for state in states):
            status = CollectorStatus.FAILED
        elif any(state.status == CollectorStatus.BLOCKED_BY_POLICY for state in states):
            status = CollectorStatus.BLOCKED_BY_POLICY
        elif any(state.status == CollectorStatus.NOT_PROBED for state in states):
            status = CollectorStatus.NOT_PROBED
        else:
            status = CollectorStatus.UNAVAILABLE
        return cls(
            discovery_id=index.discovery_id,
            status=status,
            complete=index.complete,
            package_count=index.record_count,
            inventory_sha256=index.inventory_sha256,
            policy_sha256=index.policy_sha256,
            package_inventory_ref=inventory_ref,
            counts_by_manager=index.counts_by_manager,
            counts_by_architecture=index.counts_by_architecture,
            counts_by_status=index.counts_by_status,
            warnings=warnings,
        )


def empty_inventory_index(
    *,
    discovery_id: str,
    policy: SoftwareInventoryPolicy,
    created_at: datetime,
    status: CollectorStatus,
    reason: str,
) -> PackageInventoryIndex:
    empty_sha256 = hashlib.sha256().hexdigest()
    state = PackageCollectorState(
        collector="linux.dpkg",
        status=status,
        record_count=0,
        complete=False,
        truncated=False,
        reason=reason,
    )
    return PackageInventoryIndex(
        discovery_id=discovery_id,
        inventory_sha256=empty_sha256,
        policy_sha256=policy.sha256(),
        record_count=0,
        complete=False,
        collectors=[state],
        created_at=created_at,
    )


class _CollectionStopped(RuntimeError):
    def __init__(self, *, reason: str, limit_name: str | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.limit_name = limit_name


class _ChunkWriter:
    def __init__(
        self,
        *,
        output_dir: Path,
        artifact_prefix: str,
        policy: SoftwareInventoryPolicy,
    ) -> None:
        self.output_dir = output_dir
        self.artifact_prefix = artifact_prefix.rstrip("/")
        self.policy = policy
        self.chunks: list[InventoryChunk] = []
        self.record_count = 0
        self.counts_by_manager: Counter[str] = Counter()
        self.counts_by_architecture: Counter[str] = Counter()
        self.counts_by_status: Counter[str] = Counter()
        self._record_digests: list[bytes] = []
        self._stream: Any = None
        self._temporary_path: Path | None = None
        self._final_path: Path | None = None
        self._chunk_digest: Any = None
        self._chunk_records = 0
        self._chunk_bytes = 0
        self._first_package_id: str | None = None
        self._last_package_id: str | None = None

    def _open_chunk(self) -> None:
        sequence = len(self.chunks) + 1
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._final_path = self.output_dir / f"dpkg-{sequence:04d}.jsonl"
        self._temporary_path = self._final_path.with_suffix(".jsonl.tmp")
        self._stream = self._temporary_path.open("wb")
        self._chunk_digest = hashlib.sha256()
        self._chunk_records = 0
        self._chunk_bytes = 0
        self._first_package_id = None
        self._last_package_id = None

    def add(self, record: PackageRecord) -> None:
        encoded = (
            json.dumps(
                record.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            + b"\n"
        )
        rollover = self._stream is not None and (
            self._chunk_records >= self.policy.records_per_chunk
            or self._chunk_bytes + len(encoded) > self.policy.bytes_per_chunk
        )
        if rollover:
            self.close_chunk()
        if self._stream is None:
            self._open_chunk()
        self._stream.write(encoded)
        self._chunk_digest.update(encoded)
        self._chunk_records += 1
        self._chunk_bytes += len(encoded)
        self._first_package_id = self._first_package_id or record.package_id
        self._last_package_id = record.package_id
        self.record_count += 1
        self.counts_by_manager[record.manager] += 1
        self.counts_by_architecture[record.architecture or "unknown"] += 1
        self.counts_by_status[record.status] += 1
        self._record_digests.append(hashlib.sha256(record.canonical_content_bytes()).digest())

    def inventory_sha256(self) -> str:
        digest = hashlib.sha256()
        for record_digest in sorted(self._record_digests):
            digest.update(record_digest)
        return digest.hexdigest()

    def close_chunk(self) -> None:
        if self._stream is None:
            return
        self._stream.flush()
        os.fsync(self._stream.fileno())
        self._stream.close()
        assert self._temporary_path is not None
        assert self._final_path is not None
        self._temporary_path.replace(self._final_path)
        sequence = len(self.chunks) + 1
        self.chunks.append(
            InventoryChunk(
                sequence=sequence,
                artifact_ref=f"{self.artifact_prefix}/{self._final_path.name}",
                record_count=self._chunk_records,
                byte_count=self._chunk_bytes,
                sha256=self._chunk_digest.hexdigest(),
                first_package_id=self._first_package_id,
                last_package_id=self._last_package_id,
            )
        )
        self._stream = None
        self._temporary_path = None
        self._final_path = None

    def finish(self) -> None:
        self.close_chunk()


def load_software_inventory_policy(path: Path | None) -> SoftwareInventoryPolicy:
    if path is None or not path.is_file():
        return SoftwareInventoryPolicy()
    document = load_yaml(path)
    raw_policy = document.get("software_inventory", {})
    if not isinstance(raw_policy, dict):
        raise ValueError(f"software_inventory must be an object in {path}")
    return SoftwareInventoryPolicy.model_validate(raw_policy)


class DpkgPackageCollector:
    """Collect dpkg metadata without executing package-owned binaries or maintainer scripts."""

    collector_name = "linux.dpkg"

    def __init__(self, policy: SoftwareInventoryPolicy | None = None) -> None:
        self.policy = policy or SoftwareInventoryPolicy()

    @staticmethod
    def _trusted_executable() -> Path | None:
        for candidate in (Path("/usr/bin/dpkg-query"), Path("/bin/dpkg-query")):
            if candidate.is_file():
                resolved = candidate.resolve()
                if resolved == Path("/usr/bin/dpkg-query"):
                    return resolved
        return None

    @staticmethod
    def _parse_line(line: bytes, collected_at: datetime) -> PackageRecord:
        text = line.decode("utf-8", errors="replace").rstrip("\r\n")
        fields = text.split("\t")
        if len(fields) != 4 or not fields[0]:
            raise ValueError("dpkg-query emitted a malformed package record")
        binary_name, version, architecture, status_abbrev = fields
        architecture = architecture or "unknown"
        suffix = f":{architecture}"
        name = binary_name[: -len(suffix)] if binary_name.endswith(suffix) else binary_name
        normalized_status = "installed" if status_abbrev[:2] == "ii" else status_abbrev.strip()
        return PackageRecord(
            package_id=f"dpkg:{architecture}:{name}",
            name=name,
            version=version or None,
            architecture=architecture,
            status=normalized_status or "unknown",
            manager="dpkg",
            origin=None,
            install_root=None,
            collector=DpkgPackageCollector.collector_name,
            collector_provenance="dpkg-query",
            collected_at=collected_at,
        )

    @staticmethod
    def _terminate(process: subprocess.Popen[bytes]) -> None:
        if process.poll() is not None:
            return
        try:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGTERM)
            else:
                process.terminate()
            process.wait(timeout=1)
        except (OSError, subprocess.TimeoutExpired):
            process.kill()
            process.wait(timeout=1)

    def _command_lines(self, executable: Path) -> Iterator[bytes]:
        command = [
            str(executable),
            "-W",
            "-f=${binary:Package}\t${Version}\t${Architecture}\t${db:Status-Abbrev}\n",
        ]
        environment = {
            "LANG": "C",
            "LC_ALL": "C",
            "PATH": "/usr/bin:/bin",
        }
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
            start_new_session=True,
        )
        assert process.stdout is not None
        assert process.stderr is not None
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        selector.register(process.stderr, selectors.EVENT_READ, "stderr")
        stdout_buffer = bytearray()
        stderr_buffer = bytearray()
        deadline = time.monotonic() + self.policy.collector_timeout_s
        try:
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise _CollectionStopped(
                        reason=(
                            f"dpkg-query exceeded {self.policy.collector_timeout_s:g} seconds"
                        ),
                        limit_name="collector_timeout_s",
                    )
                events = selector.select(timeout=min(remaining, 0.2))
                for key, _ in events:
                    chunk = os.read(key.fileobj.fileno(), 64 * 1024)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    if key.data == "stderr":
                        remaining_stderr = max(0, 20_000 - len(stderr_buffer))
                        stderr_buffer.extend(chunk[:remaining_stderr])
                        continue
                    stdout_buffer.extend(chunk)
                    while True:
                        newline = stdout_buffer.find(b"\n")
                        if newline < 0:
                            break
                        if newline + 1 > self.policy.max_record_bytes:
                            raise _CollectionStopped(
                                reason=(
                                    "dpkg-query emitted a record larger than "
                                    f"{self.policy.max_record_bytes} bytes"
                                ),
                                limit_name="max_record_bytes",
                            )
                        yield bytes(stdout_buffer[: newline + 1])
                        del stdout_buffer[: newline + 1]
                    if len(stdout_buffer) > self.policy.max_record_bytes:
                        raise _CollectionStopped(
                            reason=(
                                "dpkg-query emitted an unterminated record larger than "
                                f"{self.policy.max_record_bytes} bytes"
                            ),
                            limit_name="max_record_bytes",
                        )
            if stdout_buffer:
                if len(stdout_buffer) > self.policy.max_record_bytes:
                    raise _CollectionStopped(
                        reason=(
                            "dpkg-query emitted a record larger than "
                            f"{self.policy.max_record_bytes} bytes"
                        ),
                        limit_name="max_record_bytes",
                    )
                yield bytes(stdout_buffer)
            returncode = process.wait(timeout=1)
            if returncode != 0:
                detail = stderr_buffer.decode("utf-8", errors="replace").strip()
                raise _CollectionStopped(
                    reason=f"dpkg-query exited with {returncode}: {detail or 'no diagnostic'}"
                )
        finally:
            selector.close()
            self._terminate(process)

    def collect(
        self,
        *,
        output_dir: Path,
        artifact_prefix: str,
        discovery_id: str,
        collected_at: datetime | None = None,
        lines: Iterable[bytes] | None = None,
    ) -> PackageInventoryIndex:
        """Collect and chunk all records. ``lines`` is an offline test seam."""
        collected_at = collected_at or datetime.now(timezone.utc)
        started = time.monotonic()
        writer = _ChunkWriter(
            output_dir=output_dir,
            artifact_prefix=artifact_prefix,
            policy=self.policy,
        )
        raw_bytes = 0
        malformed_records = 0
        stopped: _CollectionStopped | None = None

        if lines is None and platform.system() != "Linux":
            state = PackageCollectorState(
                collector=self.collector_name,
                status=CollectorStatus.NOT_APPLICABLE,
                record_count=0,
                complete=True,
                truncated=False,
                reason="dpkg package database is not applicable on this host",
                duration_s=time.monotonic() - started,
            )
            return self._index(discovery_id, writer, state, collected_at)

        executable = self._trusted_executable() if lines is None else None
        if lines is None and executable is None:
            state = PackageCollectorState(
                collector=self.collector_name,
                status=CollectorStatus.UNAVAILABLE,
                record_count=0,
                complete=False,
                truncated=False,
                reason="trusted /usr/bin/dpkg-query was not found",
                duration_s=time.monotonic() - started,
            )
            return self._index(discovery_id, writer, state, collected_at)

        source = iter(lines) if lines is not None else self._command_lines(executable)
        try:
            for line in source:
                if len(line) > self.policy.max_record_bytes:
                    raise _CollectionStopped(
                        reason=(
                            "dpkg-query emitted a record larger than "
                            f"{self.policy.max_record_bytes} bytes"
                        ),
                        limit_name="max_record_bytes",
                    )
                if raw_bytes >= self.policy.max_raw_bytes_per_collector:
                    raise _CollectionStopped(
                        reason=(
                            "dpkg-query output exceeded "
                            f"{self.policy.max_raw_bytes_per_collector} bytes"
                        ),
                        limit_name="max_raw_bytes_per_collector",
                    )
                raw_bytes += len(line)
                try:
                    record = self._parse_line(line, collected_at)
                except ValueError:
                    malformed_records += 1
                    continue
                writer.add(record)
        except _CollectionStopped as exc:
            stopped = exc
        except (OSError, subprocess.SubprocessError) as exc:
            stopped = _CollectionStopped(reason=f"dpkg-query collection failed: {exc}")
        finally:
            close_source = getattr(source, "close", None)
            if close_source is not None:
                close_source()
            writer.finish()

        if stopped is not None:
            status = CollectorStatus.PARTIAL if writer.record_count else CollectorStatus.FAILED
            complete = False
            truncated = True
            reason = stopped.reason
            limit_name = stopped.limit_name
        elif malformed_records:
            status = CollectorStatus.PARTIAL
            complete = False
            truncated = True
            reason = f"{malformed_records} malformed dpkg records could not be normalized"
            limit_name = None
        else:
            status = CollectorStatus.SUCCEEDED
            complete = True
            truncated = False
            reason = None
            limit_name = None
        state = PackageCollectorState(
            collector=self.collector_name,
            status=status,
            record_count=writer.record_count,
            complete=complete,
            truncated=truncated,
            reason=reason,
            limit_name=limit_name,
            raw_bytes=raw_bytes,
            malformed_records=malformed_records,
            duration_s=time.monotonic() - started,
        )
        return self._index(discovery_id, writer, state, collected_at)

    def _index(
        self,
        discovery_id: str,
        writer: _ChunkWriter,
        state: PackageCollectorState,
        created_at: datetime,
    ) -> PackageInventoryIndex:
        return PackageInventoryIndex(
            discovery_id=discovery_id,
            inventory_sha256=writer.inventory_sha256(),
            policy_sha256=self.policy.sha256(),
            record_count=writer.record_count,
            complete=state.complete,
            counts_by_manager=dict(sorted(writer.counts_by_manager.items())),
            counts_by_architecture=dict(sorted(writer.counts_by_architecture.items())),
            counts_by_status=dict(sorted(writer.counts_by_status.items())),
            collectors=[state],
            chunks=writer.chunks,
            created_at=created_at,
        )
