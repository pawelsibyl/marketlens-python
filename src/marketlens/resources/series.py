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

    def walk(
        self, series_id: str, *, after: Any = None, before: Any = None, **params: Any,
    ) -> Iterator[Market]:
        """Iterate markets in a series chronologically.

        Markets are sorted by ``close_time`` ascending (earliest first).
        Pass ``status="resolved"`` to only walk completed markets.

        Usage::

            for market in client.series.walk("btc-up-or-down-5m", status="resolved"):
                ...

        Args:
            series_id: Series identifier.
            after: Only include markets closing at or after this time
                (epoch ms or ``datetime``).
            before: Only include markets closing at or before this time
                (epoch ms or ``datetime``).
            **params: Extra filter params (e.g. ``status``, ``platform``).
        """
        resolved = self._resolve(series_id)
        params["sort"] = "close_time"

        if after is not None or before is not None:
            params["series_id"] = resolved.id
            if after is not None:
                params["close_after"] = after
            if before is not None:
                params["close_before"] = before
            markets = SyncPageIterator(self._client, "/markets", params, Market).to_list()
        else:
            markets = SyncPageIterator(
                self._client, f"/series/{resolved.id}/markets", params, Market,
            ).to_list()

        yield from markets


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

    async def walk(
        self, series_id: str, *, after: Any = None, before: Any = None, **params: Any,
    ):
        """Async version of :meth:`SeriesResource.walk`.

        Usage::

            async for market in client.series.walk("btc-5min-rolling"):
                print(market.question)
        """
        resolved = await self._resolve(series_id)
        params["sort"] = "close_time"

        if after is not None or before is not None:
            params["series_id"] = resolved.id
            if after is not None:
                params["close_after"] = after
            if before is not None:
                params["close_before"] = before
            markets = await AsyncPageIterator(
                self._client, "/markets", params, Market,
            ).to_list()
        else:
            markets = await AsyncPageIterator(
                self._client, f"/series/{resolved.id}/markets", params, Market,
            ).to_list()

        for market in markets:
            yield market
