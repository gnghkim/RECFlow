from datetime import date

import pytest
from fastapi.testclient import TestClient

from api import create_app
from rec.fixture_client import FixtureClient, generate_fixtures
from rec.service import CollectorService


@pytest.fixture
def client(repo, tmp_path):
    generate_fixtures(tmp_path, date(2026, 7, 1), date(2026, 8, 6))
    service = CollectorService(repo, FixtureClient(tmp_path))
    return TestClient(create_app(service=service, repository=repo))


def test_health_reports_ok_with_no_runs(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["lastSuccessfulRun"] is None


def test_health_reports_last_successful_run(client):
    client.post("/jobs/collect", json={"tradeDate": "2026-08-06"})
    body = client.get("/health").json()
    assert body["lastSuccessfulRun"]["targetDate"] == "2026-08-06"


def test_collect_job_returns_outcome(client):
    response = client.post("/jobs/collect", json={"tradeDate": "2026-08-06"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "SUCCESS"
    assert body["rowsUpserted"] == 3


def test_collect_job_rejects_bad_date(client):
    assert client.post("/jobs/collect", json={"tradeDate": "not-a-date"}).status_code == 422
