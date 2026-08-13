"""정기 수집 스케줄.

REC 현물시장은 매주 화·목 10:00~16:00에 운영되므로 장 종료 이후에 수집한다.
타임존은 Asia/Seoul로 고정한다. 호스트 cron에 의존하지 않으므로 서버를
옮겨도 동작이 같다.
"""

from __future__ import annotations

import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from rec.service import CollectorService

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")


def build_scheduler(service: CollectorService) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=KST)

    scheduler.add_job(
        lambda: _collect_today(service, "SCHEDULED"),
        CronTrigger(day_of_week="tue,thu", hour=16, minute=30, timezone=KST),
        id="rec-scheduled",
        replace_existing=True,
    )
    scheduler.add_job(
        lambda: _collect_today(service, "RECHECK"),
        CronTrigger(day_of_week="tue,thu", hour=18, minute=0, timezone=KST),
        id="rec-recheck",
        replace_existing=True,
    )
    scheduler.add_job(
        lambda: _scan_gaps(service),
        CronTrigger(hour=9, minute=0, timezone=KST),
        id="rec-gap-scan",
        replace_existing=True,
    )
    return scheduler


def _collect_today(service: CollectorService, job_type: str) -> None:
    from datetime import datetime

    today = datetime.now(KST).date()
    logger.info("%s 수집 시작 (%s)", today, job_type)
    outcome = service.collect_day(today, job_type=job_type)
    logger.info("%s 수집 종료: %s rows=%d", today, outcome.status, outcome.rows_upserted)


def _scan_gaps(service: CollectorService) -> None:
    logger.info("누락일 점검 시작")
    outcomes = service.scan_gaps(days=30)
    logger.info("누락일 점검 종료: %d건 처리", len(outcomes))
