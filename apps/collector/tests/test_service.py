import json
from datetime import date
from pathlib import Path

import pytest

from rec.fixture_client import FixtureClient, generate_fixtures
from rec.models import ApiResponse
from rec.service import CollectorService
from tests.conftest import make_response

SAMPLES = Path(__file__).parent / "samples"


class StaticSource:
    """정해진 응답을 한 번만 주고 이후 빈 페이지를 주는 소스."""

    source_name = "static"

    def __init__(self, first: ApiResponse) -> None:
        self._first = first

    def fetch(self, page: int = 1) -> ApiResponse:
        return self._first if page == 1 else make_response()


def real_sample_source() -> StaticSource:
    payload = json.loads((SAMPLES / "rec_response_sample.json").read_text(encoding="utf-8"))
    return StaticSource(ApiResponse(payload=payload, http_status=200, endpoint="sample://real"))


@pytest.fixture
def fixture_source(tmp_path):
    generate_fixtures(tmp_path, date(2026, 6, 1), date(2026, 8, 11))
    return FixtureClient(tmp_path)


def test_collect_stores_all_trade_dates(repo):
    """실제 응답 샘플에는 거래일 3일이 들어 있고 각 거래일이 세 행이 된다."""
    outcome = CollectorService(repo, real_sample_source()).collect()
    assert outcome.status == "SUCCESS"
    assert outcome.trade_dates == 3
    assert outcome.rows_upserted == 9
    assert repo.count_market_rows() == 9


def test_collect_records_latest_trade_date(repo):
    outcome = CollectorService(repo, real_sample_source()).collect()
    assert outcome.latest_trade_date == date(2026, 8, 11)


def test_collect_is_idempotent(repo):
    """이 API는 매번 전체를 준다. 여러 번 받아도 행이 늘면 안 된다."""
    service = CollectorService(repo, real_sample_source())
    service.collect()
    service.collect()
    assert repo.count_market_rows() == 9
    assert repo.count_raw_rows() == 2  # 원본은 호출마다 남는다


def test_collect_saves_raw_before_mapping(repo):
    """매핑이 실패해도 원본이 남아야 재처리로 복구할 수 있다."""

    class BrokenSource:
        source_name = "broken"

        def fetch(self, page: int = 1) -> ApiResponse:
            return make_response([{"unexpectedKey": "x"}])

    outcome = CollectorService(repo, BrokenSource()).collect()
    assert outcome.status == "FAILED"
    assert repo.count_raw_rows() == 1
    assert repo.count_market_rows() == 0


def test_gateway_error_is_reported(repo):
    """경로가 틀리면 게이트웨이 오류가 온다. 사유가 이력에 남아야 한다."""

    class GatewaySource:
        source_name = "gateway"

        def fetch(self, page: int = 1) -> ApiResponse:
            return ApiResponse(
                payload={
                    "OpenAPI_ServiceResponse": {
                        "cmmMsgHeader": {
                            "errMsg": "NO_OPENAPI_SERVICE_ERROR",
                            "returnAuthMsg": "해당 오픈API 서비스가 없거나 폐기됨",
                            "returnReasonCode": "12",
                        }
                    }
                },
                http_status=400,
                endpoint="wrong://path",
            )

    outcome = CollectorService(repo, GatewaySource()).collect()
    assert outcome.status == "FAILED"
    assert any("NO_OPENAPI_SERVICE_ERROR" in issue for issue in outcome.issues)


def test_empty_response_is_no_data(repo):
    class EmptySource:
        source_name = "empty"

        def fetch(self, page: int = 1) -> ApiResponse:
            return make_response()

    outcome = CollectorService(repo, EmptySource()).collect()
    assert outcome.status == "NO_DATA"
    assert repo.count_market_rows() == 0


def test_validation_issue_marks_partial(repo):
    """검증 위반은 저장을 막지 않는다. 저장하고 PARTIAL로 기록한다."""
    payload = json.loads((SAMPLES / "rec_response_sample.json").read_text(encoding="utf-8"))
    payload["response"]["body"]["items"]["item"][0]["landTrdRecValue"] = -500

    source = StaticSource(ApiResponse(payload=payload, http_status=200, endpoint="sample://bad"))
    outcome = CollectorService(repo, source).collect()

    assert outcome.status == "PARTIAL"
    assert repo.count_market_rows() == 9
    assert any("거래량" in issue for issue in outcome.issues)


def test_run_is_recorded(repo):
    CollectorService(repo, real_sample_source()).collect()
    last = repo.last_successful_run()
    assert last is not None
    assert last["target_date"] == date(2026, 8, 11)
    assert last["rows_upserted"] == 9


def test_fixture_source_flows_through_same_path(repo, fixture_source):
    """fixture는 client 계층만 교체한다. 나머지는 실제와 같은 경로를 지난다."""
    outcome = CollectorService(repo, fixture_source).collect()
    assert outcome.status == "SUCCESS"
    assert outcome.rows_upserted == outcome.trade_dates * 3
