"""Heap-merge helpers for interleaving multiple OrderBookReplay streams."""

from __future__ import annotations

import heapq
from typing import AsyncIterator, Iterator

from marketlens.helpers.replay import AsyncOrderBookReplay, OrderBookReplay
from marketlens.types.history import HistoryEvent
from marketlens.types.market import Market
from marketlens.types.orderbook import OrderBook


def merge_streams(
    streams: list[Iterator[tuple[Market, HistoryEvent, OrderBook]]],
) -> Iterator[tuple[Market, HistoryEvent, OrderBook]]:
    """Heap-merge N event streams by timestamp.

    Each stream yields ``(market, event, book)`` tuples (e.g. from
    ``_make_market_stream``).  A monotonic sequence counter breaks ties.
    """
    heap: list[tuple[int, int, int, Market, HistoryEvent, OrderBook]] = []
    iters: list[Iterator[tuple[Market, HistoryEvent, OrderBook]]] = []
    seq = 0

    for idx, stream in enumerate(streams):
        it = iter(stream)
        iters.append(it)
        try:
            market, event, book = next(it)
            heap.append((event.t, idx, seq, market, event, book))
            seq += 1
        except StopIteration:
            pass

    heapq.heapify(heap)

    while heap:
        _, idx, _, market, event, book = heapq.heappop(heap)
        yield market, event, book
        try:
            m, e, b = next(iters[idx])
            seq += 1
            heapq.heappush(heap, (e.t, idx, seq, m, e, b))
        except StopIteration:
            pass


async def async_merge_streams(
    streams: list[AsyncIterator[tuple[Market, HistoryEvent, OrderBook]]],
) -> AsyncIterator[tuple[Market, HistoryEvent, OrderBook]]:
    """Async version of :func:`merge_streams`."""
    heap: list[tuple[int, int, int, Market, HistoryEvent, OrderBook]] = []
    iters: list[AsyncIterator[tuple[Market, HistoryEvent, OrderBook]]] = []
    seq = 0

    for idx, stream in enumerate(streams):
        ait = stream.__aiter__()
        iters.append(ait)
        try:
            market, event, book = await anext(ait)
            heap.append((event.t, idx, seq, market, event, book))
            seq += 1
        except StopAsyncIteration:
            pass

    heapq.heapify(heap)

    while heap:
        _, idx, _, market, event, book = heapq.heappop(heap)
        yield market, event, book
        try:
            m, e, b = await anext(iters[idx])
            seq += 1
            heapq.heappush(heap, (e.t, idx, seq, m, e, b))
        except StopAsyncIteration:
            pass


def merge_replays(
    replays: list[tuple[Market, OrderBookReplay]],
) -> Iterator[tuple[Market, HistoryEvent, OrderBook]]:
    """Heap-merge N OrderBookReplay iterators by timestamp.

    Yields ``(market, event, book)`` tuples in chronological order.
    A monotonic sequence counter breaks timestamp ties deterministically
    and prevents the heap from comparing event objects.
    """
    heap: list[tuple[int, int, int, HistoryEvent, OrderBook, Market]] = []
    iterators: list[Iterator[tuple[HistoryEvent, OrderBook]]] = []
    seq = 0

    for idx, (market, replay) in enumerate(replays):
        it = iter(replay)
        iterators.append(it)
        try:
            event, book = next(it)
            heap.append((event.t, idx, seq, event, book, market))
            seq += 1
        except StopIteration:
            pass

    heapq.heapify(heap)

    while heap:
        _t, idx, _seq, event, book, market = heapq.heappop(heap)
        yield market, event, book
        try:
            next_event, next_book = next(iterators[idx])
            seq += 1
            heapq.heappush(heap, (next_event.t, idx, seq, next_event, next_book, market))
        except StopIteration:
            pass


async def async_merge_replays(
    replays: list[tuple[Market, AsyncOrderBookReplay]],
) -> AsyncIterator[tuple[Market, HistoryEvent, OrderBook]]:
    """Async version of :func:`merge_replays`."""
    heap: list[tuple[int, int, int, HistoryEvent, OrderBook, Market]] = []
    iterators: list[AsyncIterator[tuple[HistoryEvent, OrderBook]]] = []
    seq = 0

    for idx, (market, replay) in enumerate(replays):
        ait = replay.__aiter__()
        iterators.append(ait)
        try:
            event, book = await anext(ait)
            heap.append((event.t, idx, seq, event, book, market))
            seq += 1
        except StopAsyncIteration:
            pass

    heapq.heapify(heap)

    while heap:
        _t, idx, _seq, event, book, market = heapq.heappop(heap)
        yield market, event, book
        try:
            next_event, next_book = await anext(iterators[idx])
            seq += 1
            heapq.heappush(heap, (next_event.t, idx, seq, next_event, next_book, market))
        except StopAsyncIteration:
            pass
