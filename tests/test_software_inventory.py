import hashlib
import json
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

import pytest

from rolo.stages.build.software_inventory import (
    CollectorStatus,
    DpkgPackageCollector,
    PackageRecord,
    SoftwareInventoryPolicy,
    load_software_inventory_policy,
    write_package_records,
)

COLLECTED_AT = datetime(2026, 8, 18, tzinfo=timezone.utc)


def dpkg_lines(count: int) -> list[bytes]:
    return [
        f"package-{index:05d}\t1.0.{index}\tarm64\tii \n".encode()
        for index in range(count)
    ]


def load_chunk_records(output_dir: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for path in sorted(output_dir.glob("dpkg-*.jsonl")):
        records.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines())
    return records


def test_more_than_1000_packages_roll_over_without_truncation(tmp_path: Path) -> None:
    output_dir = tmp_path / "package_inventory"
    collector = DpkgPackageCollector(
        SoftwareInventoryPolicy(records_per_chunk=1_000, bytes_per_chunk=10_000_000)
    )

    index = collector.collect(
        output_dir=output_dir,
        artifact_prefix="artifact://inventory",
        discovery_id="disc-many",
        collected_at=COLLECTED_AT,
        lines=dpkg_lines(2_505),
    )

    assert index.complete is True
    assert index.record_count == 2_505
    assert [chunk.record_count for chunk in index.chunks] == [1_000, 1_000, 505]
    assert index.collectors[0].status == CollectorStatus.SUCCEEDED
    assert index.collectors[0].truncated is False
    for chunk in index.chunks:
        path = output_dir / Path(chunk.artifact_ref).name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == chunk.sha256
    records = load_chunk_records(output_dir)
    assert len(records) == 2_505
    assert records[0]["package_id"] == "dpkg:arm64:package-00000"
    assert records[-1]["package_id"] == "dpkg:arm64:package-02504"


def test_inventory_content_hash_does_not_depend_on_chunk_size(tmp_path: Path) -> None:
    lines = dpkg_lines(1_205)
    large_chunks = DpkgPackageCollector(
        SoftwareInventoryPolicy(records_per_chunk=1_000, bytes_per_chunk=10_000_000)
    ).collect(
        output_dir=tmp_path / "large",
        artifact_prefix="artifact://large",
        discovery_id="disc-large",
        collected_at=COLLECTED_AT,
        lines=lines,
    )
    small_chunks = DpkgPackageCollector(
        SoftwareInventoryPolicy(records_per_chunk=333, bytes_per_chunk=10_000_000)
    ).collect(
        output_dir=tmp_path / "small",
        artifact_prefix="artifact://small",
        discovery_id="disc-small",
        collected_at=COLLECTED_AT,
        lines=lines,
    )

    assert len(large_chunks.chunks) == 2
    assert len(small_chunks.chunks) == 4
    assert large_chunks.inventory_sha256 == small_chunks.inventory_sha256
    assert load_chunk_records(tmp_path / "large") == load_chunk_records(tmp_path / "small")


def test_collector_wide_byte_limit_is_explicitly_partial(tmp_path: Path) -> None:
    collector = DpkgPackageCollector(
        SoftwareInventoryPolicy(
            max_raw_bytes_per_collector=100,
            records_per_chunk=1_000,
            bytes_per_chunk=10_000_000,
        )
    )

    index = collector.collect(
        output_dir=tmp_path / "limited",
        artifact_prefix="artifact://limited",
        discovery_id="disc-limited",
        collected_at=COLLECTED_AT,
        lines=dpkg_lines(10),
    )

    state = index.collectors[0]
    assert state.status == CollectorStatus.PARTIAL
    assert state.complete is False
    assert state.truncated is True
    assert state.limit_name == "max_raw_bytes_per_collector"
    assert 0 < state.record_count < 10
    assert state.record_count == index.record_count


def test_malformed_record_cannot_produce_complete_inventory(tmp_path: Path) -> None:
    index = DpkgPackageCollector().collect(
        output_dir=tmp_path / "malformed",
        artifact_prefix="artifact://malformed",
        discovery_id="disc-malformed",
        collected_at=COLLECTED_AT,
        lines=[*dpkg_lines(2), b"not-a-valid-record\n", *dpkg_lines(1)],
    )

    state = index.collectors[0]
    assert state.status == CollectorStatus.PARTIAL
    assert state.malformed_records == 1
    assert state.record_count == 3
    assert index.complete is False


def test_oversized_unterminated_record_is_bounded(tmp_path: Path) -> None:
    index = DpkgPackageCollector(
        SoftwareInventoryPolicy(max_record_bytes=64)
    ).collect(
        output_dir=tmp_path / "oversized",
        artifact_prefix="artifact://oversized",
        discovery_id="disc-oversized",
        collected_at=COLLECTED_AT,
        lines=[b"x" * 65],
    )

    state = index.collectors[0]
    assert state.status == CollectorStatus.FAILED
    assert state.limit_name == "max_record_bytes"
    assert state.record_count == 0


def test_checked_in_policy_uses_1000_record_chunk_rollover() -> None:
    policy = load_software_inventory_policy(Path("configs/discovery.yaml"))

    assert policy.records_per_chunk == 1_000
    assert policy.max_raw_bytes_per_collector == 50 * 1024 * 1024
    assert policy.max_relevant_candidates == 1_000
    assert policy.max_ownership_queries == 200


def test_not_applicable_is_distinct_from_successfully_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "rolo.stages.build.software_inventory.platform.system",
        lambda: "Windows",
    )
    collector = DpkgPackageCollector()

    not_applicable = collector.collect(
        output_dir=tmp_path / "not-applicable",
        artifact_prefix="artifact://not-applicable",
        discovery_id="disc-not-applicable",
        collected_at=COLLECTED_AT,
    )
    empty = collector.collect(
        output_dir=tmp_path / "empty",
        artifact_prefix="artifact://empty",
        discovery_id="disc-empty",
        collected_at=COLLECTED_AT,
        lines=[],
    )

    assert not_applicable.collectors[0].status == CollectorStatus.NOT_APPLICABLE
    assert not_applicable.complete is True
    assert empty.collectors[0].status == CollectorStatus.SUCCEEDED
    assert empty.complete is True


def test_command_start_failure_becomes_a_failed_collector_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    collector = DpkgPackageCollector()

    def broken_lines(_: Path) -> Iterator[bytes]:
        def generate() -> Iterator[bytes]:
            raise OSError("permission denied")
            yield b""  # pragma: no cover

        return generate()

    monkeypatch.setattr(
        DpkgPackageCollector,
        "_trusted_executable",
        staticmethod(lambda: Path("/usr/bin/dpkg-query")),
    )
    monkeypatch.setattr(collector, "_command_lines", broken_lines)
    monkeypatch.setattr(
        "rolo.stages.build.software_inventory.platform.system",
        lambda: "Linux",
    )

    index = collector.collect(
        output_dir=tmp_path / "failed",
        artifact_prefix="artifact://failed",
        discovery_id="disc-failed",
        collected_at=COLLECTED_AT,
    )

    state = index.collectors[0]
    assert state.status == CollectorStatus.FAILED
    assert state.complete is False
    assert state.truncated is True
    assert "permission denied" in (state.reason or "")


def test_targeted_records_use_same_1000_record_chunk_contract(tmp_path: Path) -> None:
    records = [
        PackageRecord(
            package_id=f"python:package-{index:04d}",
            name=f"package-{index:04d}",
            version="1.0",
            status="installed",
            manager="python",
            collector="python.metadata",
            collector_provenance="test",
            collected_at=COLLECTED_AT,
        )
        for index in range(1_001)
    ]

    index = write_package_records(
        records=records,
        output_dir=tmp_path / "relevant",
        artifact_prefix="artifact://relevant",
        discovery_id="disc-relevant",
        policy=SoftwareInventoryPolicy(
            records_per_chunk=1_000,
            bytes_per_chunk=10_000_000,
        ),
        collector="application.relevant",
        chunk_prefix="relevant",
        created_at=COLLECTED_AT,
    )

    assert index.complete is True
    assert index.record_count == 1_001
    assert [chunk.record_count for chunk in index.chunks] == [1_000, 1]
    assert [Path(chunk.artifact_ref).name for chunk in index.chunks] == [
        "relevant-0001.jsonl",
        "relevant-0002.jsonl",
    ]
