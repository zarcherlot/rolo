import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from rolo.core.artifacts import ArtifactStore


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
