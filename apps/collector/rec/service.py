"""수집 흐름 조립.

client → mapping → validation → repository 순서와 실패 시 무엇을 남길지만
결정한다. 각 모듈의 내부는 알지 못한다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta

from rec.budget import BudgetExhausted
from rec.mapping import MappingError, map_response
from rec.repository import RecRepository
from rec.trading_days import trading_days
from rec.validation import validate_rows

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CollectionOutcome:
    run_id: int
    trade_date: date
    status: str
    rows_upserted: int
    issues: list[str] = field(default_factory=list)


class CollectorService:
    def __init__(self, repository: RecRepository, source) -> None:
        self._repo = repository
        self._source = source

    def collect_day(self, trade_date: date, job_type: str = "MANUAL") -> CollectionOutcome:
        run_id = self._repo.start_run(job_type, trade_date)

        try:
            response = self._source.fetch(trade_date)
        except BudgetExhausted as exc:
            self._repo.finish_run(run_id, "FAILED", attempts=0, rows_upserted=0, error_message=str(exc))
            raise
        except Exception as exc:  # noqa: BLE001 - 어떤 실패든 이력에 남긴다
            self._repo.finish_run(run_id, "FAILED", attempts=3, rows_upserted=0, error_message=str(exc))
            logger.error("%s 수집 실패: %s", trade_date, exc)
            return CollectionOutcome(run_id, trade_date, "FAILED", 0, [str(exc)])

        # 원본은 매핑보다 먼저 저장한다. 매핑이 실패해도 재처리로 복구할 수 있어야 한다.
        self._repo.save_raw(run_id, response)

        try:
            rows = map_response(response)
        except MappingError as exc:
            self._repo.finish_run(run_id, "FAILED", attempts=1, rows_upserted=0, error_message=str(exc))
            logger.error("%s 매핑 실패: %s", trade_date, exc)
            return CollectionOutcome(run_id, trade_date, "FAILED", 0, [str(exc)])

        if not rows:
            self._repo.finish_run(run_id, "NO_DATA", attempts=1, rows_upserted=0)
            logger.info("%s 데이터 없음 (휴장일로 확정)", trade_date)
            return CollectionOutcome(run_id, trade_date, "NO_DATA", 0, [])

        issues = validate_rows(rows)
        upserted = self._repo.upsert_rows(rows, source=self._source.source_name)
        status = "PARTIAL" if issues else "SUCCESS"
        self._repo.finish_run(
            run_id,
            status,
            attempts=1,
            rows_upserted=upserted,
            error_message="; ".join(issues) if issues else None,
        )
        if issues:
            logger.warning("%s 검증 경고 %d건: %s", trade_date, len(issues), issues)
        return CollectionOutcome(run_id, trade_date, status, upserted, issues)

    def backfill(self, start: date, end: date, job_type: str = "BACKFILL") -> list[CollectionOutcome]:
        """이미 확정된 날은 건너뛴다. 예산이 소진되면 중단하고 지금까지의 결과를 돌려준다."""
        settled = self._repo.settled_trade_dates(start, end)
        outcomes: list[CollectionOutcome] = []

        for day in trading_days(start, end):
            if day in settled:
                continue
            try:
                outcomes.append(self.collect_day(day, job_type=job_type))
            except BudgetExhausted as exc:
                logger.warning("예산 소진으로 %s에서 중단한다: %s", day, exc)
                break

        return outcomes

    def scan_gaps(self, days: int = 30, today: date | None = None) -> list[CollectionOutcome]:
        end = today or date.today()
        return self.backfill(end - timedelta(days=days), end, job_type="GAP_SCAN")
