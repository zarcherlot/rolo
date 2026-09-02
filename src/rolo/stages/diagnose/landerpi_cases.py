"""Minimal read-only Diagnose cases for the LanderPi application slice.

The contracts are OS/Middleware-neutral.  The collector merely uses a small,
fixed command allowlist against an enrolled target; all interpretation is
deterministic and remains auditable in the resulting finding.
"""

from __future__ import annotations

import re
import subprocess
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
    case_id: str = Field(pattern=r"^LP-D0[123]$")
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


class LPD03Observation(BaseModel):
    """Evidence for global navigation prerequisites, without mutating pose state."""

    model_config = ConfigDict(extra="forbid")

    tf_frames: list[str] = Field(default_factory=list, max_length=256)
    runtime_topics: list[str] = Field(default_factory=list, max_length=256)
    map_to_base_footprint_available: bool = False
    map_topic_present: bool = False
    map_publisher_count: int | None = Field(default=None, ge=0)
    localization_nodes: list[str] = Field(default_factory=list, max_length=64)
    localization_lifecycle: dict[str, str] = Field(default_factory=dict, max_length=16)
    initial_pose_observed: bool = False
    collection_errors: list[str] = Field(default_factory=list, max_length=16)


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


def evaluate_lp_d03(observation: LPD03Observation) -> DiagnoseFinding:
    """Classify global-localization readiness; relative motion is out of scope."""

    localization_active = any(
        state.casefold() in {"active", "activated"}
        for state in observation.localization_lifecycle.values()
    )
    map_ready = (
        observation.map_to_base_footprint_available
        and observation.map_topic_present
        and (observation.map_publisher_count is None or observation.map_publisher_count > 0)
        and bool(observation.localization_nodes)
        and localization_active
        and observation.initial_pose_observed
    )
    refs = ["tf_map_to_base_footprint", "map_topic", "localization", "initial_pose"]
    if map_ready:
        return DiagnoseFinding(
            case_id="LP-D03",
            symptom="global navigation pose prerequisite",
            hypothesis="map, localization, and an initial pose are observable in the target runtime",
            evidence_refs=refs,
            change="NO_CHANGE",
            smoke_result="map→base_footprint TF, map publisher, active localization, and initial pose observed",
            decision="HEALTHY",
            next_probe="recheck navigation action route and run only an explicitly bounded motion canary",
            limitations=["read-only readiness does not prove localization accuracy or task-level safety"],
        )
    if observation.collection_errors and not (
        observation.tf_frames
        or observation.runtime_topics
        or observation.map_topic_present
        or observation.localization_nodes
    ):
        decision: DiagnoseDecision = "INCONCLUSIVE"
    else:
        decision = "BLOCKED"
    missing = []
    if not observation.map_topic_present:
        missing.append("/map publisher")
    if not observation.map_to_base_footprint_available:
        missing.append("map→base_footprint TF")
    if not observation.localization_nodes:
        missing.append("localization node")
    if not localization_active:
        missing.append("active localization lifecycle")
    if not observation.initial_pose_observed:
        missing.append("initial pose")
    return DiagnoseFinding(
        case_id="LP-D03",
        symptom="global navigation pose prerequisite",
        hypothesis="global navigation prerequisites are incomplete; relative motion must not be interpreted as global navigation",
        evidence_refs=refs,
        change="NO_CHANGE",
        smoke_result="missing: " + ", ".join(missing),
        decision=decision,
        next_probe="discover an explicit, target-bound relocalization/initial-pose operation; do not publish a guessed pose",
        limitations=[
            "no initial pose or parameter changes were attempted",
            "relative odometry can remain usable while global navigation is blocked",
            *observation.collection_errors,
        ],
    )


class LanderPiDiagnoseCollector:
    """Run only fixed, bounded, read-only commands on an enrolled target."""

    def __init__(self, executor: SshTargetExecutor) -> None:
        self.executor = executor

    def _run(self, argv: list[str]) -> CommandResult:
        """Turn one bounded probe timeout into evidence instead of crashing the case."""
        try:
            return self.executor.run_readonly(argv)
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            return CommandResult(argv=tuple(argv), returncode=124, stderr=str(exc)[:1000])

    @staticmethod
    def _lines(result: CommandResult) -> list[str]:
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    def collect_lp_d01(self) -> LPD01Observation:
        workspace = str(self.executor.target.workspace)
        # Query names directly instead of dumping a workspace listing: the
        # executor bounds stdout, so a broad scan could hide the only useful
        # navigation entrypoint behind unrelated files.
        static_results = [
            self._run(
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
        nodes = self._run(["ros2", "node", "list"])
        topics = self._run(["ros2", "topic", "list"])
        actions = self._run(["ros2", "action", "list"])
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
        logs = self._run(["docker", "logs", "--tail", "200", "MentorPi"])
        if logs.returncode != 0:
            logs = self._run(["journalctl", "-n", "200", "--no-pager"])
        info = self._run(["ros2", "topic", "info", "/scan"])
        hz = self._run(
            ["timeout", "6", "ros2", "topic", "hz", "/scan", "--window", "5"]
        )
        sample_results = [
            self._run(["ros2", "topic", "echo", "--once", "/scan", "--field", "ranges"])
            for _ in range(3)
        ]
        lines = self._lines(logs)
        values = [
            token.casefold()
            for sample in sample_results
            for token in _FLOAT.findall(sample.stdout)
        ]
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
                *[(f"topic_sample_{index}", sample) for index, sample in enumerate(sample_results, 1)],
            )
            if result.returncode != 0
            and not (name == "topic_hz" and result.returncode == 124 and result.stdout)
        ]
        type_match = re.search(r"Type:\s*([^\s]+)", info.stdout, re.I)
        return LPD02Observation(
            topic_type=type_match.group(1) if type_match else None,
            publisher_count=int(publisher.group(1)) if publisher else None,
            sample_count=sum(1 for sample in sample_results if sample.stdout.strip()),
            valid_range_count=valid_count,
            total_range_count=len(values),
            nan_count=nan_count,
            inf_count=inf_count,
            observed_frequency_hz=float(hz_match.group(1)) if hz_match else None,
            timeout_count=sum(1 for line in lines if _TIMEOUT.search(line)),
            log_lines=lines,
            collection_errors=errors,
        )

    def collect_lp_d03(self) -> LPD03Observation:
        topics = self._run(["ros2", "topic", "list"])
        nodes = self._run(["ros2", "node", "list"])
        map_info = self._run(["ros2", "topic", "info", "/map"])
        pose = self._run(
            ["timeout", "4", "ros2", "topic", "echo", "--once", "/initialpose"]
        )
        tf = self._run(
            ["timeout", "4", "ros2", "run", "tf2_ros", "tf2_echo", "map", "base_footprint"]
        )
        relative_tf = self._run(
            ["timeout", "4", "ros2", "run", "tf2_ros", "tf2_echo", "odom", "base_footprint"]
        )
        topic_lines = self._lines(topics)
        node_lines = self._lines(nodes)
        localization = [
            item
            for item in node_lines
            if any(token in item.casefold() for token in ("amcl", "localiz", "slam_toolbox"))
        ]
        lifecycle: dict[str, str] = {}
        for node in localization[:8]:
            name = node.lstrip("/")
            state = self._run(["ros2", "lifecycle", "get", f"/{name}"])
            match = re.search(r"(active|inactive|unconfigured|finalized)", state.stdout, re.I)
            if match:
                lifecycle[node] = match.group(1).upper()
        publisher = re.search(r"Publisher count:\s*(\d+)", map_info.stdout, re.I)
        errors = [
            f"{name}: exit {result.returncode}"
            for name, result in (
                ("topic_list", topics),
                ("node_list", nodes),
                ("map_info", map_info),
                ("initial_pose", pose),
                ("tf_echo", tf),
                ("relative_tf_echo", relative_tf),
            )
            if result.returncode != 0
            and not (name in {"initial_pose", "tf_echo"} and result.returncode == 124 and result.stdout)
        ]
        return LPD03Observation(
            tf_frames=(
                ["map", "base_footprint"]
                if "Translation:" in tf.stdout and "Rotation:" in tf.stdout
                else []
            )
            + (["odom", "base_footprint"] if "Translation:" in relative_tf.stdout else []),
            runtime_topics=topic_lines,
            map_to_base_footprint_available=("Translation:" in tf.stdout and "Rotation:" in tf.stdout),
            map_topic_present="/map" in topic_lines,
            map_publisher_count=int(publisher.group(1)) if publisher else None,
            localization_nodes=localization,
            localization_lifecycle=lifecycle,
            initial_pose_observed=bool(pose.stdout.strip()),
            collection_errors=errors,
        )
