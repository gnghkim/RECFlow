"""수집 값 검증.

위반이 있어도 저장은 한다. 원본을 버리지 않고 PARTIAL로 표시해 관리자가
판단하게 하는 편이, 조용히 버려서 데이터가 비는 것보다 낫다.
"""

from __future__ import annotations

from decimal import Decimal

from rec.models import RecMarketRow

ZERO = Decimal("0")


def validate_rows(rows: list[RecMarketRow]) -> list[str]:
    """위반 사유를 사람이 읽을 수 있는 문장 목록으로 반환한다. 정상이면 빈 목록."""
    issues: list[str] = []
    for row in rows:
        issues.extend(_validate_row(row))
    return issues


def _validate_row(row: RecMarketRow) -> list[str]:
    label = f"{row.trade_date} {row.market_area}"
    issues: list[str] = []
    # 0 이하로 이미 보고한 필드는 band 검사를 건너뛴다. 최저가보다 낮다는
    # 지적은 0 이하라는 사실의 파생 결과라 새 정보를 주지 않는다.
    non_positive: set[str] = set()

    for name, value in (
        ("평균가", row.avg_price),
        ("종가", row.close_price),
        ("최고가", row.high_price),
        ("최저가", row.low_price),
    ):
        if value is not None and value <= ZERO:
            issues.append(f"{label}: {name}가 0 이하다 ({value})")
            non_positive.add(name)

    for name, value in (("거래량", row.volume), ("거래금액", row.trade_amount)):
        if value is not None and value < ZERO:
            issues.append(f"{label}: {name}이 음수다 ({value})")

    if row.high_price is not None and row.low_price is not None and row.high_price < row.low_price:
        issues.append(f"{label}: 최고가({row.high_price})가 최저가({row.low_price})보다 낮다")

    for name, value in (("평균가", row.avg_price), ("종가", row.close_price)):
        if name not in non_positive:
            issues.extend(_check_within_band(name, value, row, label))

    return issues


def _check_within_band(name: str, value: Decimal | None, row: RecMarketRow, label: str) -> list[str]:
    if value is None or row.high_price is None or row.low_price is None:
        return []
    if value > row.high_price:
        return [f"{label}: {name}({value})가 최고가({row.high_price})보다 높다"]
    if value < row.low_price:
        return [f"{label}: {name}({value})가 최저가({row.low_price})보다 낮다"]
    return []
