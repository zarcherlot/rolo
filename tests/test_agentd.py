from fastapi.testclient import TestClient

from robot_loop.agentd import create_agentd_app


def test_mock_agentd_is_scoped_to_one_robot() -> None:
    with TestClient(create_agentd_app("demo_diff")) as client:
        health = client.get("/health")
        capability = client.get("/v1/capability")
        snapshot = client.get("/v1/state/snapshot")

    assert health.json()["robot_id"] == "demo_diff"
    assert capability.json()["platform"]["drive_model"] == "differential"
    assert snapshot.json()["safety"]["watchdog"] == "ARMED"
