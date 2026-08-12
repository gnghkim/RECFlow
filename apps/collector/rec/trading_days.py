"""REC 현물시장 거래일.

시장은 매주 화요일과 목요일 10:00~16:00에 운영된다. 공휴일에는 휴장하지만
공휴일 API를 별도로 연동하지 않는다. 화·목을 후보로 삼고, 실제 데이터가
없으면 수집 단계에서 NO_DATA로 표시해 반복 재시도를 멈춘다.
"""

from __future__ import annotations

from datetime import date, timedelta

TUESDAY = 1
THURSDAY = 3
TRADING_WEEKDAYS = frozenset({TUESDAY, THURSDAY})


def trading_days(start: date, end: date) -> list[date]:
    """start와 end를 포함한 구간의 거래일 후보를 오름차순으로 반환한다."""
    if start > end:
        return []
    days: list[date] = []
    current = start
    while current <= end:
        if current.weekday() in TRADING_WEEKDAYS:
            days.append(current)
        current += timedelta(days=1)
    return days
