from pathlib import Path

from fastapi.testclient import TestClient

from rolo.api import app
from rolo.core.config import get_settings
from rolo.jobs import JobStatus, JobStore


def _robots_config(tmp_path: Path) -> None:
    robots = tmp_path / "config" / "robots"
    robots.mkdir(parents=True)
    fixture_root = Path(__file__).parent / "fixtures" / "robots"
    for fixture in fixture_root.glob("*.yaml"):
        (robots / fixture.name).write_text(
            fixture.read_text(encoding="utf-8"), encoding="utf-8"
        )


def test_job_service_api_exposes_shared_pages_and_recovery(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ROLO_CONFIG_DIR", str(tmp_path / "config"))
    get_settings.cache_clear()
    _robots_config(tmp_path)
    store = JobStore(tmp_path / "config" / "jobs")
    job = store.create("target.inspect", "local:C:/robot")
    store.append_event(job.job_id, "STARTED", JobStatus.RUNNING, expected_revision=0)

    with TestClient(app) as client:
        listed = client.get("/v1/jobs")
        recovered = client.get(f"/v1/jobs/{job.job_id}")
        events = client.get(f"/v1/jobs/{job.job_id}/events?limit=1")
        missing = client.get("/v1/jobs/job_missing/events")

    assert listed.status_code == 200
    assert listed.json()["items"][0]["job_id"] == job.job_id
    assert recovered.status_code == 200
    assert recovered.json()["job"]["job_id"] == job.job_id
    assert events.status_code == 200
    assert events.json()["total"] == 1
    assert events.json()["next_offset"] is None
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "JOB_NOT_FOUND"
    get_settings.cache_clear()


def test_job_api_scope_is_enforced_when_scopes_are_configured(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("ROLO_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("ROLO_API_TOKEN", "token")
    monkeypatch.setenv("ROLO_API_TOKEN_SCOPES", "robots:read")
    get_settings.cache_clear()
    _robots_config(tmp_path)
    with TestClient(app) as client:
        denied = client.get("/v1/jobs", headers={"Authorization": "Bearer token"})
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "SCOPE_REQUIRED"
    get_settings.cache_clear()
