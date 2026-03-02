from __future__ import annotations

from marketlens._base import AsyncHTTPClient, SyncHTTPClient
from marketlens._constants import DEFAULT_BASE_URL, DEFAULT_MAX_RETRIES, DEFAULT_TIMEOUT
from marketlens.resources.events import AsyncEvents, Events
from marketlens.resources.markets import AsyncMarkets, Markets
from marketlens.resources.orderbook import AsyncOrderbook, Orderbook
from marketlens.resources.series import AsyncSeriesResource, SeriesResource


class MarketLens:
    """Synchronous MarketLens API client.

    Args:
        api_key: API key. Falls back to ``MARKETLENS_API_KEY`` env var.
        base_url: API base URL.
        timeout: Request timeout in seconds.
        max_retries: Max retries on 429/5xx errors.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        self._http = SyncHTTPClient(
            api_key=api_key, base_url=base_url, timeout=timeout, max_retries=max_retries,
        )
        self.markets = Markets(self._http)
        self.events = Events(self._http)
        self.series = SeriesResource(self._http)
        self.orderbook = Orderbook(self._http)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> MarketLens:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class AsyncMarketLens:
    """Asynchronous MarketLens API client.

    Args:
        api_key: API key. Falls back to ``MARKETLENS_API_KEY`` env var.
        base_url: API base URL.
        timeout: Request timeout in seconds.
        max_retries: Max retries on 429/5xx errors.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        self._http = AsyncHTTPClient(
            api_key=api_key, base_url=base_url, timeout=timeout, max_retries=max_retries,
        )
        self.markets = AsyncMarkets(self._http)
        self.events = AsyncEvents(self._http)
        self.series = AsyncSeriesResource(self._http)
        self.orderbook = AsyncOrderbook(self._http)

    async def close(self) -> None:
        await self._http.close()

    async def __aenter__(self) -> AsyncMarketLens:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
