from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from rolo.commands import adapt_tools
from rolo.stages.adapt.workset import (
    OperationApplicability,
    OperationImplementation,
    OperationRegistration,
)


def _workset():
    def item(operation, layer, applicability, implementation, registration):
        return SimpleNamespace(
            operation=operation,
            layer=layer,
            applicability=applicability,
            implementation=implementation,
            registration=registration,
            model_dump=lambda mode="json": {"operation": operation, "layer": layer},
        )

    return SimpleNamespace(
        discovery_id="disc-1",
        operations=[
            item(
                "app.navigation.start",
                "app",
                OperationApplicability.OBSERVED,
                OperationImplementation.UNBOUND,
                OperationRegistration.NOT_REGISTERED,
            ),
            item(
                "ros.topic.list",
                "ros",
                OperationApplicability.NOT_OBSERVED,
                OperationImplementation.BUILTIN,
                OperationRegistration.REGISTERED,
            ),
        ],
    )


def test_adapt_tool_operation_filters_and_bounds(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[object] = []
    monkeypatch.setattr(adapt_tools, "emit", captured.append)
    monkeypatch.setattr(adapt_tools, "_settings", lambda: (Path("artifacts"), Path("output")))
    monkeypatch.setattr(adapt_tools, "_discovery_id", lambda: None)
    monkeypatch.setattr(adapt_tools, "build_operation_workset", lambda *args: _workset())

    adapt_tools.operations_list(
        robot="robot",
        applicability=OperationApplicability.OBSERVED,
        implementation=OperationImplementation.UNBOUND,
        registration=OperationRegistration.NOT_REGISTERED,
        layer="app",
        scope="current-task",
        limit=1,
        cursor=0,
        all_operations=False,
    )
    assert captured[-1]["returned_count"] == 1
    with pytest.raises(Exception, match="scope"):
        adapt_tools.operations_list(
            robot="robot",
            applicability=None,
            implementation=None,
            registration=None,
            layer=None,
            scope="bad",
            limit=None,
            cursor=0,
            all_operations=False,
        )
    with pytest.raises(Exception, match="1 to 8"):
        adapt_tools.operations_batch_inspect([], robot="robot")
    monkeypatch.setattr(adapt_tools, "operation_detail", lambda *args: {"operation": args[3]})
    adapt_tools.operations_batch_inspect(["app.navigation.start"], robot="robot")
    assert captured[-1]["returned_count"] == 1


def test_adapt_tool_query_wrappers_forward_and_translate_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[object] = []
    monkeypatch.setattr(adapt_tools, "emit", captured.append)
    monkeypatch.setattr(adapt_tools, "_settings", lambda: (Path("a"), Path("o")))
    monkeypatch.setattr(adapt_tools, "_discovery_id", lambda: "disc")
    monkeypatch.setattr(
        adapt_tools,
        "_report",
        lambda *args: SimpleNamespace(
            discovery_id="disc", software_summary={}, dependency_report_ref=None
        ),
    )
    monkeypatch.setattr(adapt_tools, "candidate_detail", lambda *args: {"candidate": args[2]})
    monkeypatch.setattr(
        adapt_tools,
        "executable_detail",
        lambda *args: SimpleNamespace(
            executable_id=args[2],
            launch_analysis={"available": True},
            invocation={"entrypoint": []},
            communication={},
            dependencies={"python": []},
        ),
    )
    monkeypatch.setattr(adapt_tools, "evidence_metadata", lambda *args: {"reference": args[2]})
    monkeypatch.setattr(adapt_tools, "evidence_snippet", lambda *args, **kwargs: {"content": "x"})
    monkeypatch.setattr(adapt_tools, "wiki_section", lambda *args: {"heading": args[2]})
    monkeypatch.setattr(adapt_tools, "wiki_search", lambda *args: {"query": args[2]})

    adapt_tools.candidates_inspect("op", "robot")
    adapt_tools.executable_inspect("exe", "robot")
    adapt_tools.launch_inspect("exe", "robot")
    adapt_tools.dependency_inspect("robot", executable_id="exe")
    adapt_tools.evidence_resolve("artifact://x", "robot")
    adapt_tools.evidence_read_snippet("artifact://x", "robot", start_line=2, lines=3)
    adapt_tools.robot_wiki_section("Heading", "robot")
    adapt_tools.robot_wiki_search("query", "robot")
    assert len(captured) == 8

    monkeypatch.setattr(
        adapt_tools, "candidate_detail", lambda *args: (_ for _ in ()).throw(ValueError("bad"))
    )
    with pytest.raises(Exception, match="bad"):
        adapt_tools.candidates_inspect("op", "robot")
