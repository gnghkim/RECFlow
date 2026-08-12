import os
from datetime import date
from decimal import Decimal

import pytest

from rec.models import ApiResponse, MarketArea, RecMarketRow
from rec.repository import RecRepository

TEST_DSN = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")


@pytest.fixture
def repo():
    """실제 PostgreSQL에 붙는다. UPSERT는 진짜 DB가 아니면 검증되지 않는다."""
    if not TEST_DSN:
        pytest.skip("DATABASE_URL 또는 TEST_DATABASE_URL이 설정되지 않았다")
    repository = RecRepository(TEST_DSN)
    repository.truncate_market_tables()
    yield repository
    repository.truncate_market_tables()


def make_row(trade_date=date(2026, 8, 6), area=MarketArea.TOTAL, avg_price="71450") -> RecMarketRow:
    return RecMarketRow(
        trade_date=trade_date,
        market_area=area,
        trade_count=450,
        volume=Decimal("194500"),
        avg_price=Decimal(avg_price),
        high_price=Decimal("99000"),
        low_price=Decimal("10000"),
        close_price=Decimal("71600") if area is MarketArea.TOTAL else None,
        trade_amount=Decimal("13897550000") if area is MarketArea.TOTAL else None,
    )


def make_response(trade_date=date(2026, 8, 6)) -> ApiResponse:
    return ApiResponse(
        trade_date=trade_date,
        payload={"response": {"header": {"resultCode": "00"}, "body": {"items": {"item": []}}}},
        http_status=200,
        endpoint="fixture://test",
    )
