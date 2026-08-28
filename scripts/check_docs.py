"""Validate documentation layout, metadata, links, and generated-file boundaries."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
GENERATED = {
    DOCS / "OPERATION_CONTRACTS.md",
    DOCS / "CANONICAL_OPERATIONS.md",
}
ROOT_ALLOWLIST = {
    "README.md",
    "README.en.md",
    "DOCUMENT_GOVERNANCE.md",
    "OPERATION_CONTRACTS.md",
    "CANONICAL_OPERATIONS.md",
    "EPISODE_COHORT_READ_MODEL_CONTRACT.md",
    "EPISODE_OBSERVATION_BUNDLE_CONTRACT_DESIGN.md",
    "EPISODE_READ_MODEL_CONTRACT_DESIGN.md",
    "EPISODE_REVISION_HISTORY_CONTRACT.md",
}
STATUS_RE = re.compile(r"\bstatus:\s*(active|frozen|draft|archived|generated)\b", re.I)
AUTHORITY_RE = re.compile(
    r"\bauthority:\s*(normative|guide|plan|reference)\b", re.I
)
LINK_RE = re.compile(r"\]\(([^)]+)\)")
STUB_HEADING_RE = re.compile(r"^# 文档已(?:迁移|归并|归档)")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def first_heading(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line
    return ""


def is_stub(path: Path) -> bool:
    return bool(STUB_HEADING_RE.match(first_heading(read(path))))


def content_lines(text: str):
    """Yield lines outside fenced code blocks for Markdown link checks."""

    fenced = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            yield line


def check_links(path: Path, stubs: set[Path], errors: list[str]) -> None:
    base = path.parent
    text = "\n".join(content_lines(read(path)))
    for match in LINK_RE.finditer(text):
        raw_ref = match.group(1).strip()
        if raw_ref.startswith(("http://", "https://", "mailto:", "#")):
            continue
        ref_path, _, _fragment = raw_ref.partition("#")
        if not ref_path:
            continue
        target = (base / unquote(ref_path)).resolve()
        if not target.exists():
            errors.append(f"{path.relative_to(ROOT)}: broken link {raw_ref!r}")
        elif target in stubs and not is_stub(path):
            errors.append(
                f"{path.relative_to(ROOT)}: links to compatibility stub {raw_ref!r}"
            )


def main() -> int:
    errors: list[str] = []
    docs = sorted(DOCS.rglob("*.md"))
    stubs = {path.resolve() for path in docs if is_stub(path)}

    for path in docs:
        rel = path.relative_to(ROOT)
        text = read(path)
        in_archive = "archive" in path.relative_to(DOCS).parts

        if path in GENERATED:
            # OPERATION_CONTRACTS carries the generator declaration in its body.
            # CANONICAL_OPERATIONS is validated by tests against the canonical export
            # and intentionally has no hand-authored header.
            if path.name == "OPERATION_CONTRACTS.md" and "generated from" not in text.lower():
                errors.append(f"{rel}: generated document lacks source declaration")
        elif not in_archive and not is_stub(path):
            header = "\n".join(text.splitlines()[:20])
            if not STATUS_RE.search(header):
                errors.append(f"{rel}: missing status metadata")
            if not AUTHORITY_RE.search(header):
                errors.append(f"{rel}: missing authority metadata")

        if path.parent == DOCS and path.name not in ROOT_ALLOWLIST and not is_stub(path):
            errors.append(f"{rel}: substantive document must live in a topic directory")

        check_links(path, stubs, errors)

    if errors:
        print("Documentation checks failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"Documentation checks passed ({len(docs)} Markdown files).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
