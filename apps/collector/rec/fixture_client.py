"""fixture 소스.

RecApiClient와 같은 인터페이스를 제공하되 HTTP 대신 파일을 읽는다.
client 계층만 교체되므로 mapping / validation / repository는 실제와
완전히 동일한 경로를 지난다.

생성되는 JSON은 mapping.py의 FIELD_MAP과 AREA_MAP을 참조해 만들어진다.
필드명을 여기에 중복해서 쓰지 않기 위함이다.
"""

from __future__ import annotations

import json
import random
from datetime import date
from decimal import Decimal
from pathlib import Path

from rec.mapping import AREA_MAP, FIELD_MAP, FIELD_AREA, FIELD_TRADE_DAY
from rec.models import ApiResponse, MarketArea
from rec.trading_days import trading_days

EMPTY_PAYLOAD = {
    "response": {
        "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
        "body": {"numOfRows": 100, "pageNo": 1, "totalCount": 0, "items": ""},
    }
}

BASE_PRICE = Decimal("68000")
MIN_PRICE = Decimal("55000")
MAX_PRICE = Decimal("88000")


class FixtureClient:
    def __init__(self, fixture_dir: Path) -> None:
        self._dir = Path(fixture_dir)

    @property
    def source_name(self) -> str:
        return "fixture"

    def fetch(self, trade_date: date) -> ApiResponse:
        path = self._dir / f"{trade_date:%Y%m%d}.json"
        payload = json.loads(path.read_text(encoding="utf-8")) if path.exists() else EMPTY_PAYLOAD
        return ApiResponse(
            trade_date=trade_date,
            payload=payload,
            http_status=200,
            endpoint=f"fixture://{path.name}",
        )


def generate_fixtures(fixture_dir: Path, start: date, end: date, seed: int = 20260812) -> int:
    """구간의 모든 거래일에 대해 그럴듯한 응답 파일을 만든다. 같은 seed면 같은 결과가 나온다."""
    fixture_dir = Path(fixture_dir)
    fixture_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(seed)
    price = BASE_PRICE
    written = 0

    for day in trading_days(start, end):
        # 완만한 추세 + 잡음. 실제 REC 가격의 움직임을 흉내낸다.
        drift = Decimal(str(round(rng.gauss(15, 700), 2)))
        price = _clamp(price + drift, MIN_PRICE, MAX_PRICE)

        land = _area_values(rng, price, volume_base=180000)
        jeju = _area_values(rng, price - Decimal("600"), volume_base=9000)
        total_volume = land["volume"] + jeju["volume"]
        total_avg = _round2((land["avg"] * land["volume"] + jeju["avg"] * jeju["volume"]) / total_volume)

        items = [
            _item(day, MarketArea.LAND, land, close_price=None, trade_amount=None),
            _item(day, MarketArea.JEJU, jeju, close_price=None, trade_amount=None),
            _item(
                day,
                MarketArea.TOTAL,
                {
                    "count": land["count"] + jeju["count"],
                    "volume": total_volume,
                    "avg": total_avg,
                    "high": max(land["high"], jeju["high"]),
                    "low": min(land["low"], jeju["low"]),
                },
                close_price=_round2(total_avg + Decimal(str(round(rng.uniform(-250, 250), 2)))),
                trade_amount=_round2(total_avg * total_volume),
            ),
        ]

        payload = {
            "response": {
                "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
                "body": {"numOfRows": 100, "pageNo": 1, "totalCount": len(items), "items": {"item": items}},
            }
        }
        target = fixture_dir / f"{day:%Y%m%d}.json"
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        written += 1

    return written


def _area_values(rng: random.Random, center: Decimal, volume_base: int) -> dict:
    avg = _round2(center)
    spread = Decimal(str(round(rng.uniform(300, 1500), 2)))
    return {
        "count": rng.randint(int(volume_base / 500), int(volume_base / 300)),
        "volume": Decimal(rng.randint(int(volume_base * 0.6), int(volume_base * 1.4))),
        "avg": avg,
        "high": _round2(avg + spread),
        "low": _round2(avg - spread),
    }


def _item(day: date, area: MarketArea, values: dict, close_price: Decimal | None, trade_amount: Decimal | None) -> dict:
    area_label = next(label for label, mapped in AREA_MAP.items() if mapped is area)
    return {
        FIELD_TRADE_DAY: f"{day:%Y%m%d}",
        FIELD_AREA: area_label,
        FIELD_MAP["trade_count"]: str(values["count"]),
        FIELD_MAP["volume"]: str(values["volume"]),
        FIELD_MAP["avg_price"]: str(values["avg"]),
        FIELD_MAP["high_price"]: str(values["high"]),
        FIELD_MAP["low_price"]: str(values["low"]),
        FIELD_MAP["close_price"]: "" if close_price is None else str(close_price),
        FIELD_MAP["trade_amount"]: "" if trade_amount is None else str(trade_amount),
    }


def _clamp(value: Decimal, low: Decimal, high: Decimal) -> Decimal:
    return max(low, min(high, value))


def _round2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))
