import os
from datetime import date
from decimal import Decimal

import pytest

from rec.models import ApiResponse, MarketArea, RecMarketRow
from rec.repository import RecRepository

TEST_DSN = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")


def require_test_database(dsn: str) -> str:
    """테스트는 이름이 _test로 끝나는 데이터베이스에서만 돈다.

    repo fixture가 테이블을 비우기 때문에, 환경변수를 잘못 설정하면 축적된
    시세가 지워진다. REC 데이터는 화·목에만 생성되어 복구가 불가능하므로
    설정 실수를 코드로 막는다.
    """
    database_name = dsn.rsplit("/", 1)[-1].split("?")[0]
    if not database_name.endswith("_test"):
        pytest.fail(
            f"테스트 대상 데이터베이스가 '{database_name}'이다. "
            "전용 테스트 DB에서만 실행해야 하며 이름은 '_test'로 끝나야 한다. "
            "docker-compose.yml의 TEST_DATABASE_URL을 확인하라."
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


def make_row(trade_date=date(2026, 8, 6), area=MarketArea.TOTAL, avg_price="70877") -> RecMarketRow:
    return RecMarketRow(
        trade_date=trade_date,
        market_area=area,
        trade_count=4237,
        volume=Decimal("249844"),
        avg_price=Decimal(avg_price),
        high_price=Decimal("129100"),
        low_price=Decimal("64100"),
        close_price=Decimal("70900") if area is MarketArea.TOTAL else None,
        trade_amount=Decimal("17715363100") if area is MarketArea.TOTAL else None,
    )


def make_response(items: list[dict] | None = None) -> ApiResponse:
    """실제 응답과 같은 봉투 구조를 만든다."""
    body: dict = {"dataType": "JSON", "totalCount": "0", "numOfRows": "2000", "pageNo": "1"}
    body["items"] = {"item": items} if items else ""
    return ApiResponse(
        payload={"response": {"header": {"resultCode": "00", "resultMsg": "OK"}, "body": body}},
        http_status=200,
        endpoint="fixture://test",
    )
