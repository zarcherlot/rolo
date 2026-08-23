from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rolo.core.persistence import append_text_record, atomic_write_text


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def append_jsonl(self, relative_path: str, value: dict[str, Any]) -> Path:
        self.ensure()
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        append_text_record(
            path, json.dumps(value, ensure_ascii=False, default=str) + "\n"
        )
        return path

    def write_json(self, relative_path: str, value: dict[str, Any]) -> Path:
        self.ensure()
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            path,
            json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n",
        )
        return path

    def write_text(self, relative_path: str, value: str) -> Path:
        self.ensure()
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, value)
        return path
