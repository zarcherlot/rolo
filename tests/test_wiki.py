from rolo.stages.adapt.wiki import WikiNarrative, generate_robot_wiki


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
