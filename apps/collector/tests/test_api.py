import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api import create_app
from rec.models import ApiResponse
from rec.service import CollectorService
from tests.conftest import make_response

SAMPLES = Path(__file__).parent / "samples"


class SampleSource:
    source_name = "sample"

    def fetch(self, page: int = 1) -> ApiResponse:
        if page > 1:
            return make_response()
        payload = json.loads((SAMPLES / "rec_response_sample.json").read_text(encoding="utf-8"))
        return ApiResponse(payload=payload, http_status=200, endpoint="sample://real")


@pytest.fixture
def client(repo):
    service = CollectorService(repo, SampleSource())
    return TestClient(create_app(service=service, repository=repo))


def test_health_reports_ok_with_no_runs(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["lastSuccessfulRun"] is None


def test_health_reports_last_successful_run(client):
    client.post("/jobs/collect", json={})
    body = client.get("/health").json()
    assert body["lastSuccessfulRun"]["targetDate"] == "2026-08-11"


def test_collect_job_returns_outcome(client):
    response = client.post("/jobs/collect", json={})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "SUCCESS"
    assert body["rowsUpserted"] == 9
    assert body["tradeDates"] == 3
    assert body["latestTradeDate"] == "2026-08-11"


def test_collect_job_accepts_empty_body(client):
    """이 API는 날짜 필터가 없어 요청 본문이 필요 없다."""
    assert client.post("/jobs/collect").status_code == 200
