from __future__ import annotations

from typing import Any, Iterator

from marketlens._base import AsyncHTTPClient, SyncHTTPClient
from marketlens._pagination import AsyncPageIterator, SyncPageIterator
from marketlens.exceptions import NotFoundError
from marketlens.types.market import Market
from marketlens.types.series import Series


class SeriesResource:
    def __init__(self, client: SyncHTTPClient) -> None:
        self._client = client

    def _resolve(self, series_id: str) -> Series:
        """Resolve *series_id* to a Series, accepting platform slugs."""
        try:
            raw = self._client.get(f"/series/{series_id}")
            return Series.model_validate(raw)
        except NotFoundError:
            pass
        # Fall back to searching by platform_series_id (exact match client-side)
        for s in SyncPageIterator(
            self._client, "/series", {"platform_series_id": series_id}, Series,
        ):
            if s.platform_series_id == series_id:
                return s
        raise NotFoundError(404, "SERIES_NOT_FOUND", f"Series {series_id} not found")

    def list(self, **params: Any) -> SyncPageIterator[Series]:
        return SyncPageIterator(self._client, "/series", params, Series)

    def get(self, series_id: str) -> Series:
        return self._resolve(series_id)

    def markets(self, series_id: str, **params: Any) -> SyncPageIterator[Market]:
        resolved = self._resolve(series_id).id
        return SyncPageIterator(self._client, f"/series/{resolved}/markets", params, Market)

    def walk(self, series_id: str, **params: Any) -> Iterator:
        """Iterate markets in a series chronologically, yielding :class:`MarketSlot` objects.

        Each slot has lazy loaders for the market's candles, trades, and
        orderbook data — so you never load data you don't need.

        Markets are sorted by ``close_time`` ascending (earliest first).
        Pass ``status="resolved"`` to only walk completed markets.

        Usage::

            for slot in client.series.walk("btc-5min-rolling", status="resolved"):
                df = slot.candles("1m").to_dataframe()
                book = slot.orderbook()
                print(slot.market.question, book.spread, slot.overlap_with_prev)

        Args:
            series_id: Series identifier.
            **params: Filter params passed to the markets endpoint
                (e.g. ``status``, ``platform``).
        """
        from marketlens.helpers.walk import MarketSlot

        # Force chronological order
        params["sort"] = "close_time"
        markets = self.markets(series_id, **params).to_list()

        for i, market in enumerate(markets):
            prev_market = markets[i - 1] if i > 0 else None
            next_market = markets[i + 1] if i < len(markets) - 1 else None
            yield MarketSlot(market, i, prev_market, next_market, self._client)


class AsyncSeriesResource:
    def __init__(self, client: AsyncHTTPClient) -> None:
        self._client = client

    async def _resolve(self, series_id: str) -> Series:
        """Resolve *series_id* to a Series, accepting platform slugs."""
        try:
            raw = await self._client.get(f"/series/{series_id}")
            return Series.model_validate(raw)
        except NotFoundError:
            pass
        async for s in AsyncPageIterator(
            self._client, "/series", {"platform_series_id": series_id}, Series,
        ):
            if s.platform_series_id == series_id:
                return s
        raise NotFoundError(404, "SERIES_NOT_FOUND", f"Series {series_id} not found")

    def list(self, **params: Any) -> AsyncPageIterator[Series]:
        return AsyncPageIterator(self._client, "/series", params, Series)

    async def get(self, series_id: str) -> Series:
        return await self._resolve(series_id)

    async def markets(self, series_id: str, **params: Any) -> AsyncPageIterator[Market]:
        resolved = (await self._resolve(series_id)).id
        return AsyncPageIterator(self._client, f"/series/{resolved}/markets", params, Market)

    async def walk(self, series_id: str, **params: Any):
        """Async version of :meth:`SeriesResource.walk`.

        Usage::

            async for slot in client.series.walk("btc-5min-rolling"):
                book = await slot.orderbook()
        """
        from marketlens.helpers.walk import AsyncMarketSlot

        params["sort"] = "close_time"
        markets = await (await self.markets(series_id, **params)).to_list()

        for i, market in enumerate(markets):
            prev_market = markets[i - 1] if i > 0 else None
            next_market = markets[i + 1] if i < len(markets) - 1 else None
            yield AsyncMarketSlot(market, i, prev_market, next_market, self._client)
