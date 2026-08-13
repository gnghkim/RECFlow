"""수집기 내부 전용 HTTP API.

Docker 내부 네트워크에서만 접근 가능하며 Caddy에 연결하지 않는다.
웹 관리자 화면이 수집 상태 확인과 수동 재수집에 사용한다.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI
from pydantic import BaseModel

from config import load_config
from jobs.scheduler import build_scheduler
from rec.fixture_client import FixtureClient
from rec.repository import RecRepository
from rec.service import CollectorService

logger = logging.getLogger(__name__)


class CollectRequest(BaseModel):
    """수집 요청.

    이 API는 날짜 필터가 없어 항상 전체를 받는다. 거래일을 지정할 수단이 없으므로
    본문은 비어 있어도 된다. 웹 관리자 화면의 날짜 입력은 기록용일 뿐이다.
    """

    tradeDate: date | None = None


def create_app(service: CollectorService, repository: RecRepository, scheduler=None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if scheduler is not None:
            scheduler.start()
            logger.info("스케줄러를 시작했다")
        yield
        if scheduler is not None:
            scheduler.shutdown(wait=False)

    app = FastAPI(title="RECFlow Collector", lifespan=lifespan)

    @app.get("/health")
    def health() -> dict:
        last = repository.last_successful_run()
        return {
            "status": "ok",
            "lastSuccessfulRun": None
            if last is None
            else {
                "targetDate": last["target_date"].isoformat() if last["target_date"] else None,
                "jobType": last["job_type"],
                "rowsUpserted": last["rows_upserted"],
                "finishedAt": last["finished_at"].isoformat() if last["finished_at"] else None,
            },
        }

    @app.post("/jobs/collect")
    def collect(request: CollectRequest | None = None) -> dict:
        outcome = service.collect(job_type="MANUAL")
        return {
            "status": outcome.status,
            "rowsUpserted": outcome.rows_upserted,
            "tradeDates": outcome.trade_dates,
            "latestTradeDate": (
                outcome.latest_trade_date.isoformat() if outcome.latest_trade_date else None
            ),
            "issues": outcome.issues[:20],
        }

    return app


def build_default_app() -> FastAPI:
    """컨테이너 진입점. 설정에 따라 실 API 또는 fixture 소스를 고른다."""
    config = load_config()
    repository = RecRepository(config.database_url)

    if config.kpx_api_key:
        from rec.budget import DailyBudget
        from rec.client import RecApiClient

        source = RecApiClient(
            base_url=config.kpx_base_url,
            service_key=config.kpx_api_key,
            budget=DailyBudget(limit=config.kpx_daily_budget),
        )
        logger.info("실 API 소스를 사용한다")
    else:
        source = FixtureClient(config.fixture_dir)
        logger.warning("KPX_API_KEY가 없어 fixture 소스로 기동한다")

    service = CollectorService(repository, source)
    return create_app(service=service, repository=repository, scheduler=build_scheduler(service))
