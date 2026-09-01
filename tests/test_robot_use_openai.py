from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from rolo.core.models import ImageFrame, RobotUseRequest, RobotUseVerdict
from rolo.integrations.robot_use import openai as openai_backend


def make_request(*, image_url: str | None = "data:image/png;base64,AA==") -> RobotUseRequest:
    now = datetime.now(timezone.utc)
    return RobotUseRequest(
        request_id="req-openai",
        robot_id="demo",
        execution_id="exec-1",
        window_start=now - timedelta(seconds=2),
        window_end=now,
        frames=[ImageFrame(timestamp=now, image_url=image_url, artifact_ref="artifact://frame")]
        if image_url
        else [ImageFrame(timestamp=now, artifact_ref="artifact://frame")],
        task_contract={"intent": "navigate"},
        telemetry_summary={"progress_delta": 0.2},
    )


def test_openai_backend_validates_configuration_and_prompt() -> None:
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        openai_backend.OpenAIRobotUseBackend(api_key="", model="gpt")
    with pytest.raises(ValueError, match="OPENAI_MODEL"):
        openai_backend.OpenAIRobotUseBackend(api_key="key", model="")

    request = make_request()
    prompt = openai_backend.OpenAIRobotUseBackend._prompt(request)
    assert "semantic visual supervisor" in prompt
    assert '"request_id": "req-openai"' in prompt
    assert "frames" not in prompt


@pytest.mark.asyncio
async def test_openai_backend_evaluates_structured_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response_json = (
        '{"request_id":"provider-request","model":"provider-model",'
        '"verdict":"NORMAL","expected_behavior":"move","confidence":0.9,'
        '"observed_facts":[],"candidate_causes":[],"requested_checks":[],"limitations":[]}'
    )

    class Responses:
        async def create(self, **kwargs):
            assert kwargs["model"] == "vision-model"
            assert kwargs["input"][0]["content"][1]["type"] == "input_text"
            assert kwargs["input"][0]["content"][2]["type"] == "input_image"
            return SimpleNamespace(output_text=response_json, id="resp-1")

    class Client:
        def __init__(self, **kwargs):
            assert kwargs == {"api_key": "key"}
            self.responses = Responses()

    monkeypatch.setattr(openai_backend, "AsyncOpenAI", Client)
    backend = openai_backend.OpenAIRobotUseBackend(api_key="key", model="vision-model")
    result = await backend.evaluate(make_request())
    assert result.request_id == "req-openai"
    assert result.model == "vision-model"
    assert result.model_response_id == "resp-1"
    assert result.verdict is RobotUseVerdict.NORMAL


@pytest.mark.asyncio
async def test_openai_backend_requires_resolved_image_url(monkeypatch: pytest.MonkeyPatch) -> None:
    class Client:
        def __init__(self, **kwargs):
            self.responses = SimpleNamespace(create=None)

    monkeypatch.setattr(openai_backend, "AsyncOpenAI", Client)
    backend = openai_backend.OpenAIRobotUseBackend(api_key="key", model="vision-model")
    with pytest.raises(ValueError, match="requires image_url/data URI"):
        await backend.evaluate(make_request(image_url=None))
