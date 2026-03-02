from __future__ import annotations

from typing import Any, Union

from pydantic import TypeAdapter

from marketlens._base import AsyncHTTPClient, SyncHTTPClient
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
    def __init__(self, client: SyncHTTPClient) -> None:
        self._client = client

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


class AsyncOrderbook:
    def __init__(self, client: AsyncHTTPClient) -> None:
        self._client = client

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
