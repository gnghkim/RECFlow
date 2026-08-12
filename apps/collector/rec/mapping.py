"""API 응답을 도메인 모델로 옮긴다.

이 파일은 REC 현물시장 API의 응답 필드명을 아는 **유일한** 파일이다.
다른 어떤 모듈에도 API 필드 문자열을 쓰지 말 것.

주의: 아래 FIELD_MAP과 AREA_MAP의 값은 API 키 미발급 상태에서 정한 **잠정값**이다.
키가 발급되면 다음을 실행해 실제 응답을 덤프하고 이 두 상수만 수정한다.

    python -m cli probe --date YYYYMMDD
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from rec.models import ApiResponse, MarketArea, RecMarketRow


class MappingError(Exception):
    """응답 구조가 기대와 다를 때 발생한다."""


# --- 여기부터 잠정값. probe 결과로 확정한다. ---------------------------------

FIELD_TRADE_DAY = "tradeDay"
FIELD_AREA = "areaCd"

FIELD_MAP = {
    "trade_count": "tradeCnt",
    "volume": "tradeQty",
    "avg_price": "avgPrice",
    "high_price": "highPrice",
    "low_price": "lowPrice",
    "close_price": "closePrice",
    "trade_amount": "tradeAmt",
}

AREA_MAP = {
    "육지": MarketArea.LAND,
    "제주": MarketArea.JEJU,
    "합계": MarketArea.TOTAL,
}

# --- 잠정값 끝 ---------------------------------------------------------------

DECIMAL_FIELDS = ("volume", "avg_price", "high_price", "low_price", "close_price", "trade_amount")

SUCCESS_RESULT_CODE = "00"


def map_response(response: ApiResponse) -> list[RecMarketRow]:
    """응답 전체를 도메인 행 목록으로 변환한다. 휴장일이면 빈 목록을 반환한다."""
    body = _read_body(response.payload)
    items = _read_items(body)
    return [_map_item(item) for item in items]


def _read_body(payload: dict) -> dict:
    try:
        envelope = payload["response"]
        header = envelope["header"]
        body = envelope.get("body") or {}
    except (KeyError, TypeError) as exc:
        raise MappingError(f"응답 봉투 구조가 예상과 다르다: {_preview(payload)}") from exc

    code = str(header.get("resultCode", "")).strip()
    if code != SUCCESS_RESULT_CODE:
        message = header.get("resultMsg", "")
        raise MappingError(f"API가 오류를 반환했다. resultCode={code} resultMsg={message}")

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


def _map_item(item: dict) -> RecMarketRow:
    trade_date = _parse_trade_date(_require(item, FIELD_TRADE_DAY))
    market_area = _parse_area(_require(item, FIELD_AREA))

    values: dict[str, object] = {}
    for domain_name, api_name in FIELD_MAP.items():
        raw = item.get(api_name)
        if domain_name in DECIMAL_FIELDS:
            values[domain_name] = _parse_decimal(raw)
        else:
            values[domain_name] = _parse_int(raw)

    return RecMarketRow(trade_date=trade_date, market_area=market_area, **values)  # type: ignore[arg-type]


def _require(item: dict, key: str) -> str:
    if key not in item:
        raise MappingError(
            f"필수 필드 '{key}'가 응답에 없다. 실제 키 목록: {sorted(item.keys())}. "
            "mapping.py의 FIELD_MAP을 실제 응답에 맞게 수정하라."
        )
    return str(item[key])


def _parse_trade_date(value: str) -> date:
    text = value.strip().replace("-", "")
    try:
        return datetime.strptime(text, "%Y%m%d").date()
    except ValueError as exc:
        raise MappingError(f"거래일을 해석할 수 없다: {value!r}") from exc


def _parse_area(value: str) -> MarketArea:
    key = value.strip()
    if key not in AREA_MAP:
        raise MappingError(
            f"알 수 없는 시장 구분: {key!r}. mapping.py의 AREA_MAP에 추가하라. "
            f"현재 인식 가능한 값: {sorted(AREA_MAP.keys())}"
        )
    return AREA_MAP[key]


def _parse_decimal(value: object) -> Decimal | None:
    """빈 문자열과 None은 '값 없음'이다. 0으로 대체하지 않는다."""
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if text == "" or text == "-":
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
