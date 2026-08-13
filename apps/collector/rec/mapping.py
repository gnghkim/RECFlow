"""API 응답을 도메인 모델로 옮긴다.

이 파일은 REC 현물시장 API의 응답 필드명을 아는 **유일한** 파일이다.
다른 어떤 모듈에도 API 필드 문자열을 쓰지 말 것.

필드명은 2026-08-13에 실제 응답으로 확정했다. 추정값이 아니다.
샘플: tests/samples/rec_response_sample.json

## 응답 구조와 우리 스키마의 차이

API는 **거래일 하나를 한 행**으로 주고 육지·제주를 컬럼으로 나란히 담는다.

    bzDd=20260811  landAvgPrc=70877 ... jejuAvgPrc=80318 ... clsPrc=70900

우리 스키마는 (거래일, 구역) 단위이므로 한 item을 LAND / JEJU / TOTAL
세 행으로 펼친다.

## 파생값 두 가지

API가 주지 않아 우리가 만드는 값이다. 원본에는 없다.

- TOTAL.avg_price : 육지·제주의 **거래량 가중평균**. API에 통합 평균가가 없다.
  단순 산술평균을 쓰면 거래량이 200배 차이나는 두 시장을 같은 비중으로
  섞게 되어 실제 시세와 어긋난다.
- TOTAL.high_price / low_price : 두 시장의 최고·최저를 합친 범위.

나머지는 전부 API 원본 값이다.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from rec.models import ApiResponse, MarketArea, RecMarketRow


class MappingError(Exception):
    """응답 구조가 기대와 다를 때 발생한다."""


# --- 실제 응답으로 확정한 필드명 (2026-08-13) -------------------------------

FIELD_TRADE_DAY = "bzDd"

# 구역별 컬럼. (평균가, 최고가, 최저가, 거래건수, 거래량)
AREA_FIELDS = {
    MarketArea.LAND: {
        "avg_price": "landAvgPrc",
        "high_price": "landHgPrc",
        "low_price": "landLwPrc",
        "trade_count": "landTrdCnt",
        "volume": "landTrdRecValue",
        # 그날의 가격제한폭. 체결가는 이 범위 안에만 존재할 수 있다.
        "floor": "landLwlmtPrc",
        "cap": "landUplmtPrc",
    },
    MarketArea.JEJU: {
        "avg_price": "jejuAvgPrc",
        "high_price": "jejuHgPrc",
        "low_price": "jejuLwPrc",
        "trade_count": "jejuTrdCnt",
        "volume": "jejuTrdRecValue",
        "floor": "jejuLwlmtPrc",
        "cap": "jejuUplmtPrc",
    },
}

# 통합 컬럼. 종가와 거래금액은 통합값으로만 제공된다.
FIELD_CLOSE_PRICE = "clsPrc"
FIELD_TRADE_AMOUNT = "bidTrdVal"
FIELD_TOTAL_COUNT = "totCnt"
FIELD_TOTAL_VOLUME = "totRecValue"

SUCCESS_RESULT_CODE = "00"

# --- 확정값 끝 ---------------------------------------------------------------


def map_response(response: ApiResponse) -> list[RecMarketRow]:
    """응답 전체를 도메인 행 목록으로 변환한다. 한 item이 세 행이 된다."""
    body = _read_body(response.payload)
    rows: list[RecMarketRow] = []
    for item in _read_items(body):
        rows.extend(_map_item(item))
    return rows


def latest_trade_date(rows: list[RecMarketRow]) -> date | None:
    """행 목록에서 가장 최근 거래일. 원본 보존 시 어느 시점 스냅샷인지 기록하는 데 쓴다."""
    return max((row.trade_date for row in rows), default=None)


def _read_body(payload: dict) -> dict:
    # 경로나 서비스가 잘못되면 response 봉투 대신 이쪽이 온다.
    if "OpenAPI_ServiceResponse" in payload:
        header = payload["OpenAPI_ServiceResponse"].get("cmmMsgHeader", {})
        raise MappingError(
            "API 게이트웨이가 오류를 반환했다. "
            f"errMsg={header.get('errMsg')} "
            f"reason={header.get('returnAuthMsg')} "
            f"code={header.get('returnReasonCode')}"
        )

    try:
        envelope = payload["response"]
        header = envelope["header"]
        body = envelope.get("body") or {}
    except (KeyError, TypeError) as exc:
        raise MappingError(f"응답 봉투 구조가 예상과 다르다: {_preview(payload)}") from exc

    code = str(header.get("resultCode", "")).strip()
    if code != SUCCESS_RESULT_CODE:
        raise MappingError(
            f"API가 오류를 반환했다. resultCode={code} resultMsg={header.get('resultMsg', '')}"
        )

    return body


def _read_items(body: dict) -> list[dict]:
    """items가 빈 문자열, None, 단일 객체, 목록 중 무엇으로 와도 목록으로 정규화한다."""
    items = body.get("items")
    if not items:
        return []

    if isinstance(items, list):
        raw = items
    elif isinstance(items, dict):
        inner = items.get("item")
        if not inner:
            return []
        raw = inner if isinstance(inner, list) else [inner]
    else:
        return []

    return [item for item in raw if isinstance(item, dict)]


def _map_item(item: dict) -> list[RecMarketRow]:
    trade_date = _parse_trade_date(_require(item, FIELD_TRADE_DAY))

    area_rows: dict[MarketArea, RecMarketRow] = {}
    for area, fields in AREA_FIELDS.items():
        volume = _parse_decimal(item.get(fields["volume"]))
        traded = volume is not None and volume > 0
        band = (_parse_decimal(item.get(fields["floor"])), _parse_decimal(item.get(fields["cap"])))

        prices = _area_prices(item, fields, traded, band)

        area_rows[area] = RecMarketRow(
            trade_date=trade_date,
            market_area=area,
            # 거래량과 건수 0은 실제 사실이므로 그대로 남긴다.
            trade_count=_parse_int(item.get(fields["trade_count"])),
            volume=volume,
            avg_price=prices["avg_price"],
            high_price=prices["high_price"],
            low_price=prices["low_price"],
            # 종가와 거래금액은 통합값으로만 제공된다. 구역 행에서는 없는 값이다.
            close_price=None,
            trade_amount=None,
        )

    land = area_rows[MarketArea.LAND]
    jeju = area_rows[MarketArea.JEJU]

    total = RecMarketRow(
        trade_date=trade_date,
        market_area=MarketArea.TOTAL,
        trade_count=_parse_int(item.get(FIELD_TOTAL_COUNT)),
        volume=_parse_decimal(item.get(FIELD_TOTAL_VOLUME)),
        avg_price=_weighted_average(land, jeju),
        high_price=_extreme(max, land, jeju, "high_price"),
        low_price=_extreme(min, land, jeju, "low_price"),
        close_price=_parse_decimal(item.get(FIELD_CLOSE_PRICE)),
        trade_amount=_parse_decimal(item.get(FIELD_TRADE_AMOUNT)),
    )

    return [land, jeju, total]


def _area_prices(
    item: dict,
    fields: dict,
    traded: bool,
    band: tuple[Decimal | None, Decimal | None],
) -> dict[str, Decimal | None]:
    """한 구역의 가격 세 항목을 함께 판정한다.

    하나라도 제한폭을 벗어나면 그 구역의 가격을 전부 버린다. 일부만 살리면
    통합 지표가 모순된다. 실제로 2025-08-28 제주는 평균가는 범위 안이고
    최저가만 벗어났는데, 평균만 채택하니 통합 평균가가 통합 최저가보다
    낮아지는 일이 벌어졌다.

    일부가 오염된 기록은 나머지도 신뢰할 수 없다고 보는 편이 안전하다.
    원본은 rec_market_raw에 남으므로 판단 근거는 보존된다.
    """
    names = ("avg_price", "high_price", "low_price")
    if not traded:
        return {name: None for name in names}

    values: dict[str, Decimal | None] = {}
    rejected = False
    for name in names:
        raw = _parse_decimal(item.get(fields[name]))
        checked = _price_within_band(raw, band)
        if raw is not None and checked is None:
            rejected = True
        values[name] = checked

    return {name: None for name in names} if rejected else values


def _price_within_band(
    value: Decimal | None,
    band: tuple[Decimal | None, Decimal | None],
) -> Decimal | None:
    """가격 필드를 읽되 그날의 가격제한폭 안에 있는 값만 받아들인다.

    이 API의 가격 필드는 신뢰도가 구역마다 다르다. 915 거래일을 전수 확인한
    결과 육지는 한 번도 제한폭을 벗어나지 않았고, 제주는 평균가 620/885,
    최고·최저가 799/915가 벗어났다. 0원이나 상한가의 두 배 같은 값이 온다.

    제한폭은 API가 같은 응답에 함께 주는 값이다. 우리가 임의로 정한 기준이
    아니라 시장 규칙이므로, 그 밖의 값은 체결가일 수 없다.

    거른 값은 '값 없음'이 된다. 0이나 이상값을 그대로 저장하면 1년 최저가와
    백분위, 매각 판단 점수가 조용히 무너진다. 원본은 rec_market_raw에
    그대로 남으므로 판단 근거는 보존된다.

    제한폭이 응답에 없으면 검증할 근거가 없으므로 값을 그대로 쓴다.
    """
    if value is None:
        return None

    floor, cap = band
    if floor is not None and value < floor:
        return None
    if cap is not None and value > cap:
        return None
    # 제한폭이 없을 때를 대비한 최소 방어. 0원 체결은 어느 경우에도 없다.
    return None if value <= 0 else value


def _weighted_average(land: RecMarketRow, jeju: RecMarketRow) -> Decimal | None:
    """거래량 가중평균. 한쪽만 거래됐으면 그쪽 값을 그대로 쓴다."""
    pairs = [
        (row.avg_price, row.volume)
        for row in (land, jeju)
        if row.avg_price is not None and row.volume is not None and row.volume > 0
    ]
    if not pairs:
        # 거래량 정보가 없으면 평균가만으로는 가중할 수 없다. 아는 값이 하나면 그것을 쓴다.
        known = [row.avg_price for row in (land, jeju) if row.avg_price is not None]
        return known[0] if len(known) == 1 else None

    total_volume = sum(volume for _, volume in pairs)
    weighted = sum(price * volume for price, volume in pairs)
    return (weighted / total_volume).quantize(Decimal("0.01"))


def _extreme(pick, land: RecMarketRow, jeju: RecMarketRow, attribute: str) -> Decimal | None:
    """통합 최고·최저가. 제한폭 검증을 통과한 값만으로 만든다.

    검증에서 걸러진 구역은 제외한다. 제주 가격이 대부분 걸러지므로 실제로는
    육지 기준이 되는 날이 많다. 걸러진 값을 섞느니 신뢰할 수 있는 값만으로
    범위를 말하는 편이 낫다.
    """
    values = [
        value
        for value in (getattr(land, attribute), getattr(jeju, attribute))
        if value is not None
    ]
    return pick(values) if values else None


def _require(item: dict, key: str) -> str:
    if key not in item:
        raise MappingError(
            f"필수 필드 '{key}'가 응답에 없다. 실제 키 목록: {sorted(item.keys())}. "
            "mapping.py의 필드명 상수를 실제 응답에 맞게 수정하라."
        )
    return str(item[key])


def _parse_trade_date(value: str) -> date:
    text = value.strip().replace("-", "")
    try:
        return datetime.strptime(text, "%Y%m%d").date()
    except ValueError as exc:
        raise MappingError(f"거래일을 해석할 수 없다: {value!r}") from exc


def _parse_decimal(value: object) -> Decimal | None:
    """빈 문자열과 None은 '값 없음'이다. 0으로 대체하지 않는다.

    API는 숫자를 float으로 주므로 str을 거쳐 Decimal로 만든다.
    Decimal(float)을 직접 쓰면 부동소수점 오차가 그대로 들어온다.
    """
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if text in ("", "-"):
        return None
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise MappingError(f"수치를 해석할 수 없다: {value!r}") from exc


def _parse_int(value: object) -> int | None:
    decimal_value = _parse_decimal(value)
    return None if decimal_value is None else int(decimal_value)


def _preview(payload: object, limit: int = 200) -> str:
    return repr(payload)[:limit]
