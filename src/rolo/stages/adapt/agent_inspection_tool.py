"""Standalone, standard-library-only query tool copied into an Adapter Agent workspace."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def _take_option(arguments: list[str], name: str) -> str | None:
    try:
        index = arguments.index(name)
    except ValueError:
        return None
    if index + 1 >= len(arguments):
        raise ValueError(f"missing value for {name}")
    value = arguments[index + 1]
    del arguments[index : index + 2]
    return value


def _required_argument(arguments: list[str]) -> str:
    positional = [value for value in arguments if not value.startswith("--")]
    if not positional:
        raise ValueError("missing query argument")
    return positional[-1]


def _workspace_file(relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts or not candidate.parts:
        raise ValueError(f"handoff path is unsafe: {relative}")
    root = Path(__file__).resolve().parent
    path = (root / candidate).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"handoff path escapes the workspace: {relative}") from exc
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"handoff file is missing or a symlink: {relative}")
    return path


def _pack_handoff(rest: list[str]) -> dict[str, Any]:
    output_options = {
        "adapter_manifest": _take_option(rest, "--adapter-manifest"),
        "adapter_package": _take_option(rest, "--adapter-package"),
        "state_graph": _take_option(rest, "--state-graph"),
        "conformance_report": _take_option(rest, "--conformance-report"),
    }
    if any(value is None for value in output_options.values()):
        raise ValueError("handoff pack requires all four output path options")
    manifest_path = _workspace_file(output_options["adapter_manifest"] or "")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    bundle_files = manifest.get("files")
    if not isinstance(bundle_files, list):
        raise ValueError("bundle manifest must contain a v2 files list")
    paths = [value for value in output_options.values() if value is not None]
    for item in bundle_files:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise ValueError("bundle manifest contains an invalid file entry")
        paths.append(item["path"])
    package_relative = output_options["adapter_package"] or ""
    if manifest.get("package_file") != Path(package_relative).as_posix():
        raise ValueError("bundle package_file does not match --adapter-package")
    operations = manifest.get("operations")
    if not isinstance(operations, list) or not operations:
        raise ValueError("bundle manifest must contain operations")
    expected_operations: dict[str, str] = {}
    for item in operations:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("operation"), str)
            or not isinstance(item.get("entrypoint"), str)
        ):
            raise ValueError("bundle manifest contains an invalid operation entry")
        expected_operations[item["operation"]] = item["entrypoint"]
    unique_paths = list(dict.fromkeys(paths))
    if len(unique_paths) > 256:
        raise ValueError("handoff pack exceeds the 256-file limit")
    files = []
    total_bytes = 0
    for relative in unique_paths:
        path = _workspace_file(relative)
        payload = path.read_bytes()
        if len(payload) > 2 * 1024 * 1024:
            raise ValueError(f"handoff pack file exceeds 2 MiB: {relative}")
        total_bytes += len(payload)
        if total_bytes > 8 * 1024 * 1024:
            raise ValueError("handoff pack exceeds the 8 MiB Agent response limit")
        files.append(
            {
                "path": Path(relative).as_posix(),
                "encoding": "base64",
                "content": base64.b64encode(payload).decode("ascii"),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    actual_by_path = {item["path"]: item for item in files}
    for item in bundle_files:
        actual = actual_by_path[Path(item["path"]).as_posix()]["sha256"]
        if item.get("sha256") != actual:
            raise ValueError(f"bundle file digest mismatch: {item['path']}")
    package_actual = actual_by_path[Path(package_relative).as_posix()]["sha256"]
    if manifest.get("package_sha256") != package_actual:
        raise ValueError("bundle package_sha256 does not match the entrypoint payload")
    package_path = _workspace_file(package_relative)
    command = [sys.executable, str(package_path), "describe"]
    environment = {
        name: value
        for name, value in os.environ.items()
        if not any(
            marker in name.upper()
            for marker in ("KEY", "SECRET", "TOKEN", "PASSWORD", "CREDENTIAL")
        )
    }
    try:
        completed = subprocess.run(
            command,
            cwd=package_path.parent,
            env=environment,
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"adapter describe preflight could not complete: {exc}") from exc
    if completed.returncode != 0:
        raise ValueError(f"adapter describe preflight failed: {completed.stderr[:1000]}")
    try:
        described = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("adapter describe preflight returned invalid JSON") from exc
    if not isinstance(described, dict) or described.get("operations") != expected_operations:
        raise ValueError("adapter describe preflight does not match the bundle operations map")
    return {"outputs": output_options, "files": files}


def _wiki_section(snapshot: dict[str, Any], heading: str) -> dict[str, Any]:
    lines = snapshot["wiki"]["content"].splitlines()
    wanted = heading.strip().lstrip("#").strip().casefold()
    start: int | None = None
    level = 0
    end = len(lines)
    for index, line in enumerate(lines):
        if not line.startswith("#"):
            continue
        title = line.lstrip("#").strip().casefold()
        current_level = len(line) - len(line.lstrip("#"))
        if start is None and wanted in title:
            start = index
            level = current_level
        elif start is not None and current_level <= level:
            end = index
            break
    if start is None:
        raise ValueError(f"Wiki section not found: {heading}")
    return {
        "wiki_ref": snapshot["wiki"]["ref"],
        "heading": lines[start],
        "content": "\n".join(lines[start:end]),
    }


def _query(snapshot: dict[str, Any], arguments: list[str]) -> Any:
    if arguments and arguments[0] == "adapt":
        arguments.pop(0)
    if len(arguments) < 2:
        raise ValueError("expected a query group and action")
    group, action = arguments[:2]
    rest = arguments[2:]
    robot = _take_option(rest, "--robot")
    if robot is not None and robot != snapshot["robot_id"]:
        raise ValueError(f"snapshot is pinned to robot {snapshot['robot_id']}")

    if group == "operations" and action == "summary":
        return snapshot["workset_summary"]
    if group == "operations" and action == "list":
        filters = {
            key: _take_option(rest, f"--{key}")
            for key in ("applicability", "implementation", "registration", "layer")
        }
        items = snapshot["workset_operations"]
        return {
            "robot_id": snapshot["robot_id"],
            "discovery_id": snapshot["discovery_id"],
            "operations": [
                item
                for item in items
                if all(value is None or item.get(key) == value for key, value in filters.items())
            ],
        }
    if group == "operations" and action == "inspect":
        operation = _required_argument(rest)
        try:
            return snapshot["operation_details"][operation]
        except KeyError as exc:
            raise ValueError(
                f"operation is outside the prepared Agent workset: {operation}"
            ) from exc
    if group == "candidates" and action == "inspect":
        operation = _required_argument(rest)
        try:
            return snapshot["candidate_details"][operation]
        except KeyError as exc:
            raise ValueError(f"no prepared candidate for operation: {operation}") from exc
    if group == "executable" and action == "list":
        return {
            "robot_id": snapshot["robot_id"],
            "discovery_id": snapshot["discovery_id"],
            "executables": [
                {
                    "executable_id": item["executable_id"],
                    "name": item["name"],
                    "origin": item["origin"],
                    "path": item["path"],
                    "entrypoint": item["invocation"]["entrypoint"],
                    "has_launch": item["launch_analysis"]["available"],
                }
                for item in snapshot["executables"].values()
            ],
        }
    if group == "executable" and action == "inspect":
        executable_id = _required_argument(rest)
        try:
            return snapshot["executables"][executable_id]
        except KeyError as exc:
            raise ValueError(f"unknown executable_id: {executable_id}") from exc
    if group == "launch" and action == "inspect":
        executable_id = _required_argument(rest)
        try:
            item = snapshot["executables"][executable_id]
        except KeyError as exc:
            raise ValueError(f"unknown executable_id: {executable_id}") from exc
        return {
            "executable_id": executable_id,
            "launch": item["launch_analysis"],
            "invocation": item["invocation"],
            "communication": item["communication"],
        }
    if group == "dependency" and action == "inspect":
        executable_id = _take_option(rest, "--executable-id")
        if executable_id is None:
            return snapshot["dependency_summary"]
        try:
            dependencies = snapshot["executables"][executable_id]["dependencies"]
        except KeyError as exc:
            raise ValueError(f"unknown executable_id: {executable_id}") from exc
        return {"executable_id": executable_id, "dependencies": dependencies}
    if group == "schema" and action == "inspect":
        name = _required_argument(rest)
        try:
            return snapshot["schemas"][name]
        except KeyError as exc:
            raise ValueError(f"unknown prepared schema: {name}") from exc
    if group == "handoff" and action == "pack":
        return _pack_handoff(rest)
    if group == "wiki" and action == "search":
        query = _required_argument(rest)
        matches = [
            {"line": index, "text": line}
            for index, line in enumerate(snapshot["wiki"]["content"].splitlines(), start=1)
            if query.casefold() in line.casefold()
        ][:100]
        return {"wiki_ref": snapshot["wiki"]["ref"], "query": query, "matches": matches}
    if group == "wiki" and action == "section":
        return _wiki_section(snapshot, _required_argument(rest))
    if group == "evidence" and action in {"resolve", "snippet"}:
        reference = _required_argument(rest)
        try:
            evidence = snapshot["evidence"][reference]
        except KeyError as exc:
            raise ValueError(
                f"evidence was not included in the bounded snapshot: {reference}"
            ) from exc
        if action == "resolve":
            return {key: value for key, value in evidence.items() if key != "content"}
        start_line = int(_take_option(rest, "--start-line") or "1")
        line_count = min(200, max(1, int(_take_option(rest, "--lines") or "80")))
        lines = evidence.get("content", "").splitlines()
        selected = lines[max(0, start_line - 1) : max(0, start_line - 1) + line_count]
        return {
            "reference": reference,
            "authority": evidence["authority"],
            "start_line": start_line,
            "line_count": len(selected),
            "truncated": start_line - 1 + len(selected) < len(lines),
            "content": "\n".join(selected),
        }
    raise ValueError(f"unsupported read-only query: {group} {action}")


def main() -> int:
    snapshot_path = Path(__file__).with_name("rolo-agent-inspection.json")
    try:
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        result = _query(snapshot, sys.argv[1:])
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
