from datetime import date

import pytest

from rec.fixture_client import generate_fixtures, FixtureClient
from rec.service import CollectorService
from tests.conftest import make_response


@pytest.fixture
def fixture_source(tmp_path):
    generate_fixtures(tmp_path, date(2026, 7, 1), date(2026, 8, 6))
    return FixtureClient(tmp_path)


def test_collect_day_stores_rows_and_raw(repo, fixture_source):
    outcome = CollectorService(repo, fixture_source).collect_day(date(2026, 8, 6))
    assert outcome.status == "SUCCESS"
    assert outcome.rows_upserted == 3
    assert repo.count_market_rows() == 3
    assert repo.count_raw_rows() == 1


def test_collect_day_is_idempotent(repo, fixture_source):
    service = CollectorService(repo, fixture_source)
    service.collect_day(date(2026, 8, 6))
    service.collect_day(date(2026, 8, 6))
    assert repo.count_market_rows() == 3
    assert repo.count_raw_rows() == 2  # 원본은 호출마다 남는다


def test_collect_day_on_holiday_returns_no_data(repo, fixture_source):
    """fixture가 없는 날은 휴장일로 간주하고 NO_DATA로 확정한다."""
    outcome = CollectorService(repo, fixture_source).collect_day(date(2026, 8, 5))
    assert outcome.status == "NO_DATA"
    assert outcome.rows_upserted == 0
    assert repo.count_market_rows() == 0


def test_backfill_collects_every_trading_day(repo, fixture_source):
    outcomes = CollectorService(repo, fixture_source).backfill(date(2026, 8, 1), date(2026, 8, 8))
    assert len(outcomes) == 2  # 8/4 화, 8/6 목
    assert repo.count_market_rows() == 6


def test_backfill_skips_already_collected_days(repo, fixture_source):
    service = CollectorService(repo, fixture_source)
    service.collect_day(date(2026, 8, 4))
    outcomes = service.backfill(date(2026, 8, 1), date(2026, 8, 8))
    assert len(outcomes) == 1


def test_backfill_skips_no_data_days_on_second_run(repo, fixture_source):
    """NO_DATA로 확정된 휴장일은 다시 시도하지 않는다."""
    service = CollectorService(repo, fixture_source)
    service.backfill(date(2026, 7, 1), date(2026, 8, 6))
    assert service.backfill(date(2026, 7, 1), date(2026, 8, 6)) == []


def test_run_is_recorded_for_every_collection(repo, fixture_source):
    CollectorService(repo, fixture_source).collect_day(date(2026, 8, 6))
    last = repo.last_successful_run()
    assert last is not None
    assert last["target_date"] == date(2026, 8, 6)


def test_mapping_failure_still_saves_raw_and_records_failed(repo):
    class BrokenSource:
        source_name = "broken"

        def fetch(self, trade_date):
            response = make_response(trade_date)
            response.payload["response"]["body"]["items"] = {"item": [{"unexpectedKey": "x"}]}
            return response

    outcome = CollectorService(repo, BrokenSource()).collect_day(date(2026, 8, 6))
    assert outcome.status == "FAILED"
    assert repo.count_raw_rows() == 1
    assert repo.count_market_rows() == 0


def test_validation_issue_marks_partial(repo):
    class SuspiciousSource:
        source_name = "suspicious"

        def fetch(self, trade_date):
            response = make_response(trade_date)
            response.payload["response"]["body"]["items"] = {
                "item": [
                    {
                        "tradeDay": "20260806",
                        "areaCd": "합계",
                        "tradeCnt": "10",
                        "tradeQty": "-500",
                        "avgPrice": "71000",
                        "highPrice": "72000",
                        "lowPrice": "70000",
                        "closePrice": "71500",
                        "tradeAmt": "1000",
                    }
                ]
            }
            return response

    outcome = CollectorService(repo, SuspiciousSource()).collect_day(date(2026, 8, 6))
    assert outcome.status == "PARTIAL"
    assert repo.count_market_rows() == 1  # 의심스러워도 저장은 한다
    assert any("거래량" in issue for issue in outcome.issues)
