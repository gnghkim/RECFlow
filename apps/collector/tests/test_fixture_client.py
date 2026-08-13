from datetime import date
from decimal import Decimal

import pytest

from rec.fixture_client import FixtureClient, generate_fixtures
from rec.mapping import map_response
from rec.models import MarketArea


@pytest.fixture
def fixture_dir(tmp_path):
    generate_fixtures(tmp_path, date(2026, 7, 1), date(2026, 8, 11))
    return tmp_path


def test_generates_one_file_with_all_trading_days(tmp_path):
    count = generate_fixtures(tmp_path, date(2026, 8, 3), date(2026, 8, 9))
    assert count == 2  # 8/4 화, 8/6 목
    assert (tmp_path / "rec_market.json").exists()


def test_generated_fixture_passes_real_mapping(fixture_dir):
    """fixture는 실제 mapping을 통과해야 한다. 통과하지 못하면 검증 가치가 없다."""
    rows = map_response(FixtureClient(fixture_dir).fetch())
    assert rows
    assert {r.market_area for r in rows} == {MarketArea.LAND, MarketArea.JEJU, MarketArea.TOTAL}
    assert len(rows) % 3 == 0


def test_total_row_has_close_price_others_do_not(fixture_dir):
    rows = map_response(FixtureClient(fixture_dir).fetch())
    latest = max(r.trade_date for r in rows)
    by_area = {r.market_area: r for r in rows if r.trade_date == latest}
    assert by_area[MarketArea.TOTAL].close_price is not None
    assert by_area[MarketArea.LAND].close_price is None
    assert by_area[MarketArea.JEJU].close_price is None


def test_prices_are_in_plausible_range(fixture_dir):
    rows = map_response(FixtureClient(fixture_dir).fetch())
    totals = [r for r in rows if r.market_area is MarketArea.TOTAL]
    for row in totals:
        assert Decimal("50000") < row.avg_price < Decimal("100000")
        assert row.low_price <= row.avg_price <= row.high_price


def test_generation_is_deterministic(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    generate_fixtures(a, date(2026, 8, 3), date(2026, 8, 9), seed=42)
    generate_fixtures(b, date(2026, 8, 3), date(2026, 8, 9), seed=42)
    assert (a / "rec_market.json").read_text(encoding="utf-8") == (
        b / "rec_market.json"
    ).read_text(encoding="utf-8")


def test_missing_fixture_returns_empty(tmp_path):
    assert map_response(FixtureClient(tmp_path).fetch()) == []


def test_second_page_is_empty(fixture_dir):
    """fixture는 한 페이지에 전부 담는다. 서비스의 페이징 종료 조건을 만족해야 한다."""
    assert map_response(FixtureClient(fixture_dir).fetch(page=2)) == []


def test_source_name(fixture_dir):
    assert FixtureClient(fixture_dir).source_name == "fixture"
