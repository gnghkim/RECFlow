import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from rec.mapping import MappingError, map_response
from rec.models import ApiResponse, MarketArea

SAMPLES = Path(__file__).parent / "samples"


def load_sample() -> ApiResponse:
    payload = json.loads((SAMPLES / "rec_response_sample.json").read_text(encoding="utf-8"))
    return ApiResponse(
        trade_date=date(2026, 8, 6),
        payload=payload,
        http_status=200,
        endpoint="https://example.test/RecMarketInfo2",
    )


def test_maps_three_area_rows():
    rows = map_response(load_sample())
    assert len(rows) == 3
    assert {r.market_area for r in rows} == {MarketArea.LAND, MarketArea.JEJU, MarketArea.TOTAL}


def test_total_row_carries_close_price_and_trade_amount():
    rows = map_response(load_sample())
    total = next(r for r in rows if r.market_area is MarketArea.TOTAL)
    assert total.close_price == Decimal("71600")
    assert total.trade_amount == Decimal("13897550000")
    assert total.avg_price == Decimal("71450")
    assert total.trade_count == 450


def test_land_row_has_no_close_price():
    """종가와 거래금액은 통합값으로만 제공되므로 육지 행에서는 None이어야 한다."""
    rows = map_response(load_sample())
    land = next(r for r in rows if r.market_area is MarketArea.LAND)
    assert land.close_price is None
    assert land.trade_amount is None
    assert land.volume == Decimal("185000")


def test_uses_decimal_not_float():
    rows = map_response(load_sample())
    total = next(r for r in rows if r.market_area is MarketArea.TOTAL)
    assert isinstance(total.avg_price, Decimal)


def test_trade_date_comes_from_payload_not_request():
    """요청한 날짜가 아니라 응답 본문의 거래일을 신뢰한다."""
    rows = map_response(load_sample())
    assert all(r.trade_date == date(2026, 8, 6) for r in rows)


def test_empty_items_returns_empty_list():
    """휴장일에는 item이 비어 온다. 예외가 아니라 빈 목록이다."""
    response = ApiResponse(
        trade_date=date(2026, 8, 5),
        payload={
            "response": {
                "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
                "body": {"numOfRows": 10, "pageNo": 1, "totalCount": 0, "items": ""},
            }
        },
        http_status=200,
        endpoint="https://example.test/RecMarketInfo2",
    )
    assert map_response(response) == []


def test_missing_field_raises_mapping_error_listing_available_keys():
    """필드명이 바뀌면 조용히 None이 되지 않고 실제 키 목록과 함께 실패해야 한다."""
    response = ApiResponse(
        trade_date=date(2026, 8, 6),
        payload={
            "response": {
                "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
                "body": {"items": {"item": [{"someOtherName": "20260806"}]}},
            }
        },
        http_status=200,
        endpoint="https://example.test/RecMarketInfo2",
    )
    with pytest.raises(MappingError) as exc:
        map_response(response)
    assert "someOtherName" in str(exc.value)


def test_api_error_result_code_raises():
    response = ApiResponse(
        trade_date=date(2026, 8, 6),
        payload={
            "response": {
                "header": {"resultCode": "30", "resultMsg": "SERVICE KEY IS NOT REGISTERED ERROR."},
                "body": {},
            }
        },
        http_status=200,
        endpoint="https://example.test/RecMarketInfo2",
    )
    with pytest.raises(MappingError) as exc:
        map_response(response)
    assert "30" in str(exc.value)
