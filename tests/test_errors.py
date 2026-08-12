import httpx
import pytest

from marketlens import (
    AsyncMarketLens,
    MarketLens,
    AuthenticationError,
    DailyBudgetExceededError,
    NotFoundError,
    InvalidParameterError,
    RateLimitError,
    RequestUnitsExceededError,
    RowLimitExceededError,
)
from marketlens import TimeoutError as MarketlensTimeoutError

from conftest import BASE_URL


class TestErrorMapping:
    def test_401_raises_auth_error(self, mock_api, client):
        mock_api.get("/markets/x").mock(
            return_value=httpx.Response(401, json={
                "error": {"code": "UNAUTHORIZED", "message": "Invalid API key", "status": 401}
            })
        )
        with pytest.raises(AuthenticationError) as exc_info:
            client.markets.get("x")
        assert exc_info.value.status_code == 401

    def test_404_raises_not_found(self, mock_api, client):
        mock_api.get("/markets/missing").mock(
            return_value=httpx.Response(404, json={
                "error": {"code": "MARKET_NOT_FOUND", "message": "Not found", "status": 404}
            })
        )
        with pytest.raises(NotFoundError):
            client.markets.get("missing")

    def test_400_raises_invalid_param(self, mock_api, client):
        mock_api.get("/markets").mock(
            return_value=httpx.Response(400, json={
                "error": {"code": "INVALID_PARAMETER", "message": "Bad param", "status": 400}
            })
        )
        with pytest.raises(InvalidParameterError):
            client.markets.list().to_list()

    def test_429_raises_rate_limit(self, mock_api, client):
        mock_api.get("/markets").mock(
            return_value=httpx.Response(
                429,
                json={"error": {"code": "RATE_LIMITED", "message": "Too many requests", "status": 429}},
                headers={"Retry-After": "5"},
            )
        )
        with pytest.raises(RateLimitError) as exc_info:
            client.markets.list().to_list()
        assert exc_info.value.retry_after == 5


_EMPTY_PAGE = {"data": [], "meta": {"cursor": None, "has_more": False}}


def _budget_429(code: str) -> httpx.Response:
    return httpx.Response(
        429,
        json={"error": {"code": code, "message": "budget exhausted", "status": 429}},
        headers={"Retry-After": "600"},
    )


class TestBudget429Codes:
    """The three budget codes map to their own exceptions and are never
    retried: their budgets reset at wall-clock boundaries, so an in-process
    retry can only burn attempts."""

    @pytest.mark.parametrize("code,exc_cls", [
        ("DAILY_BUDGET_EXCEEDED", DailyBudgetExceededError),
        ("ROW_LIMIT_EXCEEDED", RowLimitExceededError),
        ("UNIT_LIMIT_EXCEEDED", RequestUnitsExceededError),
    ])
    def test_code_maps_and_never_retries(self, mock_api, client, code, exc_cls):
        route = mock_api.get("/markets").mock(return_value=_budget_429(code))
        with pytest.raises(exc_cls) as exc_info:
            client.markets.list().to_list()
        assert exc_info.value.retry_after == 600
        assert exc_info.value.code == code
        assert route.call_count == 1  # no retry

    def test_plain_429_still_retries(self, mock_api, client):
        route = mock_api.get("/markets")
        route.side_effect = [
            _budget_429("RATE_LIMITED"),
            httpx.Response(200, json=_EMPTY_PAGE),
        ]
        # Patch out the backoff sleep so the retry is instant.
        import marketlens._base as base
        orig_sleep = base.time.sleep
        base.time.sleep = lambda *_: None
        try:
            assert client.markets.list().to_list() == []
        finally:
            base.time.sleep = orig_sleep
        assert route.call_count == 2


class TestTimeoutRetryPolicy:
    """Read timeouts fail fast (the server is still running the query, and a
    retry re-runs it at full cost with the same deadline); connect timeouts
    never reached the server, so they stay retryable."""

    def test_read_timeout_is_not_retried(self, mock_api, client):
        route = mock_api.get("/markets").mock(side_effect=httpx.ReadTimeout("read timed out"))
        with pytest.raises(MarketlensTimeoutError):
            client.markets.list().to_list()
        assert route.call_count == 1

    def test_connect_timeout_is_retried(self, mock_api, client):
        route = mock_api.get("/markets")
        route.side_effect = [
            httpx.ConnectTimeout("connect timed out"),
            httpx.Response(200, json=_EMPTY_PAGE),
        ]
        assert client.markets.list().to_list() == []
        assert route.call_count == 2

    async def test_read_timeout_is_not_retried_async(self, mock_api):
        route = mock_api.get("/markets").mock(side_effect=httpx.ReadTimeout("read timed out"))
        async with AsyncMarketLens(api_key="mk_test_key", base_url=BASE_URL) as ac:
            with pytest.raises(MarketlensTimeoutError):
                await ac.markets.list().to_list()
        assert route.call_count == 1

    async def test_connect_timeout_is_retried_async(self, mock_api):
        route = mock_api.get("/markets")
        route.side_effect = [
            httpx.ConnectTimeout("connect timed out"),
            httpx.Response(200, json=_EMPTY_PAGE),
        ]
        async with AsyncMarketLens(api_key="mk_test_key", base_url=BASE_URL) as ac:
            assert await ac.markets.list().to_list() == []
        assert route.call_count == 2
