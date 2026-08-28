from __future__ import annotations

import hashlib
from collections.abc import Iterable, Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from rolo.agent_tools.native_tools import AgentNativeToolResult
from rolo.agent_tools.session import native_catalog_sha256

NativeToolRolloutMode = Literal["off", "shadow", "canary", "active"]


class NativeToolRolloutDecision(BaseModel):
    """Immutable per-run decision for exposing the native channel to an Agent."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-native-tool-rollout/v1"] = "rolo-native-tool-rollout/v1"
    robot_id: str = Field(min_length=1, max_length=128)
    run_id: str = Field(min_length=1, max_length=128)
    mode: NativeToolRolloutMode
    selected: bool
    selected_by: list[str] = Field(default_factory=list)
    catalog_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    tool_count: int = Field(ge=0)
    influences_release: Literal[False] = False
    fallback_reason: str | None = None


class NativeToolRunSummary(BaseModel):
    """Bounded native result summary suitable for rollout and parity dashboards."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-native-tool-run-summary/v1"] = "rolo-native-tool-run-summary/v1"
    robot_id: str = Field(min_length=1, max_length=128)
    run_id: str = Field(min_length=1, max_length=128)
    session_id: str | None = Field(default=None, min_length=1, max_length=128)
    mode: NativeToolRolloutMode
    selected: bool
    catalog_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    call_count: int = Field(ge=0)
    status_counts: dict[str, int] = Field(default_factory=dict)
    unavailable_count: int = Field(ge=0)
    timeout_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    rejected_count: int = Field(ge=0)
    truncated_count: int = Field(ge=0)
    environment_limited_count: int = Field(default=0, ge=0)
    influences_release: Literal[False] = False


class NativeToolParityReport(BaseModel):
    """Structural shadow report for command-shaped names versus family replacements."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-native-tool-parity/v1"] = "rolo-native-tool-parity/v1"
    source_operation_count: int = Field(ge=0)
    mapped_operation_count: int = Field(ge=0)
    unmapped_operations: list[str] = Field(default_factory=list)
    unknown_family_tools: list[str] = Field(default_factory=list)
    status: Literal["PASS", "DIFF"]
    influences_release: Literal[False] = False


class NativeToolExecutionParity(BaseModel):
    """Normalized parity result for one native call and its direct CLI probe."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-native-tool-execution-parity/v1"] = (
        "rolo-native-tool-execution-parity/v1"
    )
    tool_id: str
    native_status: str
    direct_status: str
    argv_match: bool
    stdout_match: bool
    stderr_match: bool
    status_match: bool
    status: Literal["PASS", "DIFF"]
    influences_release: Literal[False] = False


class NativeToolCanaryGateReport(BaseModel):
    """Release-neutral gate for deciding whether a selected native cohort is healthy."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-native-tool-canary-gate/v1"] = (
        "rolo-native-tool-canary-gate/v1"
    )
    robot_id: str
    run_id: str
    mode: NativeToolRolloutMode
    selected: bool
    status: Literal["PASS", "FAIL", "NOT_SELECTED"]
    blocking_reasons: list[str] = Field(default_factory=list)
    influences_release: Literal[False] = False


def decide_native_tool_rollout(
    *,
    robot_id: str,
    run_id: str,
    mode: NativeToolRolloutMode,
    catalog: Iterable[object],
    robot_selectors: Iterable[str] = (),
    run_selectors: Iterable[str] = (),
) -> NativeToolRolloutDecision:
    robot_selected = robot_id in set(robot_selectors)
    run_selected = run_id in set(run_selectors)
    selected_by = [
        name
        for name, selected in (("robot_id", robot_selected), ("run_id", run_selected))
        if selected
    ]
    selected = mode in {"shadow", "active"} or mode == "canary" and bool(selected_by)
    if selected and mode in {"shadow", "active"}:
        selected_by.insert(0, "mode")
    items = list(catalog)
    return NativeToolRolloutDecision(
        robot_id=robot_id,
        run_id=run_id,
        mode=mode,
        selected=selected,
        selected_by=selected_by,
        catalog_sha256=native_catalog_sha256(items),
        tool_count=len(items),
        fallback_reason=(
            "canary selectors did not match" if mode == "canary" and not selected else None
        ),
    )


def summarize_native_tool_run(
    decision: NativeToolRolloutDecision,
    results: Iterable[AgentNativeToolResult],
    *,
    session_id: str | None = None,
) -> NativeToolRunSummary:
    values = list(results)
    counts: dict[str, int] = {}
    for result in values:
        key = result.status.value
        counts[key] = counts.get(key, 0) + 1
    return NativeToolRunSummary(
        robot_id=decision.robot_id,
        run_id=decision.run_id,
        session_id=session_id,
        mode=decision.mode,
        selected=decision.selected,
        catalog_sha256=decision.catalog_sha256,
        call_count=len(values),
        status_counts=dict(sorted(counts.items())),
        unavailable_count=counts.get("UNAVAILABLE", 0),
        timeout_count=counts.get("TIMEOUT", 0),
        failed_count=counts.get("FAILED", 0),
        rejected_count=counts.get("REJECTED", 0),
        truncated_count=sum(result.truncated for result in values),
        environment_limited_count=sum(result.environment_limited for result in values),
    )


def _normalized_output(value: str) -> str:
    """Normalize line endings and trailing whitespace without changing content."""
    return "\n".join(line.rstrip() for line in value.replace("\r\n", "\n").split("\n")).rstrip(
        "\n"
    )


def compare_native_to_direct(
    result: AgentNativeToolResult,
    *,
    direct_argv: Sequence[str],
    direct_stdout: str = "",
    direct_stderr: str = "",
    direct_status: str | None = None,
    direct_return_code: int | None = None,
) -> NativeToolExecutionParity:
    """Compare a native result with a separately captured direct command.

    Callers may provide a semantic ``direct_status`` for unavailable or timed
    out probes; otherwise a zero return code is success and every other code is
    failure. Only normalized hashes are compared, so the parity artifact never
    duplicates potentially sensitive command output.
    """
    if direct_status is None:
        if direct_return_code is None:
            raise ValueError("direct_status or direct_return_code is required")
        direct_status = "SUCCEEDED" if direct_return_code == 0 else "FAILED"
    native_stdout = _normalized_output(result.stdout)
    native_stderr = _normalized_output(result.stderr)
    expected_stdout = _normalized_output(direct_stdout)
    expected_stderr = _normalized_output(direct_stderr)
    stdout_match = hashlib.sha256(native_stdout.encode("utf-8")).digest() == hashlib.sha256(
        expected_stdout.encode("utf-8")
    ).digest()
    stderr_match = hashlib.sha256(native_stderr.encode("utf-8")).digest() == hashlib.sha256(
        expected_stderr.encode("utf-8")
    ).digest()
    argv_match = list(result.argv) == list(direct_argv)
    status_match = result.status.value == direct_status
    return NativeToolExecutionParity(
        tool_id=result.tool_id,
        native_status=result.status.value,
        direct_status=direct_status,
        argv_match=argv_match,
        stdout_match=stdout_match,
        stderr_match=stderr_match,
        status_match=status_match,
        status="PASS" if argv_match and stdout_match and stderr_match and status_match else "DIFF",
    )


def evaluate_native_tool_canary_gate(
    summary: NativeToolRunSummary,
) -> NativeToolCanaryGateReport:
    """Evaluate a selected cohort without granting release authority."""
    if not summary.selected:
        return NativeToolCanaryGateReport(
            robot_id=summary.robot_id,
            run_id=summary.run_id,
            mode=summary.mode,
            selected=False,
            status="NOT_SELECTED",
            blocking_reasons=[],
        )
    reasons: list[str] = []
    if summary.failed_count:
        reasons.append(f"{summary.failed_count} native calls failed")
    if summary.rejected_count:
        reasons.append(f"{summary.rejected_count} native calls were rejected")
    if summary.truncated_count:
        reasons.append(f"{summary.truncated_count} native calls were truncated")
    non_environment_timeouts = max(
        0, summary.timeout_count - summary.environment_limited_count
    )
    if non_environment_timeouts:
        reasons.append(f"{non_environment_timeouts} native calls timed out")
    return NativeToolCanaryGateReport(
        robot_id=summary.robot_id,
        run_id=summary.run_id,
        mode=summary.mode,
        selected=True,
        status="PASS" if not reasons else "FAIL",
        blocking_reasons=reasons,
    )


def build_native_operation_parity_report(
    operations: Iterable[str],
    operation_family_map: dict[str, str],
    family_tool_ids: Iterable[str],
) -> NativeToolParityReport:
    expected = sorted(set(operations))
    known_families = set(family_tool_ids)
    unmapped = sorted(set(expected) - set(operation_family_map))
    unknown = sorted(set(operation_family_map.values()) - known_families)
    return NativeToolParityReport(
        source_operation_count=len(expected),
        mapped_operation_count=len(expected) - len(unmapped),
        unmapped_operations=unmapped,
        unknown_family_tools=unknown,
        status="PASS" if not unmapped and not unknown else "DIFF",
    )
