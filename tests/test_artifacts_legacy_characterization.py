import json
from pathlib import Path

from rolo.core.artifacts import ArtifactStore


def test_artifact_store_preserves_nested_json_and_text_writes(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "artifacts")

    json_path = store.write_json("nested/state.json", {"status": "READY", "count": 2})
    text_path = store.write_text("nested/notes.txt", "operator note\n")

    assert json_path == tmp_path / "artifacts" / "nested" / "state.json"
    assert text_path == tmp_path / "artifacts" / "nested" / "notes.txt"
    assert json.loads(json_path.read_text(encoding="utf-8")) == {
        "status": "READY",
        "count": 2,
    }
    assert text_path.read_text(encoding="utf-8") == "operator note\n"


def test_artifact_store_preserves_append_jsonl_record_order_and_encoding(
    tmp_path: Path,
) -> None:
    store = ArtifactStore(tmp_path / "artifacts")

    store.append_jsonl("audit/events.jsonl", {"event": "开始", "ok": True})
    store.append_jsonl("audit/events.jsonl", {"event": "完成", "ok": False})

    lines = (tmp_path / "artifacts" / "audit" / "events.jsonl").read_text(
        encoding="utf-8"
    ).splitlines()
    assert [json.loads(line) for line in lines] == [
        {"event": "开始", "ok": True},
        {"event": "完成", "ok": False},
    ]
