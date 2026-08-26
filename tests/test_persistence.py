import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from rolo.core.artifacts import ArtifactStore
from rolo.core.persistence import atomic_write_text, interprocess_lock


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


@pytest.mark.skipif(os.name != "nt", reason="Windows replacement sharing violation")
def test_atomic_writer_retries_transient_windows_replace_race(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_replace = os.replace
    denied = False

    def transient_replace(source, destination):  # type: ignore[no-untyped-def]
        nonlocal denied
        if not denied:
            denied = True
            raise PermissionError("simulated Windows replacement sharing violation")
        return real_replace(source, destination)

    monkeypatch.setattr("rolo.core.persistence.os.replace", transient_replace)
    target = tmp_path / "record.json"

    atomic_write_text(target, '{"status":"committed"}\n')

    assert denied is True
    assert target.read_text(encoding="utf-8") == '{"status":"committed"}\n'


def test_interprocess_lock_reclaims_same_host_owner_after_hard_crash(
    tmp_path: Path,
) -> None:
    target = tmp_path / "session-execution.guard"
    acquired = tmp_path / "child-acquired"
    program = (
        "import os,sys\n"
        "from pathlib import Path\n"
        "from rolo.core.persistence import interprocess_lock\n"
        "with interprocess_lock(Path(sys.argv[1]), stale_after_s=3600):\n"
        "    Path(sys.argv[2]).write_text('acquired', encoding='ascii')\n"
        "    os._exit(23)\n"
    )
    child = subprocess.Popen(
        [sys.executable, "-c", program, str(target), str(acquired)],
        env=os.environ.copy(),
    )
    assert child.wait(timeout=10) == 23
    assert acquired.read_text(encoding="ascii") == "acquired"

    with interprocess_lock(target, timeout_s=2, stale_after_s=3600):
        assert target.parent.exists()
