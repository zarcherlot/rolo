from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def append_jsonl(self, relative_path: str, value: dict[str, Any]) -> Path:
        self.ensure()
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(value, ensure_ascii=False, default=str))
            stream.write("\n")
        return path

    def write_json(self, relative_path: str, value: dict[str, Any]) -> Path:
        self.ensure()
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
        return path
