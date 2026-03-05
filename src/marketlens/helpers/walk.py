"""Order book walk — replay L2 books for a single market or across a series.

Single-market replay::

    for market, book in client.orderbook.walk(market_id, after=start, before=end):
        print(book.midpoint, book.spread_bps())

Rolling series replay::

    for market, book in client.orderbook.walk("btc-up-or-down-5m", status="resolved"):
        print(market.question, book.imbalance())

Both support ``.to_dataframe()``::

    df = client.orderbook.walk(market_id, after=start, before=end).to_dataframe()
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Iterator

from marketlens.helpers.replay import (
    OrderBookReplay,
    AsyncOrderBookReplay,
    _book_to_row,
    _rows_to_dataframe,
)
from marketlens.types.history import TradeEvent
from marketlens.types.market import Market
from marketlens.types.orderbook import OrderBook


class OrderBookWalk:
    """Iterate ``(Market, OrderBook)`` tuples for one or more markets.

    For each market, fetches L2 history and replays it tick-by-tick.
    Trade events are skipped (they don't change book state).

    Usage::

        # Single market
        walk = client.orderbook.walk(market_id, after=start, before=end)

        # Rolling series
        walk = client.orderbook.walk("btc-up-or-down-5m", status="resolved")

        for market, book in walk:
            ...

        # Or as a DataFrame:
        df = walk.to_dataframe()
    """

    def __init__(
        self, markets: list[Market], orderbook_resource: Any,
        *, after: Any = None, before: Any = None,
    ) -> None:
        self._markets = markets
        self._orderbook = orderbook_resource
        self._after = after
        self._before = before

    def __iter__(self) -> Iterator[tuple[Market, OrderBook]]:
        for market in self._markets:
            history = self._orderbook.history(
                market.id,
                after=self._after or market.open_time,
                before=self._before or market.close_time,
            )
            replay = OrderBookReplay(
                history, market_id=market.id, platform=market.platform,
            )
            for event, book in replay:
                if not isinstance(event, TradeEvent):
                    yield market, book

    def to_dataframe(self):
        """Replay all markets and return a DataFrame.

        Includes all standard book columns plus ``market_id`` and
        ``winning_outcome``.
        """
        rows: list[dict] = []
        for market, book in self:
            row = _book_to_row(book)
            row["t"] = book.as_of
            row["market_id"] = market.id
            row["winning_outcome"] = market.winning_outcome
            rows.append(row)
        return _rows_to_dataframe(rows)


class AsyncOrderBookWalk:
    """Async version of :class:`OrderBookWalk`."""

    def __init__(
        self, markets: list[Market], orderbook_resource: Any,
        *, after: Any = None, before: Any = None,
    ) -> None:
        self._markets = markets
        self._orderbook = orderbook_resource
        self._after = after
        self._before = before

    async def __aiter__(self) -> AsyncIterator[tuple[Market, OrderBook]]:
        for market in self._markets:
            history = self._orderbook.history(
                market.id,
                after=self._after or market.open_time,
                before=self._before or market.close_time,
            )
            replay = AsyncOrderBookReplay(
                history, market_id=market.id, platform=market.platform,
            )
            async for event, book in replay:
                if not isinstance(event, TradeEvent):
                    yield market, book

    async def to_dataframe(self):
        """Async version of :meth:`OrderBookWalk.to_dataframe`."""
        rows: list[dict] = []
        async for market, book in self:
            row = _book_to_row(book)
            row["t"] = book.as_of
            row["market_id"] = market.id
            row["winning_outcome"] = market.winning_outcome
            rows.append(row)
        return _rows_to_dataframe(rows)
