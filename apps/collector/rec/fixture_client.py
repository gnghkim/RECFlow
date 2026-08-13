"""fixture 소스.

RecApiClient와 같은 인터페이스를 제공하되 HTTP 대신 파일을 읽는다.
client 계층만 교체되므로 mapping / validation / repository는 실제와
완전히 동일한 경로를 지난다.

실 API 키가 없거나 오프라인에서 화면을 확인할 때만 쓴다. 키가 있으면
--source api 가 기본이다.

생성되는 JSON은 mapping.py의 필드명 상수를 참조해 만든다.
필드명을 여기에 중복해서 쓰지 않기 위함이다.
"""

from __future__ import annotations

import json
import random
from datetime import date
from decimal import Decimal
from pathlib import Path

from rec.mapping import (
    AREA_FIELDS,
    FIELD_CLOSE_PRICE,
    FIELD_TOTAL_COUNT,
    FIELD_TOTAL_VOLUME,
    FIELD_TRADE_AMOUNT,
    FIELD_TRADE_DAY,
)
from rec.models import ApiResponse, MarketArea
from rec.trading_days import trading_days

FIXTURE_FILE = "rec_market.json"

BASE_PRICE = Decimal("68000")
MIN_PRICE = Decimal("55000")
MAX_PRICE = Decimal("88000")


class FixtureClient:
    """실 API와 같은 모양의 응답을 파일에서 읽어 돌려준다."""

    def __init__(self, fixture_dir: Path) -> None:
        self._path = Path(fixture_dir) / FIXTURE_FILE

    @property
    def source_name(self) -> str:
        return "fixture"

    def fetch(self, page: int = 1) -> ApiResponse:
        if not self._path.exists():
            payload = _envelope([])
        elif page > 1:
            # fixture는 한 페이지에 전부 담는다. 2페이지 이후는 비어 있다.
            payload = _envelope([])
        else:
            payload = json.loads(self._path.read_text(encoding="utf-8"))

        return ApiResponse(
            payload=payload,
            http_status=200,
            endpoint=f"fixture://{self._path.name}?pageNo={page}",
        )


def generate_fixtures(fixture_dir: Path, start: date, end: date, seed: int = 20260813) -> int:
    """구간의 모든 거래일을 담은 응답 파일 하나를 만든다. 같은 seed면 같은 결과가 나온다."""
    fixture_dir = Path(fixture_dir)
    fixture_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(seed)
    price = BASE_PRICE
    items: list[dict] = []

    for index, day in enumerate(trading_days(start, end), start=1):
        drift = Decimal(str(round(rng.gauss(15, 700), 2)))
        price = _clamp(price + drift, MIN_PRICE, MAX_PRICE)

        land = _area_values(rng, price, volume_base=180000)
        jeju = _area_values(rng, price - Decimal("600"), volume_base=900)

        total_volume = land["volume"] + jeju["volume"]
        total_count = land["count"] + jeju["count"]
        weighted = _round2((land["avg"] * land["volume"] + jeju["avg"] * jeju["volume"]) / total_volume)

        item = {
            FIELD_TRADE_DAY: f"{day:%Y%m%d}",
            FIELD_CLOSE_PRICE: float(_round2(weighted + Decimal(str(round(rng.uniform(-250, 250), 2))))),
            FIELD_TRADE_AMOUNT: float(_round2(weighted * total_volume)),
            FIELD_TOTAL_COUNT: float(total_count),
            FIELD_TOTAL_VOLUME: float(total_volume),
            "rn": index,
        }
        for area, values in ((MarketArea.LAND, land), (MarketArea.JEJU, jeju)):
            fields = AREA_FIELDS[area]
            item[fields["avg_price"]] = float(values["avg"])
            item[fields["high_price"]] = float(values["high"])
            item[fields["low_price"]] = float(values["low"])
            item[fields["trade_count"]] = str(values["count"])
            item[fields["volume"]] = int(values["volume"])

        items.append(item)

    target = fixture_dir / FIXTURE_FILE
    target.write_text(json.dumps(_envelope(items), ensure_ascii=False, indent=2), encoding="utf-8")
    return len(items)


def _envelope(items: list[dict]) -> dict:
    return {
        "response": {
            "header": {"resultCode": "00", "resultMsg": "OK"},
            "body": {
                "dataType": "JSON",
                "totalCount": str(len(items)),
                "numOfRows": "2000",
                "pageNo": "1",
                "items": {"item": items} if items else "",
            },
        }
    }


def _area_values(rng: random.Random, center: Decimal, volume_base: int) -> dict:
    avg = _round2(center)
    spread = Decimal(str(round(rng.uniform(300, 1500), 2)))
    return {
        "count": rng.randint(max(1, int(volume_base / 500)), max(2, int(volume_base / 60))),
        "volume": Decimal(rng.randint(int(volume_base * 0.6), int(volume_base * 1.4))),
        "avg": avg,
        "high": _round2(avg + spread),
        "low": _round2(avg - spread),
    }


def _clamp(value: Decimal, low: Decimal, high: Decimal) -> Decimal:
    return max(low, min(high, value))


def _round2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))
