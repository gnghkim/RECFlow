import os
from datetime import date
from decimal import Decimal

import pytest
from psycopg.conninfo import conninfo_to_dict

from rec.models import ApiResponse, MarketArea, RecMarketRow
from rec.repository import RecRepository

TEST_DSN = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")


def require_test_database(dsn: str) -> str:
    database_name = conninfo_to_dict(dsn).get("dbname") or "<없음>"
    if not database_name.endswith("_test"):
        pytest.fail(
            f"대상 데이터베이스 '{database_name}'는 안전하지 않습니다. "
            "테스트는 전용 테스트 DB에서만 실행해야 하며 "
            "데이터베이스 이름은 '_test'로 끝나야 합니다."
        )
    return database_name


@pytest.fixture
def repo():
    """실제 PostgreSQL에 붙는다. UPSERT는 진짜 DB가 아니면 검증되지 않는다."""
    if not TEST_DSN:
        pytest.skip("DATABASE_URL 또는 TEST_DATABASE_URL이 설정되지 않았다")
    require_test_database(TEST_DSN)
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
