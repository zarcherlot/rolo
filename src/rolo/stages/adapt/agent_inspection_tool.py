"""Standalone, standard-library-only query tool copied into an Adapter Agent workspace."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import zlib
from pathlib import Path
from typing import Any

from rolo_agent_wiki import wiki_search_page, wiki_section_page

MAX_WIKI_CONTENT_BYTES = 2_000_000
MAX_OPERATION_LIST_LIMIT = 50
DEFAULT_OPERATION_LIST_LIMIT = 20
MAX_BATCH_INSPECT = 8
MAX_QUERY_RESPONSE_BYTES = 16 * 1024
MAX_DESCRIBE_OUTPUT_BYTES = 200_000
DESCRIBE_TIMEOUT_S = 10.0


def _terminate_process_tree(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=5,
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        process.kill()
    except OSError:
        pass


def _bounded_describe(command: list[str], *, cwd: Path, environment: dict[str, str]) -> str:
    """Run advisory describe inside the Agent sandbox with bounded resources."""
    options: dict[str, Any] = {
        "cwd": cwd,
        "env": environment,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
    }
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    process = subprocess.Popen(command, **options)
    stdout = bytearray()
    stderr = bytearray()
    output_limited = threading.Event()

    def drain(stream: Any, target: bytearray) -> None:
        while True:
            chunk = stream.read(16 * 1024)
            if not chunk:
                return
            remaining = MAX_DESCRIBE_OUTPUT_BYTES - len(target)
            if remaining > 0:
                target.extend(chunk[:remaining])
            if len(chunk) > remaining:
                output_limited.set()
                _terminate_process_tree(process)
                return

    readers = [
        threading.Thread(target=drain, args=(process.stdout, stdout), daemon=True),
        threading.Thread(target=drain, args=(process.stderr, stderr), daemon=True),
    ]
    for reader in readers:
        reader.start()
    try:
        returncode = process.wait(timeout=DESCRIBE_TIMEOUT_S)
    except subprocess.TimeoutExpired as exc:
        _terminate_process_tree(process)
        process.wait(timeout=5)
        raise ValueError("adapter describe preflight timed out") from exc
    finally:
        for reader in readers:
            reader.join(timeout=2)
    if output_limited.is_set():
        raise ValueError("adapter describe preflight exceeded its output limit")
    stderr_text = stderr.decode("utf-8", errors="replace")
    if returncode != 0:
        raise ValueError(f"adapter describe preflight failed: {stderr_text[:1000]}")
    return stdout.decode("utf-8", errors="replace")


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


def _take_flag(arguments: list[str], name: str) -> bool:
    if name not in arguments:
        return False
    arguments.remove(name)
    return True


def _operation_items(snapshot: dict[str, Any], scope: str) -> list[dict[str, Any]]:
    items = snapshot["operation_index"]
    if scope == "all":
        return items
    if scope == "current-task":
        allowed = set(snapshot["current_task_operations"])
    elif scope == "target":
        allowed = set(snapshot["target_operations"])
    else:
        raise ValueError("operation scope must be current-task, target, or all")
    return [item for item in items if item["operation"] in allowed]


def _page(items: list[dict[str, Any]], *, cursor: int, limit: int) -> dict[str, Any]:
    if cursor < 0:
        raise ValueError("cursor must be non-negative")
    if limit < 1 or limit > MAX_OPERATION_LIST_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_OPERATION_LIST_LIMIT}")
    selected = items[cursor : cursor + limit]
    next_cursor = cursor + len(selected)
    return {
        "operations": selected,
        "returned_count": len(selected),
        "truncated": next_cursor < len(items),
        "next_cursor": str(next_cursor) if next_cursor < len(items) else None,
        "total_count": len(items),
    }


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
        describe_output = _bounded_describe(
            command,
            cwd=package_path.parent,
            environment=environment,
        )
    except OSError as exc:
        raise ValueError(f"adapter describe preflight could not complete: {exc}") from exc
    try:
        described = json.loads(describe_output)
    except json.JSONDecodeError as exc:
        raise ValueError("adapter describe preflight returned invalid JSON") from exc
    if not isinstance(described, dict) or described.get("operations") != expected_operations:
        raise ValueError("adapter describe preflight does not match the bundle operations map")
    return {"outputs": output_options, "files": files}


def _wiki_content(snapshot: dict[str, Any]) -> str:
    relative = snapshot["wiki"]["content_file"]
    path = Path(__file__).with_name(relative)
    compressed = path.read_bytes()
    decoder = zlib.decompressobj()
    payload = decoder.decompress(compressed, MAX_WIKI_CONTENT_BYTES + 1)
    if (
        len(payload) > MAX_WIKI_CONTENT_BYTES
        or decoder.unconsumed_tail
        or decoder.unused_data
        or not decoder.eof
    ):
        raise ValueError("Wiki content exceeds the bounded decompression limit")
    content = payload.decode("utf-8")
    expected = snapshot["wiki"]["index"]["sha256"]
    if hashlib.sha256(payload).hexdigest() != expected:
        raise ValueError("Wiki content hash does not match its inspection index")
    return content


def _native_broker_request(action: str, *, tool_id: str | None = None) -> Any:
    address = os.environ.get("ROLO_NATIVE_BROKER_ADDRESS", "")
    token = os.environ.get("ROLO_NATIVE_BROKER_TOKEN", "")
    if not address or not token or ":" not in address:
        raise ValueError("Agent-native broker is not available in this session")
    host, port_text = address.rsplit(":", 1)
    try:
        port = int(port_text)
    except ValueError as exc:
        raise ValueError("Agent-native broker address is invalid") from exc
    request: dict[str, Any] = {"action": action}
    if tool_id is not None:
        request["tool_id"] = tool_id
    encoded = (json.dumps({**request, "token": token}, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )
    if len(encoded) > 16 * 1024:
        raise ValueError("Agent-native broker request exceeds its byte limit")
    with socket.create_connection((host, port), timeout=15) as connection:
        connection.sendall(encoded)
        payload = bytearray()
        while len(payload) <= 512 * 1024:
            chunk = connection.recv(16 * 1024)
            if not chunk:
                break
            payload.extend(chunk)
            if b"\n" in chunk:
                break
    if len(payload) > 512 * 1024:
        raise ValueError("Agent-native broker response exceeds its byte limit")
    response = json.loads(bytes(payload).decode("utf-8"))
    if not isinstance(response, dict) or response.get("status") == "ERROR":
        raise ValueError(str(response.get("message", "Agent-native broker request failed")))
    return response


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

    if group == "native" and action in {"list", "run"}:
        if action == "list":
            return _native_broker_request("list")
        return _native_broker_request("run", tool_id=_required_argument(rest))

    if group == "operations" and action == "summary":
        return snapshot["workset_summary"]
    if group == "operations" and action == "list":
        all_requested = _take_flag(rest, "--all")
        scope = _take_option(rest, "--scope") or ("all" if all_requested else "all")
        limit_value = _take_option(rest, "--limit")
        cursor = int(_take_option(rest, "--cursor") or "0")
        filters = {
            key: _take_option(rest, f"--{key}")
            for key in ("applicability", "implementation", "registration", "layer")
        }
        items = _operation_items(snapshot, scope)
        filtered = [
            item
            for item in items
            if all(value is None or item.get(key) == value for key, value in filters.items())
        ]
        # No paging options preserves the legacy full-list behavior.
        if limit_value is None and not any(
            value is not None for value in filters.values()
        ) and scope == "all":
            page = {
                "operations": filtered,
                "returned_count": len(filtered),
                "truncated": False,
                "next_cursor": None,
                "total_count": len(filtered),
            }
        else:
            page = _page(
                filtered,
                cursor=cursor,
                limit=int(limit_value or DEFAULT_OPERATION_LIST_LIMIT),
            )
        return {
            "robot_id": snapshot["robot_id"],
            "discovery_id": snapshot["discovery_id"],
            "scope": scope,
            **page,
        }
    if group == "operations" and action == "search":
        scope = _take_option(rest, "--scope") or "target"
        limit = int(_take_option(rest, "--limit") or "10")
        cursor = int(_take_option(rest, "--cursor") or "0")
        query = _required_argument(rest).casefold()
        matches = [
            item
            for item in _operation_items(snapshot, scope)
            if query in item["operation"].casefold() or query in item["layer"].casefold()
        ]
        return {
            "robot_id": snapshot["robot_id"],
            "discovery_id": snapshot["discovery_id"],
            "query": query,
            "scope": scope,
            **_page(matches, cursor=cursor, limit=limit),
        }
    if group == "operations" and action == "inspect":
        operation = _required_argument(rest)
        try:
            return snapshot["operation_details"][operation]
        except KeyError as exc:
            raise ValueError(f"NOT_IN_CURRENT_SLICE: {operation}") from exc
    if group == "operations" and action == "batch-inspect":
        operations = [value for value in rest if not value.startswith("--")]
        if not operations:
            raise ValueError("batch-inspect requires at least one operation")
        if len(operations) > MAX_BATCH_INSPECT:
            raise ValueError(f"batch-inspect accepts at most {MAX_BATCH_INSPECT} operations")
        outside = [item for item in operations if item not in snapshot["operation_details"]]
        if outside:
            raise ValueError(f"NOT_IN_CURRENT_SLICE: {', '.join(outside)}")
        return {
            "robot_id": snapshot["robot_id"],
            "discovery_id": snapshot["discovery_id"],
            "operations": [snapshot["operation_details"][item] for item in operations],
            "returned_count": len(operations),
        }
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
        cursor = int(_take_option(rest, "--cursor") or "0")
        query = _required_argument(rest)
        return {
            "wiki_ref": snapshot["wiki"]["ref"],
            **wiki_search_page(_wiki_content(snapshot), query, cursor=cursor),
        }
    if group == "wiki" and action == "section":
        cursor = int(_take_option(rest, "--cursor") or "0")
        heading = _required_argument(rest)
        return {
            "wiki_ref": snapshot["wiki"]["ref"],
            **wiki_section_page(_wiki_content(snapshot), heading, cursor=cursor),
        }
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
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    snapshot_path = Path(__file__).with_name("rolo-agent-inspection.json")
    try:
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        original_arguments = sys.argv[1:]
        arguments = list(original_arguments)
        result = _query(snapshot, arguments)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    response_bytes = len(rendered.encode("utf-8"))
    legacy_full_list = (
        "operations" in original_arguments
        and "list" in original_arguments
        and "--limit" not in original_arguments
        and "--scope" not in original_arguments
    )
    if response_bytes > MAX_QUERY_RESPONSE_BYTES and not legacy_full_list:
        print(
            json.dumps(
                {"error": "query response exceeds 16 KiB; narrow the scope or use pagination"},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2
    metrics_path = Path(__file__).with_name("rolo-agent-query-metrics.json")
    try:
        metrics = (
            json.loads(metrics_path.read_text(encoding="utf-8"))
            if metrics_path.is_file()
            else {}
        )
        metrics["query_count"] = int(metrics.get("query_count", 0)) + 1
        if "inspect" in original_arguments or "batch-inspect" in original_arguments:
            metrics["inspect_count"] = int(metrics.get("inspect_count", 0)) + 1
        metrics["response_bytes"] = int(metrics.get("response_bytes", 0)) + response_bytes
        metrics_path.write_text(json.dumps(metrics, sort_keys=True), encoding="utf-8")
    except (OSError, ValueError, TypeError):
        pass
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
