from datetime import date
from decimal import Decimal

from rec.models import MarketArea
from tests.conftest import make_response, make_row


def test_upsert_inserts_new_rows(repo):
    inserted = repo.upsert_rows([make_row(area=MarketArea.LAND), make_row(area=MarketArea.TOTAL)], source="fixture")
    assert inserted == 2
    assert repo.count_market_rows() == 2


def test_upsert_twice_does_not_duplicate(repo):
    """같은 거래일을 두 번 수집해도 행이 늘지 않아야 한다. 이 계획의 핵심 보장이다."""
    repo.upsert_rows([make_row()], source="fixture")
    repo.upsert_rows([make_row()], source="fixture")
    assert repo.count_market_rows() == 1


def test_upsert_updates_changed_values(repo):
    repo.upsert_rows([make_row(avg_price="71450")], source="fixture")
    repo.upsert_rows([make_row(avg_price="72000")], source="fixture")
    assert repo.fetch_avg_price(date(2026, 8, 6), MarketArea.TOTAL) == Decimal("72000.00")


def test_upsert_bumps_updated_at(repo):
    repo.upsert_rows([make_row(avg_price="71450")], source="fixture")
    first = repo.fetch_updated_at(date(2026, 8, 6), MarketArea.TOTAL)
    repo.upsert_rows([make_row(avg_price="72000")], source="fixture")
    assert repo.fetch_updated_at(date(2026, 8, 6), MarketArea.TOTAL) > first


def test_land_and_total_coexist_for_same_date(repo):
    repo.upsert_rows(
        [make_row(area=MarketArea.LAND), make_row(area=MarketArea.JEJU), make_row(area=MarketArea.TOTAL)],
        source="fixture",
    )
    assert repo.count_market_rows() == 3


def test_run_lifecycle(repo):
    run_id = repo.start_run("BACKFILL", date(2026, 8, 6))
    repo.finish_run(run_id, status="SUCCESS", attempts=1, rows_upserted=3)
    last = repo.last_successful_run()
    assert last is not None
    assert last["target_date"] == date(2026, 8, 6)
    assert last["rows_upserted"] == 3


def test_failed_run_is_not_reported_as_last_successful(repo):
    run_id = repo.start_run("SCHEDULED", date(2026, 8, 6))
    repo.finish_run(run_id, status="FAILED", attempts=3, rows_upserted=0, error_message="timeout")
    assert repo.last_successful_run() is None


def test_save_raw_links_to_run(repo):
    run_id = repo.start_run("MANUAL", date(2026, 8, 6))
    raw_id = repo.save_raw(run_id, make_response())
    assert raw_id > 0
    assert repo.count_raw_rows() == 1


def test_raw_is_saved_even_without_market_rows(repo):
    """매핑이 실패해도 원본은 남아야 재처리로 복구할 수 있다."""
    run_id = repo.start_run("MANUAL", date(2026, 8, 6))
    repo.save_raw(run_id, make_response())
    assert repo.count_raw_rows() == 1
    assert repo.count_market_rows() == 0


def test_existing_trade_dates(repo):
    repo.upsert_rows([make_row(trade_date=date(2026, 8, 4)), make_row(trade_date=date(2026, 8, 6))], source="fixture")
    found = repo.existing_trade_dates(date(2026, 8, 1), date(2026, 8, 31))
    assert found == {date(2026, 8, 4), date(2026, 8, 6)}


def test_settled_trade_dates_includes_no_data_days(repo):
    """NO_DATA로 확정된 휴장일은 누락일 재시도 대상에서 빠져야 한다."""
    repo.upsert_rows([make_row(trade_date=date(2026, 8, 4))], source="fixture")
    run_id = repo.start_run("GAP_SCAN", date(2026, 8, 6))
    repo.finish_run(run_id, status="NO_DATA", attempts=3, rows_upserted=0)
    settled = repo.settled_trade_dates(date(2026, 8, 1), date(2026, 8, 31))
    assert settled == {date(2026, 8, 4), date(2026, 8, 6)}
