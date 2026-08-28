from __future__ import annotations

from fastapi.testclient import TestClient

from rolo.vis import create_vis_app


def test_rolo_vis_dashboard_is_same_origin_and_exposes_no_mutation_form() -> None:
    with TestClient(create_vis_app()) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "rolo-vis" in response.text
    assert "/v1/robots/" in response.text
    assert "authorization_ref" in response.text
    assert "window.confirm" in response.text
