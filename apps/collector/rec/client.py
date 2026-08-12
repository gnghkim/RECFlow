"""REC 현물시장 Open API HTTP 클라이언트.

HTTP만 안다. 응답 필드의 의미는 mapping.py가, 저장은 repository.py가 맡는다.
"""

from __future__ import annotations

import logging
import time
from datetime import date

import httpx

from rec.budget import DailyBudget
from rec.models import ApiResponse

logger = logging.getLogger(__name__)

RETRY_DELAYS = (2.0, 8.0, 32.0)


class ApiFetchError(Exception):
    """재시도를 모두 소진했거나 재시도해도 소용없는 오류."""


class RecApiClient:
    def __init__(
        self,
        base_url: str,
        service_key: str,
        budget: DailyBudget,
        timeout_connect: float = 5.0,
        timeout_read: float = 20.0,
        max_attempts: int = 3,
        sleep=time.sleep,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._service_key = service_key
        self._budget = budget
        self._timeout = httpx.Timeout(connect=timeout_connect, read=timeout_read, write=timeout_read, pool=timeout_read)
        self._max_attempts = max_attempts
        self._sleep = sleep

    @property
    def source_name(self) -> str:
        return "kpx-openapi"

    def fetch(self, trade_date: date) -> ApiResponse:
        """거래일 하나를 조회한다. 재시도는 같은 논리적 요청이므로 예산은 한 번만 쓴다."""
        self._budget.consume()

        url = f"{self._base_url}/getRecMarketInfo"
        params = {
            "serviceKey": self._service_key,
            "pageNo": "1",
            "numOfRows": "100",
            "dataType": "JSON",
            "tradeDay": trade_date.strftime("%Y%m%d"),
        }

        last_error: Exception | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                with httpx.Client(timeout=self._timeout) as http:
                    response = http.get(url, params=params)

                if 400 <= response.status_code < 500:
                    raise ApiFetchError(
                        f"{trade_date} 요청이 {response.status_code}로 거부되었다. "
                        "인증키와 요청 파라미터를 확인하라. 재시도하지 않는다."
                    )
                response.raise_for_status()
                return ApiResponse(
                    trade_date=trade_date,
                    payload=response.json(),
                    http_status=response.status_code,
                    endpoint=str(response.request.url).split("serviceKey=")[0] + "serviceKey=***",
                )
            except ApiFetchError:
                raise
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                logger.warning("REC API 호출 실패 (%s, 시도 %d/%d): %s", trade_date, attempt, self._max_attempts, exc)
                if attempt < self._max_attempts:
                    self._sleep(RETRY_DELAYS[min(attempt - 1, len(RETRY_DELAYS) - 1)])

        raise ApiFetchError(f"{trade_date} 수집을 {self._max_attempts}회 시도했으나 모두 실패했다: {last_error}")
