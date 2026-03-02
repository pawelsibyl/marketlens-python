"""Series walk — iterate markets in a series chronologically with lazy data access.

The killer feature for backtesting: walk through every market in a rolling
series with one-liner access to candles, trades, and orderbook data per market.

Usage::

    for slot in client.series.walk("btc-5min-rolling", status="resolved"):
        candles = slot.candles("1m").to_dataframe()
        book = slot.orderbook()
        print(slot.market.question, book.spread)
"""

from __future__ import annotations

from typing import Any

from marketlens._pagination import SyncPageIterator, AsyncPageIterator
from marketlens.types.candle import Candle
from marketlens.types.market import Market
from marketlens.types.orderbook import OrderBook
from marketlens.types.trade import Trade


class MarketSlot:
    """A single market within a series walk, with lazy per-market data access.

    Attributes:
        market: The current :class:`Market` object.
        index: Zero-based position in the series (chronological order).
        prev_market: The previous market in the series, or ``None``.
        next_market: The next market in the series, or ``None``.
    """

    def __init__(
        self,
        market: Market,
        index: int,
        prev_market: Market | None,
        next_market: Market | None,
        client: Any,
    ) -> None:
        self.market = market
        self.index = index
        self.prev_market = prev_market
        self.next_market = next_market
        self._client = client

    def candles(self, resolution: str = "1m", **params: Any) -> SyncPageIterator[Candle]:
        """Fetch candles for this market.

        By default, fetches the entire market lifespan (``open_time`` to
        ``close_time``).  Pass ``after``/``before`` to narrow the range.
        """
        if "after" not in params and self.market.open_time is not None:
            params["after"] = self.market.open_time
        if "before" not in params and self.market.close_time is not None:
            params["before"] = self.market.close_time
        params["resolution"] = resolution
        return SyncPageIterator(
            self._client, f"/markets/{self.market.id}/candles", params, Candle,
        )

    def trades(self, **params: Any) -> SyncPageIterator[Trade]:
        """Fetch trades for this market.

        By default, fetches the entire market lifespan.
        """
        if "after" not in params and self.market.open_time is not None:
            params["after"] = self.market.open_time
        if "before" not in params and self.market.close_time is not None:
            params["before"] = self.market.close_time
        return SyncPageIterator(
            self._client, f"/markets/{self.market.id}/trades", params, Trade,
        )

    def orderbook(self, *, at: Any = None, depth: int | None = None) -> OrderBook:
        """Fetch the orderbook for this market.

        When ``at`` is omitted on a resolved market, defaults to
        ``close_time`` so you get the book while the market was still live
        (post-resolution the book is empty).
        """
        params: dict[str, Any] = {}
        if at is None and self.market.status == "resolved" and self.market.close_time is not None:
            at = self.market.close_time
        if at is not None:
            params["at"] = at
        if depth is not None:
            params["depth"] = depth
        raw = self._client.get(f"/markets/{self.market.id}/orderbook", params=params)
        return OrderBook.model_validate(raw)

    def history(self, *, after: Any = None, before: Any = None, **params: Any):
        """Fetch orderbook history for this market.

        By default, uses the full market lifespan.
        """
        from marketlens.resources.orderbook import _HistorySyncPageIterator
        from marketlens.types.history import SnapshotEvent

        if after is None and self.market.open_time is not None:
            after = self.market.open_time
        if before is None and self.market.close_time is not None:
            before = self.market.close_time
        params["after"] = after
        params["before"] = before
        return _HistorySyncPageIterator(
            self._client, f"/markets/{self.market.id}/orderbook/history",
            params, SnapshotEvent,
        )

    @property
    def overlap_with_prev(self) -> int | None:
        """Milliseconds of overlap with the previous market, or ``None``.

        Positive means the previous market was still open when this one started.
        """
        if self.prev_market is None:
            return None
        prev_close = self.prev_market.close_time
        curr_open = self.market.open_time
        if prev_close is None or curr_open is None:
            return None
        overlap = prev_close - curr_open
        return overlap if overlap >= 0 else None

    @property
    def gap_from_prev(self) -> int | None:
        """Milliseconds of gap after the previous market closed, or ``None``.

        Zero means the markets are perfectly contiguous. Positive means there
        was dead time between the two markets.
        """
        if self.prev_market is None:
            return None
        prev_close = self.prev_market.close_time
        curr_open = self.market.open_time
        if prev_close is None or curr_open is None:
            return None
        gap = curr_open - prev_close
        return gap if gap >= 0 else None

    def __repr__(self) -> str:
        return f"MarketSlot(index={self.index}, market_id={self.market.id!r})"


class AsyncMarketSlot:
    """Async version of :class:`MarketSlot`."""

    def __init__(
        self,
        market: Market,
        index: int,
        prev_market: Market | None,
        next_market: Market | None,
        client: Any,
    ) -> None:
        self.market = market
        self.index = index
        self.prev_market = prev_market
        self.next_market = next_market
        self._client = client

    def candles(self, resolution: str = "1m", **params: Any) -> AsyncPageIterator[Candle]:
        if "after" not in params and self.market.open_time is not None:
            params["after"] = self.market.open_time
        if "before" not in params and self.market.close_time is not None:
            params["before"] = self.market.close_time
        params["resolution"] = resolution
        return AsyncPageIterator(
            self._client, f"/markets/{self.market.id}/candles", params, Candle,
        )

    def trades(self, **params: Any) -> AsyncPageIterator[Trade]:
        if "after" not in params and self.market.open_time is not None:
            params["after"] = self.market.open_time
        if "before" not in params and self.market.close_time is not None:
            params["before"] = self.market.close_time
        return AsyncPageIterator(
            self._client, f"/markets/{self.market.id}/trades", params, Trade,
        )

    async def orderbook(self, *, at: Any = None, depth: int | None = None) -> OrderBook:
        """Fetch the orderbook for this market.

        When ``at`` is omitted on a resolved market, defaults to
        ``close_time`` so you get the book while the market was still live.
        """
        params: dict[str, Any] = {}
        if at is None and self.market.status == "resolved" and self.market.close_time is not None:
            at = self.market.close_time
        if at is not None:
            params["at"] = at
        if depth is not None:
            params["depth"] = depth
        raw = await self._client.get(f"/markets/{self.market.id}/orderbook", params=params)
        return OrderBook.model_validate(raw)

    def history(self, *, after: Any = None, before: Any = None, **params: Any):
        from marketlens.resources.orderbook import _HistoryAsyncPageIterator
        from marketlens.types.history import SnapshotEvent

        if after is None and self.market.open_time is not None:
            after = self.market.open_time
        if before is None and self.market.close_time is not None:
            before = self.market.close_time
        params["after"] = after
        params["before"] = before
        return _HistoryAsyncPageIterator(
            self._client, f"/markets/{self.market.id}/orderbook/history",
            params, SnapshotEvent,
        )

    @property
    def overlap_with_prev(self) -> int | None:
        if self.prev_market is None:
            return None
        prev_close = self.prev_market.close_time
        curr_open = self.market.open_time
        if prev_close is None or curr_open is None:
            return None
        overlap = prev_close - curr_open
        return overlap if overlap >= 0 else None

    @property
    def gap_from_prev(self) -> int | None:
        if self.prev_market is None:
            return None
        prev_close = self.prev_market.close_time
        curr_open = self.market.open_time
        if prev_close is None or curr_open is None:
            return None
        gap = curr_open - prev_close
        return gap if gap >= 0 else None

    def __repr__(self) -> str:
        return f"AsyncMarketSlot(index={self.index}, market_id={self.market.id!r})"
