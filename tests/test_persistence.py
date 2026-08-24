import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from rolo.core.artifacts import ArtifactStore
from rolo.core.persistence import atomic_write_text


def test_concurrent_atomic_writers_never_share_temporary_files(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda value: store.write_json("latest.json", {"value": value}), range(40)))

    payload = json.loads((tmp_path / "latest.json").read_text(encoding="utf-8"))
    assert payload["value"] in range(40)
    assert not list(tmp_path.glob("*.tmp"))
    assert not list(tmp_path.glob("*.lock"))


def test_concurrent_jsonl_records_remain_complete(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda value: store.append_jsonl("audit.jsonl", {"value": value}), range(40)))

    lines = (tmp_path / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    records = [json.loads(line) for line in lines]
    assert sorted(record["value"] for record in records) == list(range(40))


def test_atomic_writer_retries_transient_windows_permission_race(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_open = os.open
    denied = False

    def transient_open(path, flags, mode=0o777):
        nonlocal denied
        if not denied and Path(path).name.startswith(".l"):
            denied = True
            raise PermissionError("simulated Windows lock release race")
        return real_open(path, flags, mode)

    monkeypatch.setattr("rolo.core.persistence.os.open", transient_open)
    target = tmp_path / "record.json"

    atomic_write_text(target, '{"status":"committed"}\n')

    assert denied is True
    assert target.read_text(encoding="utf-8") == '{"status":"committed"}\n'
