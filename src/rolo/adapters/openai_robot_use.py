from __future__ import annotations

import json

from openai import AsyncOpenAI

from rolo.core.models import RobotUseRequest, RobotUseSupervision


class OpenAIRobotUseBackend:
    name = "openai"

    def __init__(self, *, api_key: str, model: str) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for the OpenAI robot_use backend")
        if not model:
            raise ValueError("OPENAI_MODEL is required for the OpenAI robot_use backend")
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def evaluate(self, request: RobotUseRequest) -> RobotUseSupervision:
        content: list[dict[str, object]] = [
            {
                "type": "input_text",
                "text": self._prompt(request),
            }
        ]
        for frame in request.frames:
            if not frame.image_url:
                raise ValueError(
                    "OpenAI backend requires image_url/data URI for every frame; "
                    "resolve artifact_ref before evaluation"
                )
            content.append(
                {
                    "type": "input_text",
                    "text": f"Frame timestamp: {frame.timestamp.isoformat()}",
                }
            )
            content.append(
                {
                    "type": "input_image",
                    "image_url": frame.image_url,
                    "detail": "low",
                }
            )

        schema = RobotUseSupervision.model_json_schema()
        response = await self._client.responses.create(
            model=self._model,
            input=[{"role": "user", "content": content}],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "robot_use_supervision",
                    "schema": schema,
                    "strict": True,
                }
            },
        )
        result = RobotUseSupervision.model_validate_json(response.output_text)
        return result.model_copy(
            update={
                "request_id": request.request_id,
                "model": self._model,
                "model_response_id": response.id,
            }
        )

    @staticmethod
    def _prompt(request: RobotUseRequest) -> str:
        context = request.model_dump(mode="json", exclude={"frames"})
        return (
            "You are the semantic visual supervisor for robot_use mode. Compare the "
            "timestamped storyboard against the task contract and telemetry. Separate directly "
            "observed facts from candidate causes. Do not claim collision, absolute position, or "
            "hardware state unless visible or corroborated. Return UNKNOWN when evidence is "
            "insufficient. You have no safety authority and must emit exactly the requested "
            "structured schema.\n\nExecution context:\n"
            + json.dumps(context, ensure_ascii=False, indent=2)
        )
