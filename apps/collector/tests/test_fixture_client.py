from datetime import date
from decimal import Decimal

import pytest

from rec.fixture_client import FixtureClient, generate_fixtures
from rec.mapping import map_response
from rec.models import MarketArea


@pytest.fixture
def fixture_dir(tmp_path):
    generate_fixtures(tmp_path, date(2026, 7, 1), date(2026, 8, 6))
    return tmp_path


def test_generates_one_file_per_trading_day(tmp_path):
    count = generate_fixtures(tmp_path, date(2026, 8, 3), date(2026, 8, 9))
    assert count == 2
    assert (tmp_path / "20260804.json").exists()
    assert (tmp_path / "20260806.json").exists()


def test_generated_fixture_passes_real_mapping(fixture_dir):
    """fixture는 실제 mapping을 통과해야 한다. 통과하지 못하면 파이프라인 검증 가치가 없다."""
    rows = map_response(FixtureClient(fixture_dir).fetch(date(2026, 8, 6)))
    assert len(rows) == 3
    assert {r.market_area for r in rows} == {MarketArea.LAND, MarketArea.JEJU, MarketArea.TOTAL}


def test_total_row_has_close_price_others_do_not(fixture_dir):
    rows = map_response(FixtureClient(fixture_dir).fetch(date(2026, 8, 6)))
    by_area = {r.market_area: r for r in rows}
    assert by_area[MarketArea.TOTAL].close_price is not None
    assert by_area[MarketArea.LAND].close_price is None
    assert by_area[MarketArea.JEJU].close_price is None


def test_prices_are_in_plausible_range(fixture_dir):
    rows = map_response(FixtureClient(fixture_dir).fetch(date(2026, 8, 6)))
    total = next(r for r in rows if r.market_area is MarketArea.TOTAL)
    assert Decimal("50000") < total.avg_price < Decimal("100000")
    assert total.low_price <= total.avg_price <= total.high_price


def test_generation_is_deterministic(tmp_path):
    """같은 seed면 같은 데이터가 나와야 재현 가능한 테스트가 된다."""
    a, b = tmp_path / "a", tmp_path / "b"
    generate_fixtures(a, date(2026, 8, 3), date(2026, 8, 9), seed=42)
    generate_fixtures(b, date(2026, 8, 3), date(2026, 8, 9), seed=42)
    assert (a / "20260806.json").read_text(encoding="utf-8") == (b / "20260806.json").read_text(encoding="utf-8")


def test_missing_day_returns_empty_items(fixture_dir):
    """fixture가 없는 날은 휴장일처럼 빈 응답을 돌려준다."""
    response = FixtureClient(fixture_dir).fetch(date(2026, 8, 5))
    assert map_response(response) == []


def test_source_name(fixture_dir):
    assert FixtureClient(fixture_dir).source_name == "fixture"
