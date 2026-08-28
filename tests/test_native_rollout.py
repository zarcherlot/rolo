from datetime import datetime, timezone

from rolo.agent_tools import (
    AgentNativeToolResult,
    NativeToolStatus,
    build_native_operation_parity_report,
    decide_native_tool_rollout,
    reduced_agent_native_catalog,
    summarize_native_tool_run,
)


def _result(status: NativeToolStatus, *, truncated: bool = False) -> AgentNativeToolResult:
    return AgentNativeToolResult(
        tool_id="native.test",
        status=status,
        argv=["true"],
        observed_at=datetime.now(timezone.utc),
        duration_ms=1,
        stdout="",
        stderr="",
        stdout_sha256="0" * 64,
        stderr_sha256="0" * 64,
        truncated=truncated,
        evidence_kind="TEST",
        sensitive=False,
    )


def test_canary_rollout_is_selector_bound_and_non_authoritative() -> None:
    catalog = reduced_agent_native_catalog()
    decision = decide_native_tool_rollout(
        robot_id="robot-a",
        run_id="run-1",
        mode="canary",
        catalog=catalog,
        robot_selectors=["robot-b"],
        run_selectors=[],
    )

    assert decision.selected is False
    assert decision.fallback_reason == "canary selectors did not match"
    assert decision.influences_release is False
    assert decision.tool_count == 22


def test_native_rollout_summary_counts_bounded_results() -> None:
    decision = decide_native_tool_rollout(
        robot_id="robot-a",
        run_id="run-1",
        mode="shadow",
        catalog=reduced_agent_native_catalog(),
    )
    summary = summarize_native_tool_run(
        decision,
        [_result(NativeToolStatus.SUCCEEDED), _result(NativeToolStatus.TIMEOUT, truncated=True)],
        session_id="native-session",
    )

    assert summary.session_id == "native-session"
    assert summary.call_count == 2
    assert summary.status_counts == {"SUCCEEDED": 1, "TIMEOUT": 1}
    assert summary.timeout_count == 1
    assert summary.truncated_count == 1
    assert summary.influences_release is False


def test_native_parity_report_detects_silent_drop() -> None:
    report = build_native_operation_parity_report(
        ["linux.host.status", "linux.process.list"],
        {"linux.host.status": "native.linux.host.inspect"},
        ["native.linux.host.inspect"],
    )

    assert report.status == "DIFF"
    assert report.mapped_operation_count == 1
    assert report.unmapped_operations == ["linux.process.list"]
    assert report.influences_release is False
