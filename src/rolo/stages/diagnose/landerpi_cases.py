"""Minimal read-only Diagnose cases for the LanderPi application slice.

The contracts are OS/Middleware-neutral.  The collector merely uses a small,
fixed command allowlist against an enrolled target; all interpretation is
deterministic and remains auditable in the resulting finding.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from rolo.targets.executor import CommandResult, SshTargetExecutor

DiagnoseDecision = Literal["HEALTHY", "DEGRADED", "BLOCKED", "INCONCLUSIVE"]
DiagnoseChange = Literal["NO_CHANGE", "AUTHORIZED_TEST"]

_NAV_ACTIONS = {
    "/navigate_to_pose",
    "/compute_path_to_pose",
    "/spin",
    "/drive_on_heading",
}
_FLOAT = re.compile(
    r"(?<![A-Za-z0-9_])(?:[-+]?\d+(?:\.\d*)?(?:[eE][-+]?\d+)?|nan|inf)(?![A-Za-z0-9_])",
    re.I,
)
_HZ = re.compile(r"(?:average rate|average):\s*([0-9]+(?:\.[0-9]+)?)", re.I)
_TIMEOUT = re.compile(r"(?:ldlidar|laser|scan).*?(?:time\s*out|timeout)", re.I)


class DiagnoseFinding(BaseModel):
    """Stable case result consumed by an Agent and persisted by Rolo."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-diagnose-finding/v1"] = "rolo-diagnose-finding/v1"
    case_id: str = Field(pattern=r"^LP-D0[12]$")
    target_evidence_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    symptom: str = Field(min_length=1, max_length=512)
    hypothesis: str = Field(min_length=1, max_length=1024)
    evidence_refs: list[str] = Field(default_factory=list, max_length=32)
    contradicting_evidence_refs: list[str] = Field(default_factory=list, max_length=32)
    change: DiagnoseChange = "NO_CHANGE"
    smoke_result: str = Field(min_length=1, max_length=1024)
    decision: DiagnoseDecision
    next_probe: str = Field(min_length=1, max_length=512)
    limitations: list[str] = Field(default_factory=list, max_length=16)


class LPD01Observation(BaseModel):
    """Evidence needed to decide whether the navigation stack is running."""

    model_config = ConfigDict(extra="forbid")

    static_entrypoints: list[str] = Field(default_factory=list, max_length=128)
    runtime_nodes: list[str] = Field(default_factory=list, max_length=256)
    runtime_topics: list[str] = Field(default_factory=list, max_length=256)
    runtime_actions: list[str] = Field(default_factory=list, max_length=128)
    collection_errors: list[str] = Field(default_factory=list, max_length=16)

    @computed_field
    @property
    def static_navigation_present(self) -> bool:
        return any(
            any(token in item.casefold() for token in ("navigation", "nav2", "nav_"))
            for item in self.static_entrypoints
        )

    @computed_field
    @property
    def runtime_navigation_present(self) -> bool:
        return bool(_NAV_ACTIONS.intersection(self.runtime_actions))


class LPD02Observation(BaseModel):
    """Bounded sensor/log window; no single sample is treated as proof of health."""

    model_config = ConfigDict(extra="forbid")

    topic: str = "/scan"
    topic_type: str | None = None
    publisher_count: int | None = Field(default=None, ge=0)
    sample_count: int = Field(default=0, ge=0, le=256)
    valid_range_count: int = Field(default=0, ge=0)
    total_range_count: int = Field(default=0, ge=0)
    nan_count: int = Field(default=0, ge=0)
    inf_count: int = Field(default=0, ge=0)
    sample_intervals_s: list[float] = Field(default_factory=list, max_length=256)
    observed_frequency_hz: float | None = Field(default=None, ge=0)
    timeout_count: int = Field(default=0, ge=0)
    log_lines: list[str] = Field(default_factory=list, max_length=256)
    collection_errors: list[str] = Field(default_factory=list, max_length=16)

    @computed_field
    @property
    def valid_ratio(self) -> float | None:
        if self.total_range_count <= 0:
            return None
        return self.valid_range_count / self.total_range_count

    @computed_field
    @property
    def max_interval_s(self) -> float | None:
        return max(self.sample_intervals_s, default=None)


def evaluate_lp_d01(observation: LPD01Observation) -> DiagnoseFinding:
    """Classify navigation availability without confusing static code with runtime."""

    static = observation.static_navigation_present
    runtime = observation.runtime_navigation_present
    refs = ["static_entrypoints"] if static else []
    if runtime:
        return DiagnoseFinding(
            case_id="LP-D01",
            symptom="navigation command discovery",
            hypothesis="navigation runtime endpoints are present in the current graph",
            evidence_refs=[*refs, "runtime_actions"],
            change="NO_CHANGE",
            smoke_result="read-only action graph contains a navigation endpoint",
            decision="HEALTHY",
            next_probe="inspect lifecycle and route binding before any write or task motion",
            limitations=[
                "runtime action presence does not prove localization, map, or physical safety"
            ],
        )
    if static:
        return DiagnoseFinding(
            case_id="LP-D01",
            symptom="navigation command discovery",
            hypothesis=(
                "navigation sources/configuration exist, but the baseline bring-up did not "
                "start the navigation runtime"
            ),
            evidence_refs=["static_entrypoints", "runtime_actions"],
            change="NO_CHANGE",
            smoke_result="no navigation action endpoint observed in the baseline graph",
            decision="DEGRADED",
            next_probe="run a controlled, Nav-only bring-up with lease, timeout, and cleanup",
            limitations=[
                "do not infer that a package is runnable until its dependencies and lifecycle "
                "are observed"
            ],
        )
    return DiagnoseFinding(
        case_id="LP-D01",
        symptom="navigation command discovery",
        hypothesis="navigation entrypoints were not found in the bounded target scan",
        evidence_refs=["static_entrypoints", "runtime_actions"],
        change="NO_CHANGE",
        smoke_result="neither static navigation entrypoint nor runtime action was observed",
        decision="BLOCKED" if not observation.collection_errors else "INCONCLUSIVE",
        next_probe=(
            "expand the target-bound workspace scan or provide an explicit middleware provider "
            "hint"
        ),
        limitations=["bounded scan is not a full-disk proof", *observation.collection_errors],
    )


def evaluate_lp_d02(observation: LPD02Observation) -> DiagnoseFinding:
    """Classify a bounded LaserScan/log window using conservative thresholds."""

    ratio = observation.valid_ratio
    healthy_window = (
        observation.sample_count >= 3
        and ratio is not None
        and ratio >= 0.90
        and observation.timeout_count == 0
        and (observation.max_interval_s is None or observation.max_interval_s <= 0.25)
    )
    refs = ["scan_window", "log_window"]
    if healthy_window:
        return DiagnoseFinding(
            case_id="LP-D02",
            symptom="range sensor timeout or data degradation",
            hypothesis="the sensor produced a stable, sufficiently valid observation window",
            evidence_refs=refs,
            change="NO_CHANGE",
            smoke_result=(
                "at least three samples, >=90% valid ranges, no timeout log, bounded cadence"
            ),
            decision="HEALTHY",
            next_probe="recheck route and localization prerequisites before navigation motion",
            limitations=["sensor health is not a navigation or physical-safety certificate"],
        )
    reasons = []
    if observation.sample_count < 3:
        reasons.append("fewer than three samples")
    if ratio is None:
        reasons.append("range quality could not be computed")
    elif ratio < 0.90:
        reasons.append(f"valid range ratio {ratio:.3f} is below 0.900")
    if observation.timeout_count:
        reasons.append(f"{observation.timeout_count} timeout log line(s)")
    if observation.max_interval_s is not None and observation.max_interval_s > 0.25:
        reasons.append(f"sample interval {observation.max_interval_s:.3f}s exceeds 0.250s")
    return DiagnoseFinding(
        case_id="LP-D02",
        symptom="range sensor timeout or data degradation",
        hypothesis=(
            "sensor output is present but the bounded window shows degraded quality or driver "
            "timeout"
        ),
        evidence_refs=refs,
        change="NO_CHANGE",
        smoke_result="; ".join(reasons) or "insufficient evidence for a healthy window",
        decision=(
            "DEGRADED" if observation.sample_count or observation.timeout_count else "INCONCLUSIVE"
        ),
        next_probe=(
            "inspect driver/transport health; do not restart or change parameters automatically"
        ),
        limitations=[
            "a bounded topic sample cannot prove obstacle-detection safety",
            *observation.collection_errors,
        ],
    )


class LanderPiDiagnoseCollector:
    """Run only fixed, bounded, read-only commands on an enrolled target."""

    def __init__(self, executor: SshTargetExecutor) -> None:
        self.executor = executor

    @staticmethod
    def _lines(result: CommandResult) -> list[str]:
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    def collect_lp_d01(self) -> LPD01Observation:
        workspace = str(self.executor.target.workspace)
        # Query names directly instead of dumping a workspace listing: the
        # executor bounds stdout, so a broad scan could hide the only useful
        # navigation entrypoint behind unrelated files.
        static_results = [
            self.executor.run_readonly(
                [
                    "find",
                    f"{workspace}/src",
                    "-maxdepth",
                    "6",
                    "-type",
                    "f",
                    "-iname",
                    pattern,
                    "-print",
                ]
            )
            for pattern in ("*navigation*", "*nav2*", "*map*.yaml")
        ]
        nodes = self.executor.run_readonly(["ros2", "node", "list"])
        topics = self.executor.run_readonly(["ros2", "topic", "list"])
        actions = self.executor.run_readonly(["ros2", "action", "list"])
        errors = [
            f"{name}: exit {result.returncode}"
            for name, result in (
                [(f"static_{index}", result) for index, result in enumerate(static_results, 1)]
                + [("nodes", nodes), ("topics", topics), ("actions", actions)]
            )
            if result.returncode != 0
        ]
        return LPD01Observation(
            static_entrypoints=[line for result in static_results for line in self._lines(result)],
            runtime_nodes=self._lines(nodes),
            runtime_topics=self._lines(topics),
            runtime_actions=self._lines(actions),
            collection_errors=errors,
        )

    def collect_lp_d02(self) -> LPD02Observation:
        logs = self.executor.run_readonly(["docker", "logs", "--tail", "200", "MentorPi"])
        if logs.returncode != 0:
            logs = self.executor.run_readonly(["journalctl", "-n", "200", "--no-pager"])
        info = self.executor.run_readonly(["ros2", "topic", "info", "/scan"])
        hz = self.executor.run_readonly(
            ["timeout", "6", "ros2", "topic", "hz", "/scan", "--window", "5"]
        )
        sample = self.executor.run_readonly(
            ["ros2", "topic", "echo", "--once", "/scan", "--field", "ranges"]
        )
        lines = self._lines(logs)
        values = [token.casefold() for token in _FLOAT.findall(sample.stdout)]
        nan_count = sum(value == "nan" for value in values)
        inf_count = sum(value in {"inf", "+inf", "-inf"} for value in values)
        valid_count = len(values) - nan_count - inf_count
        hz_match = _HZ.search(hz.stdout)
        publisher = re.search(r"Publisher count:\s*(\d+)", info.stdout, re.I)
        errors = [
            f"{name}: exit {result.returncode}"
            for name, result in (
                ("logs", logs),
                ("topic_info", info),
                ("topic_hz", hz),
                ("topic_sample", sample),
            )
            if result.returncode != 0
        ]
        type_match = re.search(r"Type:\s*([^\s]+)", info.stdout, re.I)
        return LPD02Observation(
            topic_type=type_match.group(1) if type_match else None,
            publisher_count=int(publisher.group(1)) if publisher else None,
            sample_count=1 if values else 0,
            valid_range_count=valid_count,
            total_range_count=len(values),
            nan_count=nan_count,
            inf_count=inf_count,
            observed_frequency_hz=float(hz_match.group(1)) if hz_match else None,
            timeout_count=sum(1 for line in lines if _TIMEOUT.search(line)),
            log_lines=lines,
            collection_errors=errors,
        )
