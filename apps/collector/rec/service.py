"""수집 흐름 조립.

client → mapping → validation → repository 순서와 실패 시 무엇을 남길지만
결정한다. 각 모듈의 내부는 알지 못한다.

## 수집 단위가 거래일이 아니라 전체다

이 API는 날짜 필터가 없고 전체 이력을 페이징으로 돌려준다. 그래서
수집은 날짜별 반복이 아니라 전체 조회 한 번이다.

같은 거래일을 여러 번 받아도 (trade_date, market_area) 유니크 제약에
따라 UPSERT되므로 행이 늘지 않는다. 매번 전체를 받아 덮어써도 안전하다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

from rec.budget import BudgetExhausted
from rec.mapping import MappingError, latest_trade_date, map_response
from rec.repository import RecRepository
from rec.validation import validate_rows

logger = logging.getLogger(__name__)

MAX_PAGES = 20


@dataclass(frozen=True, slots=True)
class CollectionOutcome:
    run_id: int
    status: str
    rows_upserted: int
    trade_dates: int = 0
    latest_trade_date: date | None = None
    issues: list[str] = field(default_factory=list)


class CollectorService:
    def __init__(self, repository: RecRepository, source) -> None:
        self._repo = repository
        self._source = source

    def collect(self, job_type: str = "MANUAL") -> CollectionOutcome:
        """전체 이력을 조회해 적재한다. 이 API에서 수집의 기본 단위다."""
        run_id = self._repo.start_run(job_type, None)
        all_rows = []
        attempts = 0

        try:
            for page in range(1, MAX_PAGES + 1):
                attempts += 1
                response = self._source.fetch(page)

                try:
                    rows = map_response(response)
                except MappingError:
                    # 매핑이 실패하면 원본을 반드시 남긴다. 필드가 바뀌어도
                    # 재처리로 복구할 수 있어야 한다.
                    self._repo.save_raw(run_id, response, trade_date=None)
                    raise

                # 마지막 페이지 다음은 빈 응답이다. 내용 없는 원본까지 쌓지 않는다.
                if not rows:
                    break

                self._repo.save_raw(run_id, response, trade_date=latest_trade_date(rows))
                all_rows.extend(rows)

                if len(rows) < 3:  # 한 거래일은 세 행이다. 그보다 적으면 마지막 페이지다.
                    break
        except BudgetExhausted as exc:
            self._repo.finish_run(run_id, "FAILED", attempts, 0, str(exc))
            raise
        except MappingError as exc:
            self._repo.finish_run(run_id, "FAILED", attempts, 0, str(exc))
            logger.error("매핑 실패: %s", exc)
            return CollectionOutcome(run_id, "FAILED", 0, issues=[str(exc)])
        except Exception as exc:  # noqa: BLE001 - 어떤 실패든 이력에 남긴다
            self._repo.finish_run(run_id, "FAILED", attempts, 0, str(exc))
            logger.error("수집 실패: %s", exc)
            return CollectionOutcome(run_id, "FAILED", 0, issues=[str(exc)])

        if not all_rows:
            self._repo.finish_run(run_id, "NO_DATA", attempts, 0)
            logger.info("수집 결과 없음")
            return CollectionOutcome(run_id, "NO_DATA", 0)

        issues = validate_rows(all_rows)
        upserted = self._repo.upsert_rows(all_rows, source=self._source.source_name)
        latest = latest_trade_date(all_rows)
        trade_dates = len({row.trade_date for row in all_rows})

        status = "PARTIAL" if issues else "SUCCESS"
        self._repo.finish_run(
            run_id,
            status,
            attempts,
            upserted,
            error_message=_summarize(issues) if issues else None,
            target_date=latest,
        )
        if issues:
            logger.warning("검증 경고 %d건. 예: %s", len(issues), issues[:3])
        logger.info("적재 완료: 거래일 %d일, %d행, 최신 %s", trade_dates, upserted, latest)

        return CollectionOutcome(run_id, status, upserted, trade_dates, latest, issues)


def _summarize(issues: list[str], limit: int = 20) -> str:
    """검증 경고가 수백 건 나올 수 있다. 이력 컬럼을 통째로 채우지 않는다."""
    head = "; ".join(issues[:limit])
    return head if len(issues) <= limit else f"{head} … 외 {len(issues) - limit}건"
