"""Place limit orders around the midpoint — basic market-making backtest.

Posts a buy limit below mid on each new market. When filled, posts a
sell limit above entry. Uses trade-confirmed fills (conservative).
"""

from datetime import datetime, timezone

from marketlens import MarketLens
from marketlens.backtest import Strategy

class LimitTrader(Strategy):
    def on_market_start(self, ctx, market, book):
        if book.midpoint:
            mid = float(book.midpoint)
            ctx.buy_yes(size="50", limit_price=f"{mid - 0.02:.4f}")

    def on_fill(self, ctx, market, fill):
        if fill.side.value.startswith("BUY"):
            ctx.sell_yes(
                size=fill.size,
                limit_price=f"{float(fill.price) + 0.04:.4f}",
            )


client = MarketLens()
result = client.backtest(
    LimitTrader(),
    "btc-up-or-down-5m",
    after=datetime(2026, 3, 5, 10, 0, tzinfo=timezone.utc),
    before=datetime(2026, 3, 5, 10, 3, tzinfo=timezone.utc),
    include_trades=True,
    limit_fill_rate=0.2,
)
print(result)
print()
print("Orders:")
print(result.orders_df().to_string())
client.close()
