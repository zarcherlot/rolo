from __future__ import annotations

from collections.abc import Iterable
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
) -> NativeToolRunSummary:
    values = list(results)
    counts: dict[str, int] = {}
    for result in values:
        key = result.status.value
        counts[key] = counts.get(key, 0) + 1
    return NativeToolRunSummary(
        robot_id=decision.robot_id,
        run_id=decision.run_id,
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
