"""일일 API 호출 예산.

공공데이터포털 개발계정은 하루 100건으로 제한된다. 한도에 부딪혀 수집이
멈추는 대신, 여유를 두고 스스로 멈춘 뒤 중단 지점을 기록한다.
"""

from __future__ import annotations

from datetime import date


class BudgetExhausted(Exception):
    """오늘 사용 가능한 호출 횟수를 모두 썼다."""


class DailyBudget:
    def __init__(self, limit: int, today: date | None = None) -> None:
        if limit < 0:
            raise ValueError("limit은 0 이상이어야 한다")
        self._limit = limit
        self._day = today or date.today()
        self._used = 0

    @property
    def remaining(self) -> int:
        return max(0, self._limit - self._used)

    def advance_to(self, day: date) -> None:
        """날짜가 바뀌면 사용량을 초기화한다."""
        if day != self._day:
            self._day = day
            self._used = 0

    def consume(self, today: date | None = None) -> None:
        if today is not None:
            self.advance_to(today)
        if self.remaining <= 0:
            raise BudgetExhausted(
                f"{self._day} 일일 호출 예산 {self._limit}건을 모두 사용했다. "
                "다음 날 남은 구간부터 이어서 수집한다."
            )
        self._used += 1
