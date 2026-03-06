from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from marketlens.backtest._fees import FeeModel
from marketlens.backtest._types import Fill, Order, OrderSide

if TYPE_CHECKING:
    from marketlens.types.history import TradeEvent
    from marketlens.types.orderbook import OrderBook

_FOUR = Decimal("0.0001")
_ZERO = Decimal("0")
_ONE = Decimal("1")


class FillSimulator:
    def __init__(
        self,
        fee_model: FeeModel,
        *,
        taker_only: bool = True,
        max_fill_fraction: float = 1.0,
    ) -> None:
        self._fee_model = fee_model
        self._taker_only = taker_only
        self._max_fill_fraction = Decimal(str(max_fill_fraction))

    def try_fill_market_order(
        self, order: Order, book: OrderBook, timestamp: int,
    ) -> Fill | None:
        remaining = Decimal(order.size) - Decimal(order.filled_size)
        if remaining <= 0:
            return None

        # BUY_YES / SELL_NO walk asks; SELL_YES / BUY_NO walk bids
        if order.side in (OrderSide.BUY_YES, OrderSide.SELL_NO):
            levels = book.asks
        else:
            levels = book.bids

        total_filled = _ZERO
        total_cost = _ZERO  # in YES-price space

        for level in levels:
            available = Decimal(level.size) * self._max_fill_fraction
            level_price = Decimal(level.price)
            fill = min(remaining - total_filled, available)
            if fill <= 0:
                break
            total_cost += fill * level_price
            total_filled += fill
            if total_filled >= remaining:
                break

        if total_filled == 0:
            return None

        yes_vwap = total_cost / total_filled

        # Convert to the order's price space
        if order.side in (OrderSide.BUY_NO, OrderSide.SELL_NO):
            fill_price = _ONE - yes_vwap
        else:
            fill_price = yes_vwap

        fill_price_str = str(fill_price.quantize(_FOUR))
        fill_size_str = str(total_filled.quantize(_FOUR))
        fee = self._fee_model.calculate(fill_price, total_filled, is_maker=False)

        return Fill(
            order_id=order.id,
            market_id=order.market_id,
            side=order.side,
            price=fill_price_str,
            size=fill_size_str,
            fee=str(fee.quantize(_FOUR)),
            timestamp=timestamp,
            is_maker=False,
        )

    def try_fill_limit_order(
        self,
        order: Order,
        book: OrderBook,
        trade: TradeEvent | None,
        timestamp: int,
    ) -> Fill | None:
        if trade is None:
            return None

        remaining = Decimal(order.size) - Decimal(order.filled_size)
        if remaining <= 0:
            return None

        limit_price = Decimal(order.limit_price)  # type: ignore[arg-type]
        trade_price = Decimal(trade.price)
        trade_size = Decimal(trade.size)

        triggered = False
        if order.side == OrderSide.BUY_YES:
            triggered = trade.side == "SELL" and trade_price <= limit_price
        elif order.side == OrderSide.SELL_YES:
            triggered = trade.side == "BUY" and trade_price >= limit_price
        elif order.side == OrderSide.BUY_NO:
            yes_threshold = _ONE - limit_price
            triggered = trade.side == "BUY" and trade_price >= yes_threshold
        elif order.side == OrderSide.SELL_NO:
            yes_threshold = _ONE - limit_price
            triggered = trade.side == "SELL" and trade_price <= yes_threshold

        if not triggered:
            return None

        fill_size = min(remaining, trade_size)
        fee = self._fee_model.calculate(limit_price, fill_size, is_maker=True)

        return Fill(
            order_id=order.id,
            market_id=order.market_id,
            side=order.side,
            price=str(limit_price.quantize(_FOUR)),
            size=str(fill_size.quantize(_FOUR)),
            fee=str(fee.quantize(_FOUR)),
            timestamp=timestamp,
            is_maker=True,
        )
