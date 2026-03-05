from __future__ import annotations

from typing import Any, Union

from pydantic import TypeAdapter

from marketlens._base import AsyncHTTPClient, SyncHTTPClient
from marketlens.exceptions import NotFoundError
from marketlens._pagination import AsyncPageIterator, SyncPageIterator
from marketlens.types.history import DeltaEvent, SnapshotEvent, TradeEvent
from marketlens.types.orderbook import BookMetrics, OrderBook

HistoryEvent = Union[SnapshotEvent, DeltaEvent, TradeEvent]

_HISTORY_EVENT_ADAPTER = TypeAdapter(HistoryEvent)


def _parse_history_event(raw: dict) -> HistoryEvent:
    return _HISTORY_EVENT_ADAPTER.validate_python(raw)


class _HistorySyncPageIterator(SyncPageIterator[HistoryEvent]):
    """Specialized iterator that discriminates history event types."""

    def _fetch_page(self) -> None:
        if self._cursor:
            self._params["cursor"] = self._cursor
        raw = self._client.get(self._path, params=self._params)
        meta = raw.get("meta", {})
        items = raw.get(self._data_key, [])
        self._current_page = [_parse_history_event(item) for item in items]
        self._cursor = meta.get("cursor")
        self._has_more = meta.get("has_more", False)


class _HistoryAsyncPageIterator(AsyncPageIterator[HistoryEvent]):
    """Specialized async iterator that discriminates history event types."""

    async def _fetch_page(self) -> None:
        if self._cursor:
            self._params["cursor"] = self._cursor
        raw = await self._client.get(self._path, params=self._params)
        meta = raw.get("meta", {})
        items = raw.get(self._data_key, [])
        self._current_page = [_parse_history_event(item) for item in items]
        self._cursor = meta.get("cursor")
        self._has_more = meta.get("has_more", False)


class Orderbook:
    def __init__(self, client: SyncHTTPClient, *, series: Any = None, markets: Any = None) -> None:
        self._client = client
        self._series = series
        self._markets = markets

    def get(self, market_id: str, *, at: Any = None, depth: int | None = None) -> OrderBook:
        params: dict[str, Any] = {}
        if at is not None:
            params["at"] = at
        if depth is not None:
            params["depth"] = depth
        raw = self._client.get(f"/markets/{market_id}/orderbook", params=params)
        return OrderBook.model_validate(raw)

    def history(
        self, market_id: str, *, after: Any, before: Any, **params: Any
    ) -> _HistorySyncPageIterator:
        params["after"] = after
        params["before"] = before
        return _HistorySyncPageIterator(
            self._client, f"/markets/{market_id}/orderbook/history", params, SnapshotEvent
        )

    def metrics(
        self, market_id: str, *, after: Any, before: Any, resolution: str, **params: Any
    ) -> SyncPageIterator[BookMetrics]:
        params["after"] = after
        params["before"] = before
        params["resolution"] = resolution
        return SyncPageIterator(
            self._client, f"/markets/{market_id}/orderbook/metrics", params, BookMetrics
        )

    def walk(
        self, id: str, *, after: Any = None, before: Any = None, **params: Any,
    ):
        """Replay L2 books for a single market or across a rolling series.

        Accepts either a market ID or a rolling series ID/slug. When a market
        ID is given, replays that single market's book within the ``after``/
        ``before`` window. When a series is given, iterates all matching
        markets chronologically.

        Returns an :class:`~marketlens.helpers.walk.OrderBookWalk` that yields
        ``(Market, OrderBook)`` tuples and supports ``.to_dataframe()``.

        For non-rolling series, use :meth:`~marketlens.resources.series.SeriesResource.events`
        to browse events and their strike-level markets.

        Args:
            id: Market ID or series identifier / platform slug.
            after: Start time (market: book history window; series: close_time filter).
            before: End time (market: book history window; series: close_time filter).
            **params: Extra filter params (e.g. ``status``, ``platform``).
        """
        from marketlens.helpers.walk import OrderBookWalk

        # Try as a market ID first
        try:
            market = self._markets.get(id)
            return OrderBookWalk([market], self, after=after, before=before)
        except NotFoundError:
            pass

        # Fall back to series
        markets = list(self._series.walk(id, after=after, before=before, **params))
        return OrderBookWalk(markets, self)


class AsyncOrderbook:
    def __init__(self, client: AsyncHTTPClient, *, series: Any = None, markets: Any = None) -> None:
        self._client = client
        self._series = series
        self._markets = markets

    async def get(self, market_id: str, *, at: Any = None, depth: int | None = None) -> OrderBook:
        params: dict[str, Any] = {}
        if at is not None:
            params["at"] = at
        if depth is not None:
            params["depth"] = depth
        raw = await self._client.get(f"/markets/{market_id}/orderbook", params=params)
        return OrderBook.model_validate(raw)

    def history(
        self, market_id: str, *, after: Any, before: Any, **params: Any
    ) -> _HistoryAsyncPageIterator:
        params["after"] = after
        params["before"] = before
        return _HistoryAsyncPageIterator(
            self._client, f"/markets/{market_id}/orderbook/history", params, SnapshotEvent
        )

    def metrics(
        self, market_id: str, *, after: Any, before: Any, resolution: str, **params: Any
    ) -> AsyncPageIterator[BookMetrics]:
        params["after"] = after
        params["before"] = before
        params["resolution"] = resolution
        return AsyncPageIterator(
            self._client, f"/markets/{market_id}/orderbook/metrics", params, BookMetrics
        )

    async def walk(
        self, id: str, *, after: Any = None, before: Any = None, **params: Any,
    ):
        """Async version of :meth:`Orderbook.walk`."""
        from marketlens.helpers.walk import AsyncOrderBookWalk

        # Try as a market ID first
        try:
            market = await self._markets.get(id)
            return AsyncOrderBookWalk([market], self, after=after, before=before)
        except NotFoundError:
            pass

        # Fall back to series
        markets = []
        async for market in self._series.walk(id, after=after, before=before, **params):
            markets.append(market)
        return AsyncOrderBookWalk(markets, self)
