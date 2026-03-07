from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from marketlens.exceptions import NotFoundError
from marketlens.backtest._fees import FeeModel, PolymarketFeeModel, ZeroFeeModel
from marketlens.backtest._fills import FillSimulator
from marketlens.backtest._portfolio import Portfolio
from marketlens.backtest._results import BacktestResult
from marketlens.backtest._strategy import Strategy, StrategyContext
from marketlens.backtest._types import (
    Fill,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    PositionSide,
    SettlementRecord,
)
from marketlens.helpers.merge import async_merge_replays, merge_replays
from marketlens.helpers.replay import AsyncOrderBookReplay, OrderBookReplay
from marketlens.types.history import DeltaEvent, SnapshotEvent, TradeEvent
from marketlens.types.market import Market
from marketlens.types.orderbook import OrderBook

_FOUR = Decimal("0.0001")


@dataclass
class BacktestConfig:
    initial_cash: str = "10000.0000"
    fee_model: FeeModel | None = None
    fees: str | None = "polymarket"
    taker_only: bool = True
    max_fill_fraction: float = 1.0
    include_trades: bool = True
    latency_ms: int = 50
    slippage_bps: int = 0
    limit_fill_rate: float = 0.1


class _EngineCore:
    """Shared logic for sync and async engines."""

    def __init__(self, strategy: Strategy, config: BacktestConfig | None = None) -> None:
        self._strategy = strategy
        self._config = config or BacktestConfig()

        self._auto_fees = self._config.fees == "polymarket"
        fee_model = self._config.fee_model or ZeroFeeModel()
        self._fill_sim = FillSimulator(
            fee_model,
            taker_only=self._config.taker_only,
            max_fill_fraction=self._config.max_fill_fraction,
            slippage_bps=self._config.slippage_bps,
            limit_fill_rate=self._config.limit_fill_rate,
        )
        self._latency_ms = self._config.latency_ms
        self._portfolio = Portfolio(self._config.initial_cash)
        self._order_counter = 0
        self._orders: list[Order] = []
        self._open_orders: list[Order] = []
        self._pending_orders: list[tuple[int, Order]] = []  # (activate_at, order)
        self._settlements: list[SettlementRecord] = []
        self._equity_curve: list[dict] = []
        self._cash_rejected = 0

        self._current_market: Market | None = None
        self._current_book: OrderBook | None = None
        self._current_time: int = 0
        self._current_event: Any = None
        self._event_books: dict[str, OrderBook] = {}

        self._ctx = StrategyContext(self)

    @property
    def portfolio(self) -> Portfolio:
        return self._portfolio

    @property
    def current_market(self) -> Market:
        return self._current_market  # type: ignore[return-value]

    @property
    def current_book(self) -> OrderBook:
        return self._current_book  # type: ignore[return-value]

    @property
    def current_time(self) -> int:
        return self._current_time

    @property
    def open_orders(self) -> list[Order]:
        return [o for o in self._open_orders if o.status == OrderStatus.OPEN]

    def submit_order(
        self,
        side: OrderSide,
        size: str,
        *,
        limit_price: str | None = None,
        cancel_after: int | None = None,
    ) -> Order:
        self._order_counter += 1
        order_type = OrderType.LIMIT if limit_price is not None else OrderType.MARKET

        # Validate sell orders
        if side in (OrderSide.SELL_YES, OrderSide.SELL_NO):
            pos = self._portfolio.position(self._current_market.id)  # type: ignore[union-attr]
            expected_side = PositionSide.YES if side == OrderSide.SELL_YES else PositionSide.NO
            held = Decimal(pos.shares) if pos.side == expected_side else Decimal("0")
            needed = Decimal(size)
            if held < needed:
                side_name = "YES" if side == OrderSide.SELL_YES else "NO"
                raise ValueError(
                    f"Cannot sell {size} {side_name} shares: only holding {held.quantize(_FOUR)}"
                )

        # Validate limit price
        if limit_price is not None:
            lp = Decimal(limit_price)
            if lp <= 0 or lp >= 1:
                raise ValueError(f"Limit price must be in (0, 1), got {limit_price}")

        order = Order(
            id=f"ord-{self._order_counter}",
            market_id=self._current_market.id,  # type: ignore[union-attr]
            side=side,
            order_type=order_type,
            size=size,
            limit_price=limit_price,
            submitted_at=self._current_time,
            cancel_after=cancel_after,
        )
        self._orders.append(order)

        if self._latency_ms > 0:
            activate_at = self._current_time + self._latency_ms
            self._pending_orders.append((activate_at, order))
        elif order_type == OrderType.MARKET:
            self._fill_market_order(order)
        else:
            order.status = OrderStatus.OPEN
            self._open_orders.append(order)

        return order

    def cancel_order(self, order: Order) -> None:
        if order.status in (OrderStatus.OPEN, OrderStatus.PENDING):
            order.status = OrderStatus.CANCELLED
            self._open_orders = [o for o in self._open_orders if o.id != order.id]
            self._pending_orders = [(t, o) for t, o in self._pending_orders if o.id != order.id]

    def cancel_all_orders(self, *, market_id: str | None = None) -> None:
        remaining: list[Order] = []
        for o in self._open_orders:
            if o.status == OrderStatus.OPEN and (
                market_id is None or o.market_id == market_id
            ):
                o.status = OrderStatus.CANCELLED
            else:
                remaining.append(o)
        self._open_orders = remaining
        remaining_pending: list[tuple[int, Order]] = []
        for t, o in self._pending_orders:
            if o.status == OrderStatus.PENDING and (
                market_id is None or o.market_id == market_id
            ):
                o.status = OrderStatus.CANCELLED
            else:
                remaining_pending.append((t, o))
        self._pending_orders = remaining_pending

    def _activate_pending_orders(self, *, market_id: str | None = None) -> None:
        """Activate orders whose latency delay has elapsed.

        When *market_id* is given, only orders for that market are considered.
        This prevents cross-market fills in event (multi-market) mode.
        """
        still_pending: list[tuple[int, Order]] = []
        for activate_at, order in self._pending_orders:
            if (
                self._current_time >= activate_at
                and order.status == OrderStatus.PENDING
                and (market_id is None or order.market_id == market_id)
            ):
                try:
                    if order.order_type == OrderType.MARKET:
                        self._fill_market_order(order)
                    else:
                        order.status = OrderStatus.OPEN
                        self._open_orders.append(order)
                except ValueError:
                    # Position no longer sufficient (e.g. duplicate sell from latency)
                    order.status = OrderStatus.CANCELLED
            else:
                still_pending.append((activate_at, order))
        self._pending_orders = still_pending

    def _fill_market_order(self, order: Order) -> None:
        fill = self._fill_sim.try_fill_market_order(
            order, self._current_book, self._current_time,  # type: ignore[arg-type]
        )
        if fill is None:
            order.status = OrderStatus.CANCELLED
            return
        try:
            self._apply_fill(order, fill)
        except ValueError:
            order.status = OrderStatus.CANCELLED

    def _try_fill_limit_orders(self, trade: TradeEvent) -> list[Fill]:
        fills: list[Fill] = []
        for order in list(self._open_orders):
            if order.status != OrderStatus.OPEN:
                continue
            if order.market_id != self._current_market.id:  # type: ignore[union-attr]
                continue
            fill = self._fill_sim.try_fill_limit_order(
                order, self._current_book, trade, self._current_time,  # type: ignore[arg-type]
            )
            if fill is None:
                continue
            try:
                self._apply_fill(order, fill)
                fills.append(fill)
            except ValueError:
                order.status = OrderStatus.CANCELLED
                self._open_orders = [o for o in self._open_orders if o.id != order.id]
        return fills

    def _apply_fill(self, order: Order, fill: Fill) -> None:
        # Check cash sufficiency for buy orders
        if fill.side in (OrderSide.BUY_YES, OrderSide.BUY_NO):
            cost = Decimal(fill.price) * Decimal(fill.size) + Decimal(fill.fee)
            if self._portfolio._cash < cost:
                self._cash_rejected += 1
                raise ValueError("Insufficient cash")
        # Apply to portfolio — may also raise ValueError for insufficient shares
        self._portfolio.apply_fill(fill)

        order.fills.append(fill)
        filled = Decimal(order.filled_size) + Decimal(fill.size)
        order.filled_size = str(filled.quantize(_FOUR))
        order.total_fees = str(
            (Decimal(order.total_fees) + Decimal(fill.fee)).quantize(_FOUR)
        )

        total_cost = sum(Decimal(f.price) * Decimal(f.size) for f in order.fills)
        total_filled = sum(Decimal(f.size) for f in order.fills)
        order.avg_fill_price = str((total_cost / total_filled).quantize(_FOUR))

        if filled >= Decimal(order.size):
            order.status = OrderStatus.FILLED
            self._open_orders = [o for o in self._open_orders if o.id != order.id]
        else:
            order.status = OrderStatus.PARTIALLY_FILLED

        self._strategy.on_fill(self._ctx, self._current_market, fill)  # type: ignore[arg-type]

    def _expire_orders(self) -> None:
        remaining: list[Order] = []
        for order in self._open_orders:
            if (
                order.cancel_after is not None
                and self._current_time >= order.cancel_after
            ):
                order.status = OrderStatus.EXPIRED
            else:
                remaining.append(order)
        self._open_orders = remaining

    def _process_event(self, event: SnapshotEvent | DeltaEvent | TradeEvent, book: OrderBook, market: Market, first_book_seen: bool) -> bool:
        """Process a single event. Returns True if this was the first book event."""
        self._current_market = market
        self._current_book = book
        self._current_time = event.t
        is_first = False

        self._activate_pending_orders(market_id=market.id)

        if isinstance(event, TradeEvent):
            self._try_fill_limit_orders(event)
            self._strategy.on_trade(self._ctx, market, book, event)
        elif isinstance(event, (SnapshotEvent, DeltaEvent)):
            if not first_book_seen:
                self._strategy.on_market_start(self._ctx, market, book)
                is_first = True
            self._strategy.on_book(self._ctx, market, book)

        self._expire_orders()
        self._portfolio.mark_to_market(market.id, book)

        if isinstance(event, SnapshotEvent):
            self._equity_curve.append({
                "t": event.t,
                "market_id": market.id,
                "cash": self._portfolio.cash,
                "equity": self._portfolio.equity,
            })

        return is_first

    def _finalize_market(self, market: Market) -> None:
        self._strategy.on_market_end(self._ctx, market)
        self.cancel_all_orders(market_id=market.id)

        if market.status == "resolved" and market.winning_outcome_index is not None:
            timestamp = market.resolved_at or market.close_time or self._current_time
            record = self._portfolio.settle_market(market, timestamp)
            if record is not None:
                self._settlements.append(record)

    def _build_result(self) -> BacktestResult:
        return BacktestResult(
            portfolio=self._portfolio,
            orders=self._orders,
            settlements=self._settlements,
            equity_curve=self._equity_curve,
            cash_rejected=self._cash_rejected,
        )
        


class BacktestEngine(_EngineCore):
    def run(
        self,
        client: Any,
        id: str,
        *,
        after: Any = None,
        before: Any = None,
        **params: Any,
    ) -> BacktestResult:
        # 1. Try as a market UUID
        try:
            market = client.markets.get(id)
            self._run_single_market(client, market, after=after, before=before)
            return self._build_result()
        except NotFoundError:
            pass

        # 2. Try as a series
        try:
            series = client.series.get(id)
        except NotFoundError:
            series = None

        if series is not None:
            if series.structured_type:
                event_params = dict(params)
                if after is not None:
                    event_params["end_after"] = after
                if before is not None:
                    event_params["start_before"] = before
                events = client.series.events(id, **event_params).to_list()
                for evt in events:
                    event_markets = client.events.markets(evt.id).to_list()
                    self._run_event_markets(
                        client, evt, event_markets, after=after, before=before,
                    )
            elif series.is_rolling:
                markets = list(client.series.walk(id, after=after, before=before, **params))
                for market in markets:
                    self._run_single_market(client, market)
            else:
                raise ValueError(
                    f"Series '{series.title}' is neither rolling nor structured."
                )
            return self._build_result()

        # 3. Fallback: condition ID
        found = client.markets.list(condition_id=id).to_list()
        if found:
            self._run_single_market(client, found[0], after=after, before=before)
            return self._build_result()

        raise NotFoundError(404, "NOT_FOUND", f"No market or series found for '{id}'")

    def _run_single_market(
        self, client: Any, market: Market, *, after: Any = None, before: Any = None,
    ) -> None:
        self._current_market = market
        if self._auto_fees:
            self._fill_sim._fee_model = PolymarketFeeModel.for_category(market.category)
        history_params: dict[str, Any] = {}
        if self._config.include_trades:
            history_params["include_trades"] = True

        history = client.orderbook.history(
            market.id,
            after=after or market.open_time,
            before=before or market.close_time,
            **history_params,
        )
        replay = OrderBookReplay(history, market_id=market.id, platform=market.platform)

        first_book_seen = False
        for event, book in replay:
            if self._process_event(event, book, market, first_book_seen):
                first_book_seen = True
            elif not first_book_seen and isinstance(event, (SnapshotEvent, DeltaEvent)):
                first_book_seen = True

        self._finalize_market(market)

    def _run_event_markets(
        self, client: Any, evt: Any, event_markets: list[Market],
        *, after: Any = None, before: Any = None,
    ) -> None:
        self._current_event = evt
        self._event_books = {}
        self._strategy.on_event_start(self._ctx, evt, event_markets)

        history_params: dict[str, Any] = {}
        if self._config.include_trades:
            history_params["include_trades"] = True

        replays: list[tuple[Market, OrderBookReplay]] = []
        for m in event_markets:
            history = client.orderbook.history(
                m.id,
                after=after or m.open_time,
                before=before or m.close_time,
                **history_params,
            )
            replays.append((m, OrderBookReplay(history, market_id=m.id, platform=m.platform)))

        first_book_seen: set[str] = set()
        for market, event, book in merge_replays(replays):
            if self._auto_fees:
                self._fill_sim._fee_model = PolymarketFeeModel.for_category(market.category)
            self._event_books[market.id] = book
            seen = market.id in first_book_seen
            if self._process_event(event, book, market, seen):
                first_book_seen.add(market.id)
            elif not seen and isinstance(event, (SnapshotEvent, DeltaEvent)):
                first_book_seen.add(market.id)

        for m in event_markets:
            self._finalize_market(m)

        self._strategy.on_event_end(self._ctx, evt)
        self._current_event = None
        self._event_books = {}


class AsyncBacktestEngine(_EngineCore):
    async def run(
        self,
        client: Any,
        id: str,
        *,
        after: Any = None,
        before: Any = None,
        **params: Any,
    ) -> BacktestResult:
        # 1. Try as a market UUID
        try:
            market = await client.markets.get(id)
            await self._run_single_market(client, market, after=after, before=before)
            return self._build_result()
        except NotFoundError:
            pass

        # 2. Try as a series
        try:
            series = await client.series.get(id)
        except NotFoundError:
            series = None

        if series is not None:
            if series.structured_type:
                event_params = dict(params)
                if after is not None:
                    event_params["end_after"] = after
                if before is not None:
                    event_params["start_before"] = before
                events = await (await client.series.events(id, **event_params)).to_list()
                for evt in events:
                    event_markets = await client.events.markets(evt.id).to_list()
                    await self._run_event_markets(
                        client, evt, event_markets, after=after, before=before,
                    )
            elif series.is_rolling:
                markets = []
                async for m in client.series.walk(id, after=after, before=before, **params):
                    markets.append(m)
                for market in markets:
                    await self._run_single_market(client, market)
            else:
                raise ValueError(
                    f"Series '{series.title}' is neither rolling nor structured."
                )
            return self._build_result()

        # 3. Fallback: condition ID
        found = await client.markets.list(condition_id=id).to_list()
        if found:
            await self._run_single_market(client, found[0], after=after, before=before)
            return self._build_result()

        raise NotFoundError(404, "NOT_FOUND", f"No market or series found for '{id}'")

    async def _run_single_market(
        self, client: Any, market: Market, *, after: Any = None, before: Any = None,
    ) -> None:
        self._current_market = market
        if self._auto_fees:
            self._fill_sim._fee_model = PolymarketFeeModel.for_category(market.category)
        history_params: dict[str, Any] = {}
        if self._config.include_trades:
            history_params["include_trades"] = True

        history = client.orderbook.history(
            market.id,
            after=after or market.open_time,
            before=before or market.close_time,
            **history_params,
        )
        replay = AsyncOrderBookReplay(
            history, market_id=market.id, platform=market.platform,
        )

        first_book_seen = False
        async for event, book in replay:
            if self._process_event(event, book, market, first_book_seen):
                first_book_seen = True
            elif not first_book_seen and isinstance(event, (SnapshotEvent, DeltaEvent)):
                first_book_seen = True

        self._finalize_market(market)

    async def _run_event_markets(
        self, client: Any, evt: Any, event_markets: list[Market],
        *, after: Any = None, before: Any = None,
    ) -> None:
        self._current_event = evt
        self._event_books = {}
        self._strategy.on_event_start(self._ctx, evt, event_markets)

        history_params: dict[str, Any] = {}
        if self._config.include_trades:
            history_params["include_trades"] = True

        replays: list[tuple[Market, AsyncOrderBookReplay]] = []
        for m in event_markets:
            history = client.orderbook.history(
                m.id,
                after=after or m.open_time,
                before=before or m.close_time,
                **history_params,
            )
            replays.append((
                m, AsyncOrderBookReplay(history, market_id=m.id, platform=m.platform),
            ))

        first_book_seen: set[str] = set()
        async for market, event, book in async_merge_replays(replays):
            if self._auto_fees:
                self._fill_sim._fee_model = PolymarketFeeModel.for_category(market.category)
            self._event_books[market.id] = book
            seen = market.id in first_book_seen
            if self._process_event(event, book, market, seen):
                first_book_seen.add(market.id)
            elif not seen and isinstance(event, (SnapshotEvent, DeltaEvent)):
                first_book_seen.add(market.id)

        for m in event_markets:
            self._finalize_market(m)

        self._strategy.on_event_end(self._ctx, evt)
        self._current_event = None
        self._event_books = {}
