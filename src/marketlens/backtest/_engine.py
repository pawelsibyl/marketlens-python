from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from marketlens.exceptions import NotFoundError
from marketlens.backtest._fees import FeeModel, PolymarketFeeModel
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
from marketlens.helpers.replay import AsyncOrderBookReplay, OrderBookReplay
from marketlens.types.history import DeltaEvent, SnapshotEvent, TradeEvent
from marketlens.types.market import Market
from marketlens.types.orderbook import OrderBook

_FOUR = Decimal("0.0001")


@dataclass
class BacktestConfig:
    initial_cash: str = "10000.0000"
    fee_model: FeeModel | None = None
    fee_rate_bps: int = 0
    taker_only: bool = True
    max_fill_fraction: float = 1.0
    include_trades: bool = True


class _EngineCore:
    """Shared logic for sync and async engines."""

    def __init__(self, strategy: Strategy, config: BacktestConfig | None = None) -> None:
        self._strategy = strategy
        self._config = config or BacktestConfig()

        fee_model = self._config.fee_model or PolymarketFeeModel(
            rate_bps=self._config.fee_rate_bps,
        )
        self._fill_sim = FillSimulator(
            fee_model,
            taker_only=self._config.taker_only,
            max_fill_fraction=self._config.max_fill_fraction,
        )
        self._portfolio = Portfolio(self._config.initial_cash)
        self._order_counter = 0
        self._orders: list[Order] = []
        self._open_orders: list[Order] = []
        self._settlements: list[SettlementRecord] = []
        self._equity_curve: list[dict] = []

        self._current_market: Market | None = None
        self._current_book: OrderBook | None = None
        self._current_time: int = 0

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

        if order_type == OrderType.MARKET:
            self._fill_market_order(order)
        else:
            order.status = OrderStatus.OPEN
            self._open_orders.append(order)

        return order

    def cancel_order(self, order: Order) -> None:
        if order.status == OrderStatus.OPEN:
            order.status = OrderStatus.CANCELLED
            self._open_orders = [o for o in self._open_orders if o.id != order.id]

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

    def _fill_market_order(self, order: Order) -> None:
        fill = self._fill_sim.try_fill_market_order(
            order, self._current_book, self._current_time,  # type: ignore[arg-type]
        )
        if fill is None:
            order.status = OrderStatus.CANCELLED
            return
        self._apply_fill(order, fill)

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

        self._portfolio.apply_fill(fill)
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
        self._current_book = book
        self._current_time = event.t
        is_first = False

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
        try:
            market = client.markets.get(id)
            markets = [market]
            is_single = True
        except NotFoundError:
            markets = list(client.series.walk(id, after=after, before=before, **params))
            is_single = False

        for market in markets:
            h_after = after if is_single else None
            h_before = before if is_single else None
            self._run_single_market(client, market, after=h_after, before=h_before)

        return self._build_result()

    def _run_single_market(
        self, client: Any, market: Market, *, after: Any = None, before: Any = None,
    ) -> None:
        self._current_market = market
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
        try:
            market = await client.markets.get(id)
            markets = [market]
            is_single = True
        except NotFoundError:
            markets = []
            async for m in client.series.walk(id, after=after, before=before, **params):
                markets.append(m)
            is_single = False

        for market in markets:
            h_after = after if is_single else None
            h_before = before if is_single else None
            await self._run_single_market(client, market, after=h_after, before=h_before)

        return self._build_result()

    async def _run_single_market(
        self, client: Any, market: Market, *, after: Any = None, before: Any = None,
    ) -> None:
        self._current_market = market
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
