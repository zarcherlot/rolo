from __future__ import annotations

import hashlib
import re
from typing import Any

WIKI_SECTION_MAX_CHARS = 8_000
WIKI_SECTION_MAX_LINES = 120
WIKI_SEARCH_MAX_CHARS = 6_000
WIKI_SEARCH_MAX_MATCHES = 20
WIKI_SEARCH_MAX_LINE_CHARS = 500
WIKI_OUTLINE_MAX_ITEMS = 100
WIKI_INDEX_MAX_SECTIONS = 200


def _headings(content: str) -> list[dict[str, Any]]:
    lines = content.splitlines()
    headings: list[dict[str, Any]] = []
    for line_index, line in enumerate(lines):
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if not match:
            continue
        level = len(match.group(1))
        title = match.group(2).strip()
        headings.append(
            {
                "section_id": f"section-{len(headings) + 1:03d}",
                "heading": line,
                "title": title,
                "level": level,
                "start_line": line_index + 1,
            }
        )
    stack: list[dict[str, Any]] = []
    for item in headings:
        while stack and stack[-1]["level"] >= item["level"]:
            stack.pop()["end_line"] = item["start_line"] - 1
        stack.append(item)
    for item in stack:
        item["end_line"] = len(lines)
    for item in headings:
        end_line = item["end_line"]
        section = "\n".join(lines[item["start_line"] - 1 : end_line])
        item["chars"] = len(section)
        item["sha256"] = hashlib.sha256(section.encode("utf-8")).hexdigest()
    return headings


def build_wiki_index(content: str) -> dict[str, Any]:
    headings = _headings(content)
    return {
        "chars": len(content),
        "lines": len(content.splitlines()),
        "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "section_count": len(headings),
        "sections_truncated": len(headings) > WIKI_INDEX_MAX_SECTIONS,
        "sections": headings[:WIKI_INDEX_MAX_SECTIONS],
    }


def _selected_section(content: str, heading: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    headings = _headings(content)
    wanted = heading.strip().lstrip("#").strip().casefold()
    exact = [item for item in headings if item["title"].casefold() == wanted]
    partial = [item for item in headings if wanted in item["title"].casefold()]
    matches = exact or partial
    if not matches:
        raise ValueError(f"Wiki section not found: {heading}")
    return matches[0], headings


def wiki_section_page(
    content: str,
    heading: str,
    *,
    cursor: int = 0,
    max_chars: int = WIKI_SECTION_MAX_CHARS,
    max_lines: int = WIKI_SECTION_MAX_LINES,
) -> dict[str, Any]:
    selected, headings = _selected_section(content, heading)
    if cursor < 0:
        raise ValueError("Wiki section cursor must be non-negative")
    if selected["level"] == 1:
        candidates = [
            item
            for item in headings
            if item["start_line"] > selected["start_line"]
            and item["start_line"] <= selected["end_line"]
        ]
        outline: list[dict[str, Any]] = []
        outline_chars = 0
        for item in candidates[:WIKI_OUTLINE_MAX_ITEMS]:
            entry = {
                "section_id": item["section_id"],
                "heading": item["heading"][:200],
                "level": item["level"],
                "chars": item["chars"],
            }
            entry_chars = len(entry["heading"]) + 80
            if outline and outline_chars + entry_chars > WIKI_SECTION_MAX_CHARS:
                break
            outline.append(entry)
            outline_chars += entry_chars
        return {
            "section_id": selected["section_id"],
            "heading": selected["heading"],
            "content": selected["heading"],
            "is_outline": True,
            "outline": outline,
            "truncated": len(outline) < len(candidates),
            "next_cursor": None,
        }

    lines = content.splitlines()
    section = "\n".join(lines[selected["start_line"] - 1 : selected["end_line"]])
    if cursor >= len(section):
        raise ValueError("Wiki section cursor is past the end of the section")
    remainder = section[cursor:]
    page_parts: list[str] = []
    consumed = 0
    for part in remainder.splitlines(keepends=True)[:max_lines]:
        available = max_chars - consumed
        if available <= 0:
            break
        selected_part = part[:available]
        page_parts.append(selected_part)
        consumed += len(selected_part)
        if len(selected_part) < len(part):
            break
    page = "".join(page_parts)
    next_offset = cursor + consumed
    truncated = next_offset < len(section)
    return {
        "section_id": selected["section_id"],
        "heading": selected["heading"],
        "content": page,
        "is_outline": False,
        "start_cursor": cursor,
        "truncated": truncated,
        "next_cursor": next_offset if truncated else None,
        "section_chars": len(section),
        "content_sha256": selected["sha256"],
    }


def wiki_search_page(
    content: str,
    query: str,
    *,
    cursor: int = 0,
    max_chars: int = WIKI_SEARCH_MAX_CHARS,
    max_matches: int = WIKI_SEARCH_MAX_MATCHES,
) -> dict[str, Any]:
    if not query.strip():
        raise ValueError("Wiki search query must not be empty")
    if cursor < 0:
        raise ValueError("Wiki search cursor must be non-negative")
    all_matches = [
        {"line": index, "text": line[:WIKI_SEARCH_MAX_LINE_CHARS]}
        for index, line in enumerate(content.splitlines(), start=1)
        if query.casefold() in line.casefold()
    ]
    matches: list[dict[str, Any]] = []
    used_chars = 0
    position = cursor
    while position < len(all_matches) and len(matches) < max_matches:
        item = all_matches[position]
        item_chars = len(item["text"]) + 32
        if matches and used_chars + item_chars > max_chars:
            break
        if not matches and item_chars > max_chars:
            item = {**item, "text": item["text"][: max(0, max_chars - 32)]}
            item_chars = len(item["text"]) + 32
        matches.append(item)
        used_chars += item_chars
        position += 1
    truncated = position < len(all_matches)
    return {
        "query": query,
        "matches": matches,
        "total_matches": len(all_matches),
        "start_cursor": cursor,
        "truncated": truncated,
        "next_cursor": position if truncated else None,
    }
