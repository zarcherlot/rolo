from datetime import datetime, timezone

import pytest

from rolo.core.models import DiscoveryReport, DiscoveryStatus, OperationCandidate, ProbeResult
from rolo.stages.adapt.active_discovery import ActiveDiscoveryReport
from rolo.stages.adapt.review import render_discovery_review_markdown
from rolo.stages.adapt.wiki import WikiNarrative, generate_robot_wiki
from rolo.stages.adapt.wiki_diff import build_wiki_discovery_diff
from rolo.stages.adapt.wiki_insights import (
    WikiHeuristicFinding,
    WikiInsightBundle,
    collect_wiki_insights,
)


class FakePolisher:
    provider = "fake"
    model = "fake-model"

    def polish(self, draft: str) -> WikiNarrative:
        assert "## 全栈摘要" in draft
        return WikiNarrative(
            overview="当前证据可用于工程梳理，但仍需现场确认。",
            evidence_limits=["未执行运动验证"],
            maintenance_priorities=["核对部署版本"],
        )


class FailingPolisher:
    provider = "fake"
    model = "broken-model"

    def polish(self, draft: str) -> WikiNarrative:
        raise RuntimeError("model unavailable")


def test_model_polishing_adds_only_bounded_narrative() -> None:
    draft = "# 机器人 Wiki：demo\n\n## 全栈摘要\n\n- 事实：unknown\n"

    wiki, metadata = generate_robot_wiki(draft, FakePolisher())

    assert "## 大模型润色摘要" in wiki
    assert "当前证据可用于工程梳理" in wiki
    assert "- 事实：unknown" in wiki
    assert metadata.status == "MODEL_POLISHED"
    assert metadata.provider == "fake"


def test_model_failure_falls_back_without_blocking_discovery() -> None:
    draft = "# 机器人 Wiki：demo\n\n## 全栈摘要\n"

    wiki, metadata = generate_robot_wiki(draft, FailingPolisher())

    assert wiki == draft
    assert metadata.status == "DETERMINISTIC_FALLBACK"
    assert metadata.fallback_reason == "model unavailable"


def _review_inputs() -> tuple[DiscoveryReport, ActiveDiscoveryReport]:
    now = datetime.now(timezone.utc)
    probes = {
        "hw": ProbeResult(
            layer="hw",
            status=DiscoveryStatus.SUCCEEDED,
            data={
                "compute_platform": "raspberry_pi",
                "architecture": "aarch64",
                "devices": [
                    {
                        "name": "video20",
                        "driver": "pispbe-input",
                        "path": "/dev/video20",
                    }
                ],
                "buses": {"usb": []},
            },
        ),
        "linux": ProbeResult(
            layer="linux",
            status=DiscoveryStatus.SUCCEEDED,
            data={"host": {"hostname": "robot", "system": "Linux", "release": "6.6"}},
        ),
        "ros": ProbeResult(
            layer="ros",
            status=DiscoveryStatus.UNAVAILABLE,
            data={"nodes": [], "topics": [], "services": [], "actions": []},
        ),
    }
    report = DiscoveryReport(
        discovery_id="disc-test",
        robot_id="demo",
        status=DiscoveryStatus.PARTIAL,
        platform={},
        capability_manifest={
            "expected_profile": {
                "platform": {"compute": "auto_discover", "drive_model": "unresolved"},
                "geometry": {},
                "features": {
                    "enrollment": {"unresolved_semantics": ["platform.drive_model"]},
                    "urdf_structure": {"links": [], "joints": []},
                    "urdf_hardware": {},
                },
            },
            "compatibility": {"status": "MATCH", "mismatches": []},
            "hardware_reconciliation": {"effective": []},
        },
        probes=probes,
        operation_candidates=[
            OperationCandidate(
                operation="app.teleop.velocity",
                semantic_bindings=["/controller/cmd_vel"],
            )
        ],
        created_at=now,
    )
    repeated_publishers = [{"name": "/controller/cmd_vel"} for _ in range(25)]
    active = ActiveDiscoveryReport.model_validate(
        {
            "discovery_id": "disc-test",
            "robot_id": "demo",
            "technical_status": "PARTIAL",
            "discovery_mode": {
                "level": "ARTIFACT_DOC",
                "confidence": "MEDIUM",
                "reason": "test",
            },
            "inputs": {},
            "coverage": {},
            "executables": [
                {
                    "executable_id": "exe-hook",
                    "name": "pythonpath_develop.ps1",
                    "path": "/workspace/build/demo/hook/pythonpath_develop.ps1",
                    "origin": "DISCOVERED_BUILD_ARTIFACT",
                },
                {
                    "executable_id": "exe-voice",
                    "name": "voice_control",
                    "path": "/workspace/build/voice/voice_control",
                    "origin": "DISCOVERED_BUILD_ARTIFACT",
                    "launch_analysis": {
                        "available": True,
                        "references": ["launch/voice.launch.py"],
                        "packages": ["voice"],
                        "nodes": ["voice_control"],
                    },
                    "communication": {
                        "ros": {"publishers": repeated_publishers},
                        "confidence": "LOW",
                    },
                    "safety": {"risk": "R0", "motion_possible": False},
                },
            ],
            "unattributed_source_interfaces": [
                {
                    "role": "publisher",
                    "name": "<symbol:diagnostic_topic>",
                    "type": "std_msgs::msg::String",
                    "source": "/workspace/src/diagnostic.cpp",
                    "name_source": "SYMBOLIC_EXPRESSION",
                }
            ],
            "dependency_summary": {},
            "unknowns": [
                "dependency declarations unavailable: exe-hook",
                "geometry.drive_model unavailable",
            ],
            "warnings": [],
            "created_at": now,
        }
    )
    return report, active


def test_engineer_wiki_filters_noise_deduplicates_and_marks_uncertainty() -> None:
    report, active = _review_inputs()

    wiki = render_discovery_review_markdown(report, active)

    assert "未发现明确冲突；关键项未获取，不能确认完全兼容" in wiki
    assert "环境/构建脚本 1 个" in wiki
    assert "### pythonpath_develop.ps1" not in wiki
    assert wiki.count("/controller/cmd_vel") < 5
    assert "需安全复核（发现运动线索）" in wiki
    assert "疑似聚合，需复核" in wiki
    assert "`app.teleop.velocity`" in wiki
    assert "`hw.firmware.update`" not in wiki
    assert "可通过构建/源码补采" in wiki
    assert "可启发式推断，需确认" in wiki
    assert "内部流水线端点" in wiki
    assert "/dev/video20" in wiki
    assert "尚无可验证的同机器人基线" in wiki
    assert "未归属静态接口：1 项" in wiki
    assert "### 未归属的静态接口" in wiki
    assert "<symbol:diagnostic_topic>" in wiki


def test_external_wiki_insights_are_bounded_to_the_same_discovery() -> None:
    report, active = _review_inputs()
    mismatched = WikiInsightBundle(
        robot_id="another-robot",
        discovery_id=report.discovery_id,
        findings=[
            WikiHeuristicFinding(
                category="MAINTENANCE",
                statement="需要核对版本。",
                confidence="LOW",
                basis=["agent review"],
                verification="由维护人员确认。",
                source="ADAPT_AGENT_SKILL",
            )
        ],
    )

    with pytest.raises(ValueError, match="does not match"):
        render_discovery_review_markdown(report, active, insight_bundle=mismatched)


def test_optional_insight_provider_failure_falls_back_to_builtin_rules() -> None:
    report, active = _review_inputs()

    class FailingInsightProvider:
        provider = "adapt-agent-skill"

        def infer(
            self,
            _report: DiscoveryReport,
            _active: ActiveDiscoveryReport,
        ) -> WikiInsightBundle:
            raise RuntimeError("agent unavailable")

    bundle, fallback_reason = collect_wiki_insights(
        report,
        active,
        FailingInsightProvider(),
    )

    assert fallback_reason == "agent unavailable"
    assert bundle.findings
    assert all(item.source == "DETERMINISTIC_RULE" for item in bundle.findings)


def test_wiki_diff_reports_engineer_relevant_changes() -> None:
    previous_report, previous_active = _review_inputs()
    report = previous_report.model_copy(
        update={
            "discovery_id": "disc-next",
            "operation_candidates": [],
        }
    )
    active = previous_active.model_copy(
        update={
            "discovery_id": "disc-next",
            "unknowns": ["geometry.drive_model unavailable"],
        }
    )

    diff = build_wiki_discovery_diff(report, active, previous_report, previous_active)

    assert diff.status == "CHANGED"
    assert diff.baseline_discovery_id == "disc-test"
    categories = {item.category for item in diff.changes}
    assert {"OPERATION", "UNKNOWN"} <= categories
