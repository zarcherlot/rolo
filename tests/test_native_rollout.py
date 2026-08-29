from datetime import datetime, timezone

from rolo.agent_tools import (
    AgentNativeToolResult,
    NativeToolStatus,
    build_native_operation_parity_report,
    compare_native_to_direct,
    decide_native_tool_rollout,
    evaluate_native_tool_canary_gate,
    reduced_agent_native_catalog,
    summarize_native_tool_run,
)


def _result(
    status: NativeToolStatus,
    *,
    truncated: bool = False,
    environment_limited: bool = False,
) -> AgentNativeToolResult:
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
        environment_limited=environment_limited,
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

    shadow = decide_native_tool_rollout(
        robot_id="robot-a",
        run_id="run-1",
        mode="shadow",
        catalog=catalog,
    )
    assert shadow.selected_by == ["mode"]


def test_native_rollout_summary_counts_bounded_results() -> None:
    decision = decide_native_tool_rollout(
        robot_id="robot-a",
        run_id="run-1",
        mode="shadow",
        catalog=reduced_agent_native_catalog(),
    )
    summary = summarize_native_tool_run(
        decision,
        [
            _result(NativeToolStatus.SUCCEEDED),
            _result(NativeToolStatus.TIMEOUT, truncated=True, environment_limited=True),
        ],
        session_id="native-session",
    )

    assert summary.session_id == "native-session"
    assert summary.call_count == 2
    assert summary.status_counts == {"SUCCEEDED": 1, "TIMEOUT": 1}
    assert summary.timeout_count == 1
    assert summary.truncated_count == 1
    assert summary.environment_limited_count == 1
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


def test_execution_parity_normalizes_line_endings_and_trailing_space() -> None:
    result = _result(NativeToolStatus.SUCCEEDED)
    result = result.model_copy(update={"argv": ["uname", "-a"], "stdout": "host\n"})

    parity = compare_native_to_direct(
        result,
        direct_argv=["uname", "-a"],
        direct_stdout="host\r\n",
        direct_stderr="",
        direct_return_code=0,
    )

    assert parity.status == "PASS"
    assert parity.stdout_match is True
    assert parity.argv_match is True


def test_canary_gate_allows_environment_limited_timeout_but_blocks_real_timeout() -> None:
    decision = decide_native_tool_rollout(
        robot_id="robot-a",
        run_id="run-1",
        mode="canary",
        catalog=reduced_agent_native_catalog(),
        robot_selectors=["robot-a"],
    )
    summary = summarize_native_tool_run(
        decision,
        [_result(NativeToolStatus.TIMEOUT, environment_limited=True)],
    )
    assert evaluate_native_tool_canary_gate(summary).status == "PASS"

    blocked = summarize_native_tool_run(
        decision,
        [_result(NativeToolStatus.TIMEOUT)],
    )
    gate = evaluate_native_tool_canary_gate(blocked)
    assert gate.status == "FAIL"
    assert "timed out" in gate.blocking_reasons[0]


def test_selected_native_gate_blocks_zero_calls_and_execution_parity_diff() -> None:
    decision = decide_native_tool_rollout(
        robot_id="robot-a",
        run_id="run-1",
        mode="shadow",
        catalog=reduced_agent_native_catalog(),
    )
    empty = summarize_native_tool_run(decision, [])
    empty_gate = evaluate_native_tool_canary_gate(empty)
    assert empty_gate.status == "FAIL"
    assert "no calls" in empty_gate.blocking_reasons[0]

    result = _result(NativeToolStatus.SUCCEEDED).model_copy(
        update={"argv": ["uname", "-a"], "stdout": "native\n"}
    )
    summary = summarize_native_tool_run(decision, [result])
    parity = compare_native_to_direct(
        result,
        direct_argv=["uname", "-a"],
        direct_stdout="direct\n",
        direct_stderr="",
        direct_return_code=0,
    )
    gate = evaluate_native_tool_canary_gate(summary, [parity])
    assert gate.status == "FAIL"
    assert "parity" in gate.blocking_reasons[0]
