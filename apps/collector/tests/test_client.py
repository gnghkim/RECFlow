from datetime import date

import httpx
import pytest
import respx

from rec.budget import BudgetExhausted, DailyBudget
from rec.client import ApiFetchError, RecApiClient

BASE_URL = "https://apis.example.test/B552115/RecMarketInfo2"
OK_BODY = {
    "response": {
        "header": {"resultCode": "00", "resultMsg": "OK"},
        "body": {"totalCount": "0", "items": ""},
    }
}
GATEWAY_ERROR = {
    "OpenAPI_ServiceResponse": {
        "cmmMsgHeader": {
            "errMsg": "NO_OPENAPI_SERVICE_ERROR",
            "returnAuthMsg": "해당 오픈API 서비스가 없거나 폐기됨",
            "returnReasonCode": "12",
        }
    }
}

SECRET_KEY = "super-secret-service-key"


def build_client(**overrides) -> RecApiClient:
    kwargs = dict(
        base_url=BASE_URL,
        service_key=SECRET_KEY,
        budget=DailyBudget(limit=10, today=date(2026, 8, 13)),
        sleep=lambda _seconds: None,
    )
    kwargs.update(overrides)
    return RecApiClient(**kwargs)


@respx.mock
def test_fetch_returns_api_response():
    respx.get(url__startswith=BASE_URL).mock(return_value=httpx.Response(200, json=OK_BODY))
    result = build_client().fetch()
    assert result.http_status == 200
    assert result.payload == OK_BODY


@respx.mock
def test_calls_the_confirmed_operation_path():
    """경로가 틀리면 게이트웨이가 NO_OPENAPI_SERVICE_ERROR를 낸다. 실측으로 확정한 값이다."""
    route = respx.get(url__startswith=BASE_URL).mock(return_value=httpx.Response(200, json=OK_BODY))
    build_client().fetch()
    assert route.calls[0].request.url.path.endswith("/getRecMarketInfo2")


@respx.mock
def test_sends_pagination_not_trade_day():
    """이 API는 날짜 필터를 지원하지 않는다. tradeDay를 보내면 안 된다."""
    route = respx.get(url__startswith=BASE_URL).mock(return_value=httpx.Response(200, json=OK_BODY))
    build_client(page_size=2000).fetch(page=3)
    params = route.calls[0].request.url.params
    assert params["serviceKey"] == SECRET_KEY
    assert params["pageNo"] == "3"
    assert params["numOfRows"] == "2000"
    assert params["dataType"] == "JSON"
    assert "tradeDay" not in params


@respx.mock
def test_retries_three_times_on_server_error_then_fails():
    route = respx.get(url__startswith=BASE_URL).mock(return_value=httpx.Response(503))
    with pytest.raises(ApiFetchError):
        build_client().fetch()
    assert route.call_count == 3


@respx.mock
def test_retries_then_succeeds():
    route = respx.get(url__startswith=BASE_URL)
    route.side_effect = [httpx.Response(503), httpx.Response(200, json=OK_BODY)]
    assert build_client().fetch().http_status == 200
    assert route.call_count == 2


@respx.mock
def test_does_not_retry_on_client_error():
    route = respx.get(url__startswith=BASE_URL).mock(return_value=httpx.Response(400, json=GATEWAY_ERROR))
    with pytest.raises(ApiFetchError):
        build_client().fetch()
    assert route.call_count == 1


@respx.mock
def test_client_error_message_includes_gateway_reason():
    """400의 원인은 본문에 있다. 그것을 보여주지 않으면 경로 오류를 찾는 데 오래 걸린다."""
    respx.get(url__startswith=BASE_URL).mock(return_value=httpx.Response(400, json=GATEWAY_ERROR))
    with pytest.raises(ApiFetchError) as exc:
        build_client().fetch()
    assert "NO_OPENAPI_SERVICE_ERROR" in str(exc.value)


@respx.mock
def test_error_message_never_leaks_the_service_key():
    """인증키가 예외 메시지로 새면 로그와 오류 보고에 그대로 남는다."""
    respx.get(url__startswith=BASE_URL).mock(
        return_value=httpx.Response(400, text=f"key was {SECRET_KEY} rejected")
    )
    with pytest.raises(ApiFetchError) as exc:
        build_client().fetch()
    assert SECRET_KEY not in str(exc.value)
    assert "***" in str(exc.value)


@respx.mock
def test_backoff_delays_are_exponential():
    delays: list[float] = []
    respx.get(url__startswith=BASE_URL).mock(return_value=httpx.Response(503))
    with pytest.raises(ApiFetchError):
        build_client(sleep=delays.append).fetch()
    assert delays == [2.0, 8.0]


@respx.mock
def test_budget_is_consumed_once_per_fetch_not_per_attempt():
    respx.get(url__startswith=BASE_URL).mock(return_value=httpx.Response(200, json=OK_BODY))
    budget = DailyBudget(limit=10, today=date(2026, 8, 13))
    build_client(budget=budget).fetch()
    assert budget.remaining == 9


@respx.mock
def test_raises_budget_exhausted_without_calling_api():
    route = respx.get(url__startswith=BASE_URL).mock(return_value=httpx.Response(200, json=OK_BODY))
    with pytest.raises(BudgetExhausted):
        build_client(budget=DailyBudget(limit=0, today=date(2026, 8, 13))).fetch()
    assert route.call_count == 0


@respx.mock
def test_retries_on_network_error():
    route = respx.get(url__startswith=BASE_URL)
    route.side_effect = [httpx.ConnectError("boom"), httpx.Response(200, json=OK_BODY)]
    assert build_client().fetch().http_status == 200
    assert route.call_count == 2
