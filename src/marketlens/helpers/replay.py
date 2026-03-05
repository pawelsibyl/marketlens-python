from __future__ import annotations

from decimal import Decimal
from typing import AsyncIterable, AsyncIterator, Iterable, Iterator, Union

from marketlens.types.history import DeltaEvent, SnapshotEvent, TradeEvent
from marketlens.types.orderbook import OrderBook, PriceLevel

HistoryEvent = Union[SnapshotEvent, DeltaEvent, TradeEvent]

FOUR = Decimal("0.0001")
ZERO = Decimal("0")


def _book_to_row(book: OrderBook) -> dict:
    """Extract standard book metrics into a dict row."""
    wmid = book.weighted_midpoint(1)
    return {
        "best_bid": float(book.best_bid) if book.best_bid else None,
        "best_ask": float(book.best_ask) if book.best_ask else None,
        "spread": float(book.spread) if book.spread else None,
        "midpoint": float(book.midpoint) if book.midpoint else None,
        "bid_depth": float(book.bid_depth) if book.bid_depth else None,
        "ask_depth": float(book.ask_depth) if book.ask_depth else None,
        "bid_levels": book.bid_levels,
        "ask_levels": book.ask_levels,
        "imbalance": book.imbalance(),
        "weighted_midpoint": float(wmid) if wmid else None,
        "spread_bps": book.spread_bps(),
    }


def _rows_to_dataframe(rows: list[dict]):
    """Convert rows with a ``t`` column (epoch ms) to a DataFrame."""
    import pandas as pd

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["t"] = pd.to_datetime(df["t"], unit="ms", utc=True)
    df = df.set_index("t")
    return df


def _build_book(
    bids: dict[str, Decimal],
    asks: dict[str, Decimal],
    market_id: str,
    platform: str,
    as_of: int,
) -> OrderBook:
    """Build an OrderBook from raw bid/ask dicts."""
    bid_levels = sorted(
        [PriceLevel(price=p, size=str(s.quantize(FOUR))) for p, s in bids.items() if s > ZERO],
        key=lambda l: Decimal(l.price),
        reverse=True,
    )
    ask_levels = sorted(
        [PriceLevel(price=p, size=str(s.quantize(FOUR))) for p, s in asks.items() if s > ZERO],
        key=lambda l: Decimal(l.price),
    )

    best_bid = bid_levels[0].price if bid_levels else None
    best_ask = ask_levels[0].price if ask_levels else None
    spread = None
    midpoint = None
    if best_bid and best_ask:
        spread = str((Decimal(best_ask) - Decimal(best_bid)).quantize(FOUR))
        midpoint = str(((Decimal(best_bid) + Decimal(best_ask)) / 2).quantize(FOUR))

    bid_depth = str(sum((Decimal(l.size) for l in bid_levels), ZERO).quantize(FOUR))
    ask_depth = str(sum((Decimal(l.size) for l in ask_levels), ZERO).quantize(FOUR))

    return OrderBook(
        market_id=market_id,
        platform=platform,
        as_of=as_of,
        bids=bid_levels,
        asks=ask_levels,
        best_bid=best_bid,
        best_ask=best_ask,
        spread=spread,
        midpoint=midpoint,
        bid_depth=bid_depth,
        ask_depth=ask_depth,
        bid_levels=len(bid_levels),
        ask_levels=len(ask_levels),
    )


class OrderBookReplay:
    """Reconstruct full orderbook state from a history event stream.

    Yields ``(event, book)`` tuples where ``book`` is the full ``OrderBook``
    state after applying the event.

    Usage::

        history = client.orderbook.history(market_id, after=start, before=end)
        for event, book in OrderBookReplay(history, market_id=market_id):
            print(f"t={event.t}  spread={book.spread}")

    Args:
        events: Iterable of history events (from ``client.orderbook.history()``).
        market_id: Market identifier (used in the resulting OrderBook objects).
        platform: Platform name (defaults to ``"polymarket"``).
    """

    def __init__(
        self,
        events: Iterable[HistoryEvent],
        market_id: str = "",
        platform: str = "polymarket",
    ) -> None:
        self._events = events
        self._market_id = market_id
        self._platform = platform

    def __iter__(self) -> Iterator[tuple[HistoryEvent, OrderBook]]:
        bids: dict[str, Decimal] = {}
        asks: dict[str, Decimal] = {}
        book: OrderBook | None = None
        initialized = False

        for event in self._events:
            if isinstance(event, SnapshotEvent):
                bids = {l.price: Decimal(l.size) for l in event.bids}
                asks = {l.price: Decimal(l.size) for l in event.asks}
                book = _build_book(bids, asks, self._market_id, self._platform, event.t)
                initialized = True
                yield event, book

            elif isinstance(event, DeltaEvent):
                if not initialized:
                    raise ValueError(
                        "OrderBookReplay received a delta before any snapshot. "
                        "The history stream must begin with a snapshot event."
                    )
                side_book = bids if event.side == "BUY" else asks
                price = str(Decimal(event.price).quantize(FOUR))
                size = Decimal(event.size)
                if size == ZERO:
                    side_book.pop(price, None)
                else:
                    side_book[price] = size
                book = _build_book(bids, asks, self._market_id, self._platform, event.t)
                yield event, book

            elif isinstance(event, TradeEvent):
                if book is None:
                    if not initialized:
                        raise ValueError(
                            "OrderBookReplay received a trade before any snapshot. "
                            "The history stream must begin with a snapshot event."
                        )
                    book = _build_book(bids, asks, self._market_id, self._platform, event.t)
                yield event, book

    def to_dataframe(self):
        """Replay the event stream and return a DataFrame of book state over time.

        Each row corresponds to one event. Columns include:

        - ``t`` — event timestamp (``datetime64[ns, UTC]``)
        - ``event_type`` — ``"snapshot"``, ``"delta"``, or ``"trade"``
        - ``best_bid``, ``best_ask``, ``spread``, ``midpoint`` — ``float64``
        - ``bid_depth``, ``ask_depth`` — ``float64``
        - ``bid_levels``, ``ask_levels`` — ``int``
        - ``imbalance`` — ``float64`` (bid-ask imbalance in ``[-1, 1]``)
        - ``weighted_midpoint`` — ``float64`` (top-of-book size-weighted mid)
        - ``spread_bps`` — ``float64`` (spread in basis points)

        """
        rows: list[dict] = []
        for event, book in self:
            row = _book_to_row(book)
            row["t"] = event.t
            row["event_type"] = event.type

            if isinstance(event, TradeEvent):
                row["trade_price"] = float(event.price)
                row["trade_size"] = float(event.size)
                row["trade_side"] = event.side

            rows.append(row)

        return _rows_to_dataframe(rows)


class AsyncOrderBookReplay:
    """Async version of OrderBookReplay for use with AsyncPageIterator."""

    def __init__(
        self,
        events: AsyncIterable[HistoryEvent],
        market_id: str = "",
        platform: str = "polymarket",
    ) -> None:
        self._events = events
        self._market_id = market_id
        self._platform = platform

    async def __aiter__(self) -> AsyncIterator[tuple[HistoryEvent, OrderBook]]:
        bids: dict[str, Decimal] = {}
        asks: dict[str, Decimal] = {}
        book: OrderBook | None = None
        initialized = False

        async for event in self._events:
            if isinstance(event, SnapshotEvent):
                bids = {l.price: Decimal(l.size) for l in event.bids}
                asks = {l.price: Decimal(l.size) for l in event.asks}
                book = _build_book(bids, asks, self._market_id, self._platform, event.t)
                initialized = True
                yield event, book

            elif isinstance(event, DeltaEvent):
                if not initialized:
                    raise ValueError(
                        "OrderBookReplay received a delta before any snapshot. "
                        "The history stream must begin with a snapshot event."
                    )
                side_book = bids if event.side == "BUY" else asks
                price = str(Decimal(event.price).quantize(FOUR))
                size = Decimal(event.size)
                if size == ZERO:
                    side_book.pop(price, None)
                else:
                    side_book[price] = size
                book = _build_book(bids, asks, self._market_id, self._platform, event.t)
                yield event, book

            elif isinstance(event, TradeEvent):
                if book is None:
                    if not initialized:
                        raise ValueError(
                            "OrderBookReplay received a trade before any snapshot. "
                            "The history stream must begin with a snapshot event."
                        )
                    book = _build_book(bids, asks, self._market_id, self._platform, event.t)
                yield event, book

    async def to_dataframe(self):
        """Async version of :meth:`OrderBookReplay.to_dataframe`."""
        rows: list[dict] = []
        async for event, book in self:
            row = _book_to_row(book)
            row["t"] = event.t
            row["event_type"] = event.type

            if isinstance(event, TradeEvent):
                row["trade_price"] = float(event.price)
                row["trade_size"] = float(event.size)
                row["trade_side"] = event.side

            rows.append(row)

        return _rows_to_dataframe(rows)
