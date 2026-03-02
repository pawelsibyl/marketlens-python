import httpx
import pytest

from marketlens import (
    MarketLens,
    AuthenticationError,
    NotFoundError,
    InvalidParameterError,
    RateLimitError,
)


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
