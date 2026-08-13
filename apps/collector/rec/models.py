"""도메인 모델. 외부 라이브러리와 API 필드명을 알지 못한다."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum


class MarketArea(StrEnum):
    LAND = "LAND"
    JEJU = "JEJU"
    TOTAL = "TOTAL"


@dataclass(frozen=True, slots=True)
class ApiResponse:
    """수집 소스가 돌려주는 원본 응답. client와 fixture_client의 공통 반환형.

    거래일 필드가 없다. 이 API는 날짜 필터를 지원하지 않고 전체 이력을
    페이징으로 돌려주므로, 응답 하나가 여러 거래일을 담는다.
    """

    payload: dict
    http_status: int
    endpoint: str


@dataclass(frozen=True, slots=True)
class RecMarketRow:
    """rec_market 한 행에 대응하는 도메인 값."""

    trade_date: date
    market_area: MarketArea
    trade_count: int | None = None
    volume: Decimal | None = None
    avg_price: Decimal | None = None
    high_price: Decimal | None = None
    low_price: Decimal | None = None
    close_price: Decimal | None = None
    trade_amount: Decimal | None = None
