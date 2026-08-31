from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import types
import zlib
from pathlib import Path

import pytest

SOURCE = Path(__file__).parents[1] / "src/rolo/stages/adapt/agent_inspection_tool.py"


@pytest.fixture
def tool(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Load the copied, stdlib-only tool with the bundled wiki functions shimmed."""
    from rolo.stages.adapt import wiki_retrieval

    shim = types.ModuleType("rolo_agent_wiki")
    shim.wiki_search_page = wiki_retrieval.wiki_search_page
    shim.wiki_section_page = wiki_retrieval.wiki_section_page
    monkeypatch.setitem(sys.modules, "rolo_agent_wiki", shim)
    name = "rolo_test_agent_inspection_tool"
    spec = importlib.util.spec_from_file_location(name, SOURCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "__file__", str(tmp_path / "agent_inspection_tool.py"))
    return module


@pytest.fixture
def snapshot(tmp_path: Path) -> dict[str, object]:
    wiki = "# Robot Wiki\n\n## Motion\n\nvelocity is available\n"
    wiki_path = tmp_path / "rolo-agent-wiki.zlib"
    wiki_path.write_bytes(zlib.compress(wiki.encode("utf-8")))
    return {
        "robot_id": "demo",
        "discovery_id": "disc-1",
        "workset_summary": {"count": 2},
        "operation_index": [
            {
                "operation": "app.teleop.velocity",
                "layer": "app",
                "applicability": "APPLICABLE",
                "implementation": "adapter",
                "registration": "registered",
            },
            {
                "operation": "ros.topic.list",
                "layer": "ros",
                "applicability": "UNKNOWN",
                "implementation": "native",
                "registration": "declared",
            },
        ],
        "current_task_operations": ["app.teleop.velocity"],
        "target_operations": ["app.teleop.velocity", "ros.topic.list"],
        "operation_details": {"app.teleop.velocity": {"contract": "velocity-contract"}},
        "candidate_details": {"app.teleop.velocity": {"status": "CANDIDATE"}},
        "executables": {
            "exe-1": {
                "executable_id": "exe-1",
                "name": "driver",
                "origin": "target",
                "path": "/opt/driver",
                "invocation": {"entrypoint": ["driver", "--help"]},
                "launch_analysis": {"available": True},
                "communication": {"topics": ["/cmd_vel"]},
                "dependencies": {"python": ["numpy"]},
            }
        },
        "dependency_summary": {"count": 1},
        "schemas": {"Velocity": {"type": "object"}},
        "evidence": {
            "evidence://one": {
                "authority": "observed",
                "content": "line one\nline two\nline three",
                "path": "driver.py",
            }
        },
        "wiki": {
            "ref": "artifact://wiki",
            "content_file": "rolo-agent-wiki.zlib",
            "index": {"sha256": hashlib.sha256(wiki.encode()).hexdigest()},
        },
    }


def test_query_covers_operations_paging_and_scopes(tool, snapshot):
    assert tool._query(snapshot, ["adapt", "operations", "summary"]) == {"count": 2}
    full = tool._query(snapshot, ["operations", "list"])
    assert full["returned_count"] == 2 and full["truncated"] is False
    page = tool._query(
        snapshot,
        ["operations", "list", "--scope", "current-task", "--limit", "1"],
    )
    assert page["operations"][0]["operation"] == "app.teleop.velocity"
    search = tool._query(snapshot, ["operations", "search", "velocity"])
    assert search["total_count"] == 1
    assert tool._query(snapshot, ["operations", "inspect", "app.teleop.velocity"])["contract"]
    assert (
        tool._query(snapshot, ["operations", "batch-inspect", "app.teleop.velocity"])[
            "returned_count"
        ]
        == 1
    )


def test_query_covers_executables_schemas_evidence_and_wiki(tool, snapshot):
    assert tool._query(snapshot, ["candidates", "inspect", "app.teleop.velocity"])["status"]
    assert (
        tool._query(snapshot, ["executable", "list"])["executables"][0]["executable_id"] == "exe-1"
    )
    assert tool._query(snapshot, ["executable", "inspect", "exe-1"])["name"] == "driver"
    launch = tool._query(snapshot, ["launch", "inspect", "exe-1"])
    assert launch["launch"]["available"] is True
    assert tool._query(snapshot, ["dependency", "inspect"])["count"] == 1
    assert tool._query(snapshot, ["dependency", "inspect", "--executable-id", "exe-1"])[
        "dependencies"
    ] == {"python": ["numpy"]}
    assert tool._query(snapshot, ["schema", "inspect", "Velocity"])["type"] == "object"
    assert (
        tool._query(snapshot, ["evidence", "resolve", "evidence://one"])["authority"] == "observed"
    )
    snippet = tool._query(
        snapshot,
        ["evidence", "snippet", "--start-line", "2", "--lines", "1", "evidence://one"],
    )
    assert snippet["content"] == "line two"

    wiki_search = tool._query(snapshot, ["wiki", "search", "velocity"])
    assert wiki_search["matches"][0]["line"] == 5
    wiki_section = tool._query(snapshot, ["wiki", "section", "Motion"])
    assert "velocity" in wiki_section["content"]


def test_query_rejects_unsafe_or_out_of_scope_requests(tool, snapshot):
    cases = [
        (["unknown", "action"], "unsupported read-only query"),
        (["operations", "inspect", "missing"], "NOT_IN_CURRENT_SLICE"),
        (["operations", "batch-inspect"], "at least one operation"),
        (["candidates", "inspect", "missing"], "no prepared candidate"),
        (["executable", "inspect", "missing"], "unknown executable_id"),
        (["schema", "inspect", "missing"], "unknown prepared schema"),
        (["operations", "list", "--scope", "invalid"], "operation scope"),
        (["operations", "search"], "missing query argument"),
    ]
    for arguments, message in cases:
        with pytest.raises(ValueError, match=message):
            tool._query(snapshot, arguments)
    with pytest.raises(ValueError, match="pinned to robot"):
        tool._query(snapshot, ["operations", "summary", "--robot", "other"])
    with pytest.raises(ValueError, match="expected a query group"):
        tool._query(snapshot, ["operations"])


def test_native_broker_request_and_native_queries(tool, snapshot, monkeypatch):
    monkeypatch.setenv("ROLO_NATIVE_BROKER_ADDRESS", "127.0.0.1:1234")
    monkeypatch.setenv("ROLO_NATIVE_BROKER_TOKEN", "secret")
    calls: list[tuple[tuple[str, int], bytes]] = []

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def sendall(self, payload: bytes) -> None:
            calls.append((("127.0.0.1", 1234), payload))

        def recv(self, _size: int) -> bytes:
            return b'{"status":"OK","value":1}\n'

    monkeypatch.setattr(tool.socket, "create_connection", lambda address, timeout: Connection())
    assert tool._query(snapshot, ["native", "list"])["value"] == 1
    result = tool._query(
        snapshot,
        ["native", "run", "camera.list", "--mode", "read", "--device-id", "cam0"],
    )
    assert result["value"] == 1
    sent = json.loads(calls[-1][1])
    assert sent["tool_id"] == "camera.list"
    assert sent["arguments"] == {"mode": "read", "device_id": "cam0"}

    monkeypatch.delenv("ROLO_NATIVE_BROKER_TOKEN")
    with pytest.raises(ValueError, match="not available"):
        tool._native_broker_request("list")


def test_main_reads_snapshot_updates_metrics_and_reports_errors(
    tool, snapshot, tmp_path, monkeypatch, capsys
):
    snapshot_path = tmp_path / "agent_inspection_tool.py"
    snapshot_path.with_name("rolo-agent-inspection.json").write_text(
        json.dumps(snapshot), encoding="utf-8"
    )
    monkeypatch.setattr(tool, "__file__", str(snapshot_path))
    monkeypatch.setattr(tool.sys, "argv", ["tool", "operations", "summary"])
    assert tool.main() == 0
    assert json.loads(capsys.readouterr().out) == {"count": 2}
    metrics = json.loads(snapshot_path.with_name("rolo-agent-query-metrics.json").read_text())
    assert metrics == {"query_count": 1, "response_bytes": 16}

    monkeypatch.setattr(tool.sys, "argv", ["tool", "unsupported", "action"])
    assert tool.main() == 2
    assert "unsupported read-only query" in capsys.readouterr().err


def test_pack_handoff_validates_manifest_and_describe(tool, tmp_path, monkeypatch):
    files = {"package.py": b'print({"operations":{"app.demo":"package.py"}})', "data.txt": b"data"}
    for name, payload in files.items():
        (tmp_path / name).write_bytes(payload)
    manifest = {
        "files": [{"path": "data.txt", "sha256": hashlib.sha256(files["data.txt"]).hexdigest()}],
        "package_file": "package.py",
        "package_sha256": hashlib.sha256(files["package.py"]).hexdigest(),
        "operations": [{"operation": "app.demo", "entrypoint": "package.py"}],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(tool, "_workspace_file", lambda relative: tmp_path / relative)
    monkeypatch.setattr(
        tool,
        "_bounded_describe",
        lambda *args, **kwargs: json.dumps(
            manifest["operations"] and {"operations": {"app.demo": "package.py"}}
        ),
    )
    result = tool._pack_handoff(
        [
            "--adapter-manifest",
            "manifest.json",
            "--adapter-package",
            "package.py",
            "--state-graph",
            "data.txt",
            "--conformance-report",
            "data.txt",
        ]
    )
    assert {item["path"] for item in result["files"]} == {"manifest.json", "package.py", "data.txt"}

    with pytest.raises(ValueError, match="all four output"):
        tool._pack_handoff(["--adapter-manifest", "manifest.json"])
