"""정기 수집 스케줄.

REC 현물시장은 매주 화·목 10:00~16:00에 운영된다. 다만 공개 API에 당일
데이터가 올라오는 시각은 장 종료와 다를 수 있다. 2026-08-13(목) 19시에
확인했을 때 최신 데이터가 아직 08-11(화)이었다. 그래서 장 직후 한 번만
받고 끝내지 않고, 다음 날 아침에도 다시 받는다.

이 API는 날짜 필터가 없어 매번 전체 이력을 받는다. UPSERT라 중복이
생기지 않으므로 여러 번 받아도 안전하고, 늦게 올라온 데이터도 자연히 채워진다.

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

    # 장 종료 직후. 당일 데이터가 이미 올라왔으면 여기서 받는다.
    scheduler.add_job(
        lambda: _collect(service, "SCHEDULED"),
        CronTrigger(day_of_week="tue,thu", hour=16, minute=30, timezone=KST),
        id="rec-scheduled",
        replace_existing=True,
    )
    # 같은 날 저녁 재확인.
    scheduler.add_job(
        lambda: _collect(service, "RECHECK"),
        CronTrigger(day_of_week="tue,thu", hour=18, minute=0, timezone=KST),
        id="rec-recheck",
        replace_existing=True,
    )
    # 매일 아침. 늦게 올라온 거래일을 잡는 마지막 그물이다.
    scheduler.add_job(
        lambda: _collect(service, "GAP_SCAN"),
        CronTrigger(hour=9, minute=0, timezone=KST),
        id="rec-gap-scan",
        replace_existing=True,
    )
    return scheduler


def _collect(service: CollectorService, job_type: str) -> None:
    logger.info("수집 시작 (%s)", job_type)
    try:
        outcome = service.collect(job_type=job_type)
        logger.info(
            "수집 종료 (%s): %s 거래일 %d일 %d행 최신 %s",
            job_type,
            outcome.status,
            outcome.trade_dates,
            outcome.rows_upserted,
            outcome.latest_trade_date,
        )
    except Exception as exc:  # noqa: BLE001
        # 한 번 실패로 스케줄러가 멈추면 안 된다. 다음 주기에 다시 시도한다.
        logger.error("수집 실패 (%s): %s", job_type, exc)
