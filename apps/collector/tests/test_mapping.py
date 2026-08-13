"""매핑 골든 테스트.

tests/samples/rec_response_sample.json 은 실제 API 응답에서 잘라낸 것이다.
추정값이 아니므로 이 테스트가 통과하면 실 데이터에서도 통과한다.
"""

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
        payload=payload,
        http_status=200,
        endpoint="https://example.test/getRecMarketInfo2",
    )


def rows_for(trade_date: date):
    return {row.market_area: row for row in map_response(load_sample()) if row.trade_date == trade_date}


def test_one_item_becomes_three_area_rows():
    """API는 거래일 1행에 육지·제주를 컬럼으로 담아 준다. 우리 스키마는 구역별 행이다."""
    rows = map_response(load_sample())
    # 샘플에 거래일 3개가 들어 있다
    assert len(rows) == 9
    assert {r.market_area for r in rows} == {MarketArea.LAND, MarketArea.JEJU, MarketArea.TOTAL}


def test_trade_dates_are_parsed():
    dates = {r.trade_date for r in map_response(load_sample())}
    assert dates == {date(2026, 8, 11), date(2026, 8, 6), date(2017, 5, 30)}


def test_land_row_uses_land_columns():
    land = rows_for(date(2026, 8, 11))[MarketArea.LAND]
    assert land.avg_price == Decimal("70877")
    assert land.high_price == Decimal("71000")
    assert land.low_price == Decimal("70400")
    assert land.trade_count == 4223
    assert land.volume == Decimal("249096")


def test_jeju_row_applies_band_check_on_real_data():
    """실제 2026-08-11 제주 데이터. 제한폭은 63,400~77,400이다.

    평균가 80,318과 최고가 129,100이 상한가를 넘는다. 최저가 64,100은 범위
    안이지만, 같은 구역의 다른 항목이 오염됐으므로 가격 전체를 버린다.
    거래량과 건수는 별개의 사실이므로 그대로 남긴다.
    """
    jeju = rows_for(date(2026, 8, 11))[MarketArea.JEJU]
    assert jeju.avg_price is None
    assert jeju.high_price is None
    assert jeju.low_price is None
    assert jeju.trade_count == 14
    assert jeju.volume == Decimal("748")


def test_total_row_carries_close_price_and_amount():
    """종가와 거래금액은 통합값으로만 제공된다."""
    total = rows_for(date(2026, 8, 11))[MarketArea.TOTAL]
    assert total.close_price == Decimal("70900")
    assert total.trade_amount == Decimal("17715363100")
    assert total.trade_count == 4237
    assert total.volume == Decimal("249844")


def test_area_rows_have_no_close_price():
    """육지·제주 행의 종가는 없는 값이다. 0으로 채우면 통계가 조용히 틀어진다."""
    rows = rows_for(date(2026, 8, 11))
    for area in (MarketArea.LAND, MarketArea.JEJU):
        assert rows[area].close_price is None
        assert rows[area].trade_amount is None


def test_total_equals_sum_of_areas():
    """API가 주는 합계가 실제로 육지+제주와 맞는지 확인한다."""
    rows = rows_for(date(2026, 8, 11))
    assert rows[MarketArea.TOTAL].volume == rows[MarketArea.LAND].volume + rows[MarketArea.JEJU].volume
    assert rows[MarketArea.TOTAL].trade_count == (
        rows[MarketArea.LAND].trade_count + rows[MarketArea.JEJU].trade_count
    )


def test_uses_decimal_not_float():
    """API는 숫자를 float으로 준다. 금액 계산에 부동소수점이 새면 안 된다."""
    total = rows_for(date(2026, 8, 11))[MarketArea.TOTAL]
    assert isinstance(total.avg_price, Decimal)
    assert isinstance(total.trade_amount, Decimal)


def test_total_avg_price_excludes_rejected_area():
    """통합 평균가는 API가 주지 않으므로 검증을 통과한 구역의 거래량 가중평균으로 만든다.

    2026-08-11은 제주 평균가가 제한폭을 벗어나 걸러지므로 육지 값만 남는다.
    """
    rows = rows_for(date(2026, 8, 11))
    assert rows[MarketArea.JEJU].avg_price is None
    assert rows[MarketArea.TOTAL].avg_price == Decimal("70877.00")


def test_total_avg_price_is_volume_weighted_when_both_valid():
    """양쪽 다 유효하면 거래량 가중평균이다. 산술평균이 아니다."""
    response = ApiResponse(
        payload={
            "response": {
                "header": {"resultCode": "00", "resultMsg": "OK"},
                "body": {
                    "items": {
                        "item": [
                            {
                                "bzDd": "20260811",
                                "landAvgPrc": 70000.0,
                                "landHgPrc": 71000.0,
                                "landLwPrc": 69000.0,
                                "landLwlmtPrc": 63000.0,
                                "landUplmtPrc": 78000.0,
                                "landTrdCnt": "100",
                                "landTrdRecValue": 90000,
                                "jejuAvgPrc": 76000.0,
                                "jejuHgPrc": 77000.0,
                                "jejuLwPrc": 75000.0,
                                "jejuLwlmtPrc": 63000.0,
                                "jejuUplmtPrc": 78000.0,
                                "jejuTrdCnt": "10",
                                "jejuTrdRecValue": 10000,
                                "clsPrc": 70500.0,
                                "bidTrdVal": 7060000000.0,
                                "totCnt": 110.0,
                                "totRecValue": 100000.0,
                            }
                        ]
                    }
                },
            }
        },
        http_status=200,
        endpoint="https://example.test/getRecMarketInfo2",
    )
    total = {r.market_area: r for r in map_response(response)}[MarketArea.TOTAL]
    # (70000*90000 + 76000*10000) / 100000 = 70600. 산술평균이면 73000이다.
    assert total.avg_price == Decimal("70600.00")


def test_old_record_maps_too():
    """2017년 최초 거래일도 같은 구조로 매핑된다."""
    rows = rows_for(date(2017, 5, 30))
    assert rows[MarketArea.TOTAL].close_price == Decimal("128000")
    assert rows[MarketArea.LAND].avg_price == Decimal("130445")


def _no_trade_item() -> ApiResponse:
    """제주에 거래가 없던 날. API는 거래 없음을 0으로 표현한다 (실제 2017-06-27 형태)."""
    return ApiResponse(
        payload={
            "response": {
                "header": {"resultCode": "00", "resultMsg": "OK"},
                "body": {
                    "items": {
                        "item": [
                            {
                                "bzDd": "20170627",
                                "landAvgPrc": 124708.0,
                                "landHgPrc": 126100.0,
                                "landLwPrc": 110000.0,
                                "landTrdCnt": "114",
                                "landTrdRecValue": 5327,
                                "jejuAvgPrc": 0.0,
                                "jejuHgPrc": 0.0,
                                "jejuLwPrc": 0.0,
                                "jejuTrdCnt": "0",
                                "jejuTrdRecValue": 0,
                                "clsPrc": 124500.0,
                                "bidTrdVal": 664319000.0,
                                "totCnt": 114.0,
                                "totRecValue": 5327.0,
                            }
                        ]
                    }
                },
            }
        },
        http_status=200,
        endpoint="https://example.test/getRecMarketInfo2",
    )


def test_no_trade_area_has_null_prices_not_zero():
    """거래가 없던 구역의 가격은 0이 아니라 '값 없음'이다.

    0을 가격으로 저장하면 최저가·평균·백분위가 전부 오염된다.
    """
    rows = {r.market_area: r for r in map_response(_no_trade_item())}
    jeju = rows[MarketArea.JEJU]
    assert jeju.avg_price is None
    assert jeju.high_price is None
    assert jeju.low_price is None


def test_no_trade_area_keeps_zero_volume_and_count():
    """거래량 0은 실제 사실이므로 그대로 남긴다. 가격만 값 없음이다."""
    rows = {r.market_area: r for r in map_response(_no_trade_item())}
    jeju = rows[MarketArea.JEJU]
    assert jeju.volume == Decimal("0")
    assert jeju.trade_count == 0


def test_total_low_is_not_polluted_by_idle_area():
    """제주 최저가 0이 통합 최저가로 새면 1년 최저가 통계가 무너진다."""
    rows = {r.market_area: r for r in map_response(_no_trade_item())}
    total = rows[MarketArea.TOTAL]
    assert total.low_price == Decimal("110000")
    assert total.high_price == Decimal("126100")
    assert total.avg_price == Decimal("124708.00")


def _band_violation_item() -> ApiResponse:
    """제주 가격이 그날 상하한가를 벗어난 날 (실제 2025-09-04 형태).

    하한가 64,600 / 상한가 78,800인데 최저 200, 최고 126,500, 평균 62,805.
    셋 다 제도적으로 체결될 수 없는 값이다.
    """
    return ApiResponse(
        payload={
            "response": {
                "header": {"resultCode": "00", "resultMsg": "OK"},
                "body": {
                    "items": {
                        "item": [
                            {
                                "bzDd": "20250904",
                                "landAvgPrc": 71700.0,
                                "landHgPrc": 72000.0,
                                "landLwPrc": 71400.0,
                                "landLwlmtPrc": 64600.0,
                                "landUplmtPrc": 78800.0,
                                "landTrdCnt": "3476",
                                "landTrdRecValue": 233715,
                                "jejuAvgPrc": 62805.0,
                                "jejuHgPrc": 126500.0,
                                "jejuLwPrc": 200.0,
                                "jejuLwlmtPrc": 64600.0,
                                "jejuUplmtPrc": 78800.0,
                                "jejuTrdCnt": "9",
                                "jejuTrdRecValue": 703,
                                "clsPrc": 71700.0,
                                "bidTrdVal": 16807000000.0,
                                "totCnt": 3485.0,
                                "totRecValue": 234418.0,
                            }
                        ]
                    }
                },
            }
        },
        http_status=200,
        endpoint="https://example.test/getRecMarketInfo2",
    )


def test_prices_outside_daily_band_are_rejected():
    """상하한가를 벗어난 가격은 체결가일 수 없다. API가 같은 응답에 준 한계값으로 거른다."""
    rows = {r.market_area: r for r in map_response(_band_violation_item())}
    jeju = rows[MarketArea.JEJU]
    assert jeju.avg_price is None
    assert jeju.high_price is None
    assert jeju.low_price is None


def test_band_check_keeps_valid_area_untouched():
    rows = {r.market_area: r for r in map_response(_band_violation_item())}
    land = rows[MarketArea.LAND]
    assert land.avg_price == Decimal("71700")
    assert land.high_price == Decimal("72000")
    assert land.low_price == Decimal("71400")


def test_total_ignores_area_with_rejected_prices():
    """가격이 걸러진 구역은 통합 지표에서 빠진다. 거래량은 합계 그대로다."""
    rows = {r.market_area: r for r in map_response(_band_violation_item())}
    total = rows[MarketArea.TOTAL]
    assert total.avg_price == Decimal("71700.00")  # 육지만 남음
    assert total.high_price == Decimal("72000")
    assert total.low_price == Decimal("71400")
    # 거래량과 건수는 API 통합값을 그대로 쓴다
    assert total.volume == Decimal("234418")
    assert total.trade_count == 3485


def test_band_check_is_skipped_when_limits_missing():
    """상하한가가 없는 응답이면 검증할 근거가 없으므로 값을 그대로 쓴다."""
    response = ApiResponse(
        payload={
            "response": {
                "header": {"resultCode": "00", "resultMsg": "OK"},
                "body": {
                    "items": {
                        "item": [
                            {
                                "bzDd": "20260811",
                                "landAvgPrc": 70877.0,
                                "landHgPrc": 71000.0,
                                "landLwPrc": 70400.0,
                                "landTrdCnt": "4223",
                                "landTrdRecValue": 249096,
                                "jejuTrdCnt": "0",
                                "jejuTrdRecValue": 0,
                                "clsPrc": 70900.0,
                                "bidTrdVal": 17715363100.0,
                                "totCnt": 4223.0,
                                "totRecValue": 249096.0,
                            }
                        ]
                    }
                },
            }
        },
        http_status=200,
        endpoint="https://example.test/getRecMarketInfo2",
    )
    rows = {r.market_area: r for r in map_response(response)}
    assert rows[MarketArea.LAND].avg_price == Decimal("70877")


def test_zero_price_with_real_trading_is_also_null():
    """거래가 있었는데 일부 가격만 0인 원본 오류(실제 2019-10-15 형태).

    같은 응답의 하한가가 수만 원대이므로 0원 체결은 제도적으로 불가능하다.
    0을 저장하면 1년 최저가가 0원으로 표시된다.
    """
    response = ApiResponse(
        payload={
            "response": {
                "header": {"resultCode": "00", "resultMsg": "OK"},
                "body": {
                    "items": {
                        "item": [
                            {
                                "bzDd": "20191015",
                                "landAvgPrc": 53219.0,
                                "landHgPrc": 53700.0,
                                "landLwPrc": 52800.0,
                                "landTrdCnt": "770",
                                "landTrdRecValue": 135875,
                                "landLwlmtPrc": 37600.0,
                                "landUplmtPrc": 69800.0,
                                "jejuAvgPrc": 9144.0,
                                "jejuHgPrc": 43900.0,
                                "jejuLwPrc": 0.0,
                                "jejuTrdCnt": "13",
                                "jejuTrdRecValue": 1043,
                                "jejuLwlmtPrc": 37600.0,
                                "jejuUplmtPrc": 69800.0,
                                "clsPrc": 52800.0,
                                "bidTrdVal": 7240680100.0,
                                "totCnt": 783.0,
                                "totRecValue": 136918.0,
                            }
                        ]
                    }
                },
            }
        },
        http_status=200,
        endpoint="https://example.test/getRecMarketInfo2",
    )
    rows = {r.market_area: r for r in map_response(response)}

    # 최저가 0과 평균가 9,144(하한가 37,600 미만)가 오염됐으므로
    # 제주 가격은 최고가까지 통째로 버린다.
    jeju = rows[MarketArea.JEJU]
    assert jeju.avg_price is None
    assert jeju.high_price is None
    assert jeju.low_price is None

    total = rows[MarketArea.TOTAL]
    assert total.low_price == Decimal("52800")  # 검증 통과한 육지 값
    assert total.high_price == Decimal("53700")
    assert total.avg_price == Decimal("53219.00")  # 제주가 빠져 육지만 남음


def test_empty_items_returns_empty_list():
    response = ApiResponse(
        payload={
            "response": {
                "header": {"resultCode": "00", "resultMsg": "OK"},
                "body": {"totalCount": "0", "items": ""},
            }
        },
        http_status=200,
        endpoint="https://example.test/getRecMarketInfo2",
    )
    assert map_response(response) == []


def test_missing_field_raises_with_available_keys():
    """필드명이 바뀌면 조용히 None이 되지 않고 실제 키 목록과 함께 실패해야 한다."""
    response = ApiResponse(
        payload={
            "response": {
                "header": {"resultCode": "00", "resultMsg": "OK"},
                "body": {"items": {"item": [{"someOtherName": "20260811"}]}},
            }
        },
        http_status=200,
        endpoint="https://example.test/getRecMarketInfo2",
    )
    with pytest.raises(MappingError) as exc:
        map_response(response)
    assert "someOtherName" in str(exc.value)


def test_api_error_result_code_raises():
    response = ApiResponse(
        payload={
            "response": {
                "header": {"resultCode": "30", "resultMsg": "SERVICE KEY IS NOT REGISTERED ERROR."},
                "body": {},
            }
        },
        http_status=200,
        endpoint="https://example.test/getRecMarketInfo2",
    )
    with pytest.raises(MappingError) as exc:
        map_response(response)
    assert "30" in str(exc.value)


def test_openapi_level_error_raises():
    """경로가 틀리면 response 봉투가 아니라 OpenAPI_ServiceResponse가 온다."""
    response = ApiResponse(
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
        endpoint="https://example.test/wrong",
    )
    with pytest.raises(MappingError) as exc:
        map_response(response)
    assert "NO_OPENAPI_SERVICE_ERROR" in str(exc.value)
