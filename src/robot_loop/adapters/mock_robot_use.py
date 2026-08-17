from __future__ import annotations

from robot_loop.models import (
    CandidateCause,
    ObservedFact,
    RobotUseRequest,
    RobotUseSupervision,
    RobotUseVerdict,
    TimeInterval,
)


class MockRobotUseBackend:
    """Deterministic offline stand-in for GPT; it performs no local image analysis."""

    name = "mock"

    async def evaluate(self, request: RobotUseRequest) -> RobotUseSupervision:
        telemetry = request.telemetry_summary
        progress = float(telemetry.get("progress_delta", 1.0))
        commanded_speed = float(telemetry.get("commanded_speed_mps", 0.0))

        if commanded_speed > 0.05 and progress < 0.01:
            return RobotUseSupervision(
                request_id=request.request_id,
                verdict=RobotUseVerdict.SUSPECTED_FAILURE,
                failure_type="NO_PHYSICAL_PROGRESS",
                first_abnormal_interval=TimeInterval(
                    start=request.window_start,
                    end=request.window_end,
                ),
                expected_behavior="Robot makes progress according to the task contract",
                observed_facts=[
                    ObservedFact(
                        frame_time=request.frames[-1].timestamp,
                        fact="Mock supervision scenario indicates no progress",
                    )
                ],
                candidate_causes=[CandidateCause(cause="controller stall", confidence=0.65)],
                requested_checks=[
                    "compare cmd_vel with encoder and IMU",
                    "check motor current for stall",
                ],
                confidence=0.85,
                limitations=["Mock backend does not inspect image content"],
                model="mock-robot-use-v1",
            )

        return RobotUseSupervision(
            request_id=request.request_id,
            verdict=RobotUseVerdict.NORMAL,
            expected_behavior="Robot follows the declared task contract",
            observed_facts=[
                ObservedFact(
                    frame_time=request.frames[-1].timestamp,
                    fact="Mock supervision completed without a configured anomaly",
                )
            ],
            confidence=0.8,
            limitations=["Mock backend does not inspect image content"],
            model="mock-robot-use-v1",
        )
