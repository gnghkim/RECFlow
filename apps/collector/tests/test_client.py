from datetime import date

import httpx
import pytest
import respx

from rec.budget import BudgetExhausted, DailyBudget
from rec.client import ApiFetchError, RecApiClient

BASE_URL = "https://apis.example.test/B552115/RecMarketInfo2"
OK_BODY = {
    "response": {
        "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
        "body": {"items": {"item": []}},
    }
}


def build_client(**overrides) -> RecApiClient:
    kwargs = dict(
        base_url=BASE_URL,
        service_key="test-key",
        budget=DailyBudget(limit=10, today=date(2026, 8, 6)),
        sleep=lambda _seconds: None,
    )
    kwargs.update(overrides)
    return RecApiClient(**kwargs)


@respx.mock
def test_fetch_returns_api_response():
    respx.get(url__startswith=BASE_URL).mock(return_value=httpx.Response(200, json=OK_BODY))
    result = build_client().fetch(date(2026, 8, 6))
    assert result.http_status == 200
    assert result.trade_date == date(2026, 8, 6)
    assert result.payload == OK_BODY


@respx.mock
def test_sends_required_query_parameters():
    route = respx.get(url__startswith=BASE_URL).mock(return_value=httpx.Response(200, json=OK_BODY))
    build_client().fetch(date(2026, 8, 6))
    params = route.calls[0].request.url.params
    assert params["serviceKey"] == "test-key"
    assert params["tradeDay"] == "20260806"
    assert params["dataType"] == "JSON"
    assert params["pageNo"] == "1"
    assert params["numOfRows"] == "100"


@respx.mock
def test_retries_three_times_on_server_error_then_fails():
    route = respx.get(url__startswith=BASE_URL).mock(return_value=httpx.Response(503))
    with pytest.raises(ApiFetchError):
        build_client().fetch(date(2026, 8, 6))
    assert route.call_count == 3


@respx.mock
def test_retries_then_succeeds():
    route = respx.get(url__startswith=BASE_URL)
    route.side_effect = [httpx.Response(503), httpx.Response(200, json=OK_BODY)]
    result = build_client().fetch(date(2026, 8, 6))
    assert result.http_status == 200
    assert route.call_count == 2


@respx.mock
def test_does_not_retry_on_client_error():
    """4xx는 재시도해도 결과가 같으므로 즉시 실패한다."""
    route = respx.get(url__startswith=BASE_URL).mock(return_value=httpx.Response(401))
    with pytest.raises(ApiFetchError):
        build_client().fetch(date(2026, 8, 6))
    assert route.call_count == 1


@respx.mock
def test_backoff_delays_are_exponential():
    delays: list[float] = []
    route = respx.get(url__startswith=BASE_URL).mock(return_value=httpx.Response(503))
    client = build_client(sleep=delays.append)
    with pytest.raises(ApiFetchError):
        client.fetch(date(2026, 8, 6))
    assert delays == [2.0, 8.0]
    assert route.call_count == 3


@respx.mock
def test_budget_is_consumed_once_per_fetch_not_per_attempt():
    """재시도는 같은 논리적 요청이므로 예산은 한 번만 소모한다."""
    respx.get(url__startswith=BASE_URL).mock(return_value=httpx.Response(200, json=OK_BODY))
    budget = DailyBudget(limit=10, today=date(2026, 8, 6))
    client = build_client(budget=budget)
    client.fetch(date(2026, 8, 6))
    assert budget.remaining == 9


@respx.mock
def test_raises_budget_exhausted_without_calling_api():
    route = respx.get(url__startswith=BASE_URL).mock(return_value=httpx.Response(200, json=OK_BODY))
    budget = DailyBudget(limit=0, today=date(2026, 8, 6))
    with pytest.raises(BudgetExhausted):
        build_client(budget=budget).fetch(date(2026, 8, 6))
    assert route.call_count == 0


@respx.mock
def test_retries_on_network_error():
    route = respx.get(url__startswith=BASE_URL)
    route.side_effect = [httpx.ConnectError("boom"), httpx.Response(200, json=OK_BODY)]
    result = build_client().fetch(date(2026, 8, 6))
    assert result.http_status == 200
    assert route.call_count == 2
