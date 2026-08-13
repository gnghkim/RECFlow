"""REC 현물시장 Open API HTTP 클라이언트.

HTTP만 안다. 응답 필드의 의미는 mapping.py가, 저장은 repository.py가 맡는다.

## 이 API의 성질 (2026-08-13 실측)

- 엔드포인트: /B552115/RecMarketInfo2/getRecMarketInfo2
- **날짜 필터가 없다.** tradeDay를 보내도 무시하고 전체 이력을 준다.
- 페이징으로 전체를 돌려주며 2017-05-30부터 오름차순이다.
- numOfRows를 크게 잡으면 한 번에 전부 받을 수 있다.

그래서 수집은 날짜별 반복이 아니라 전체 조회 한 번이다. 개발계정의
하루 100건 제한이 사실상 문제가 되지 않는다.
"""

from __future__ import annotations

import logging
import time

import httpx

from rec.budget import DailyBudget
from rec.models import ApiResponse

logger = logging.getLogger(__name__)

# httpx는 INFO에서 요청 URL 전체를 남긴다. 우리 URL에는 serviceKey가 쿼리로 들어가므로
# 그대로 두면 인증키가 터미널과 로그 파일에 평문으로 찍힌다. 이 모듈을 쓰는 모든 경로
# (CLI, 스케줄러, 내부 API)를 한 번에 막기 위해 import 시점에 낮춘다.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

RETRY_DELAYS = (2.0, 8.0, 32.0)

OPERATION = "getRecMarketInfo2"

# 2026-08-13 기준 전체 915건. 여유를 두어 한 번에 받는다.
DEFAULT_PAGE_SIZE = 2000


class ApiFetchError(Exception):
    """재시도를 모두 소진했거나 재시도해도 소용없는 오류."""


class RecApiClient:
    def __init__(
        self,
        base_url: str,
        service_key: str,
        budget: DailyBudget,
        timeout_connect: float = 5.0,
        timeout_read: float = 30.0,
        max_attempts: int = 3,
        page_size: int = DEFAULT_PAGE_SIZE,
        sleep=time.sleep,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._service_key = service_key
        self._budget = budget
        self._timeout = httpx.Timeout(
            connect=timeout_connect, read=timeout_read, write=timeout_read, pool=timeout_read
        )
        self._max_attempts = max_attempts
        self._page_size = page_size
        self._sleep = sleep

    @property
    def source_name(self) -> str:
        return "kpx-openapi"

    def fetch(self, page: int = 1) -> ApiResponse:
        """한 페이지를 조회한다. 재시도는 같은 논리적 요청이므로 예산은 한 번만 쓴다."""
        self._budget.consume()

        url = f"{self._base_url}/{OPERATION}"
        params = {
            "serviceKey": self._service_key,
            "pageNo": str(page),
            "numOfRows": str(self._page_size),
            "dataType": "JSON",
        }

        last_error: Exception | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                with httpx.Client(timeout=self._timeout) as http:
                    response = http.get(url, params=params)

                if 400 <= response.status_code < 500:
                    # 게이트웨이 오류는 본문에 사유가 들어 있다. 인증키는 절대 담지 않는다.
                    raise ApiFetchError(
                        f"요청이 {response.status_code}로 거부되었다. "
                        f"응답: {self._safe_body(response)} "
                        "인증키와 엔드포인트 경로를 확인하라. 재시도하지 않는다."
                    )
                response.raise_for_status()

                return ApiResponse(
                    payload=response.json(),
                    http_status=response.status_code,
                    endpoint=f"{url}?pageNo={page}&numOfRows={self._page_size}",
                )
            except ApiFetchError:
                raise
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                logger.warning(
                    "REC API 호출 실패 (page %d, 시도 %d/%d): %s",
                    page,
                    attempt,
                    self._max_attempts,
                    self._redact(str(exc)),
                )
                if attempt < self._max_attempts:
                    self._sleep(RETRY_DELAYS[min(attempt - 1, len(RETRY_DELAYS) - 1)])

        raise ApiFetchError(
            f"page {page} 수집을 {self._max_attempts}회 시도했으나 모두 실패했다: "
            f"{self._redact(str(last_error))}"
        )

    def _safe_body(self, response: httpx.Response) -> str:
        return self._redact(response.text[:300].replace("\n", " "))

    def _redact(self, text: str) -> str:
        """인증키가 메시지에 섞여 로그나 예외로 새어나가지 않게 지운다."""
        return text.replace(self._service_key, "***") if self._service_key else text
