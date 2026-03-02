from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

_FOUR = Decimal("0.0001")
_ZERO = Decimal("0")


class PriceLevel(BaseModel):
    model_config = ConfigDict(frozen=True)

    price: str
    size: str


class OrderBook(BaseModel):
    model_config = ConfigDict(frozen=True)

    market_id: str
    platform: str
    as_of: int
    bids: list[PriceLevel]
    asks: list[PriceLevel]
    best_bid: str | None = None
    best_ask: str | None = None
    spread: str | None = None
    midpoint: str | None = None
    bid_depth: str | None = None
    ask_depth: str | None = None
    bid_levels: int
    ask_levels: int

    def impact(self, side: str, size: str) -> str | None:
        """Volume-weighted average execution price for a hypothetical market order.

        Args:
            side: "BUY" or "SELL".
            size: Order size in USD as a decimal string.

        Returns:
            Average execution price as a 4-decimal string, or None if
            insufficient liquidity.
        """
        remaining = Decimal(size)
        levels = self.asks if side == "BUY" else self.bids
        total_cost = _ZERO
        total_filled = _ZERO

        for level in levels:
            level_size = Decimal(level.size)
            level_price = Decimal(level.price)
            fill = min(remaining, level_size)
            total_cost += fill * level_price
            total_filled += fill
            remaining -= fill
            if remaining <= 0:
                break

        if total_filled == 0:
            return None
        avg = total_cost / total_filled
        return str(avg.quantize(_FOUR))

    def depth_within(self, spread: str) -> tuple[str, str]:
        """Total size on each side within ``spread`` of midpoint.

        Args:
            spread: Maximum distance from midpoint as a decimal string.

        Returns:
            ``(bid_depth, ask_depth)`` as 4-decimal strings.
        """
        if self.midpoint is None:
            return ("0.0000", "0.0000")

        mid = Decimal(self.midpoint)
        max_spread = Decimal(spread)

        bid_total = _ZERO
        for level in self.bids:
            if mid - Decimal(level.price) <= max_spread:
                bid_total += Decimal(level.size)

        ask_total = _ZERO
        for level in self.asks:
            if Decimal(level.price) - mid <= max_spread:
                ask_total += Decimal(level.size)

        return (str(bid_total.quantize(_FOUR)), str(ask_total.quantize(_FOUR)))

    def slippage(self, side: str, size: str) -> str | None:
        """Difference between midpoint and average execution price.

        Args:
            side: "BUY" or "SELL".
            size: Order size in USD as a decimal string.

        Returns:
            Slippage as a 4-decimal string (always non-negative), or None
            if midpoint is unavailable or insufficient liquidity.
        """
        if self.midpoint is None:
            return None
        avg = self.impact(side, size)
        if avg is None:
            return None
        diff = abs(Decimal(avg) - Decimal(self.midpoint))
        return str(diff.quantize(_FOUR))

    def imbalance(self) -> float | None:
        """Order book imbalance: ``(bid_depth - ask_depth) / (bid_depth + ask_depth)``.

        Returns a float in ``[-1, 1]``, or ``None`` if the book is empty.
        A positive value indicates more resting liquidity on the bid side.
        """
        if self.bid_depth is None or self.ask_depth is None:
            return None
        bd = Decimal(self.bid_depth)
        ad = Decimal(self.ask_depth)
        total = bd + ad
        if total == 0:
            return None
        return float((bd - ad) / total)

    def weighted_midpoint(self, n: int = 1) -> str | None:
        """Size-weighted midpoint from the top *n* levels on each side.

        More responsive than the simple midpoint when the best level has
        thin liquidity.  With ``n=1`` this is the classic weighted mid::

            wmid = (best_bid * ask_size + best_ask * bid_size)
                 / (bid_size + ask_size)

        Args:
            n: Number of top levels to include from each side.

        Returns:
            Weighted midpoint as a 4-decimal string, or ``None`` if either
            side has no levels.
        """
        top_bids = self.bids[:n]
        top_asks = self.asks[:n]
        if not top_bids or not top_asks:
            return None

        bid_value = sum(Decimal(l.price) * Decimal(l.size) for l in top_bids)
        bid_size = sum(Decimal(l.size) for l in top_bids)
        ask_value = sum(Decimal(l.price) * Decimal(l.size) for l in top_asks)
        ask_size = sum(Decimal(l.size) for l in top_asks)

        total_size = bid_size + ask_size
        if total_size == 0:
            return None

        # Weight each side's VWAP by the opposite side's size
        # wmid = (bid_vwap * ask_size + ask_vwap * bid_size) / total_size
        wmid = (bid_value / bid_size * ask_size + ask_value / ask_size * bid_size) / total_size
        return str(wmid.quantize(_FOUR))


class BookMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    t: int
    best_bid: str | None = None
    best_ask: str | None = None
    spread: str | None = None
    midpoint: str | None = None
    bid_depth: str | None = None
    ask_depth: str | None = None
    bid_levels: int
    ask_levels: int
