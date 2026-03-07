"""Rolling series backtest — spread-timing strategy across sequential markets.

Each market in a rolling series represents a successive time window.
The engine walks them in order, settling each before moving to the next.
"""

from datetime import datetime, timezone

from marketlens import MarketLens
from marketlens.backtest import Strategy


class SpreadTimer(Strategy):
    def on_market_start(self, ctx, market, book):
        self._entered = False

    def on_book(self, ctx, market, book):
        if self._entered:
            return
        if (s := book.spread_bps()) and s < 300 and book.imbalance(levels=3) > 0.1:
            ctx.buy_yes(size="200")
            self._entered = True


client = MarketLens()
result = client.backtest(
    SpreadTimer(), "solana-up-or-down-hourly",
    initial_cash="10000.0000",
    after=datetime(2026, 3, 5, 12, 0, tzinfo=timezone.utc),
    before=datetime(2026, 3, 5, 13, 0, tzinfo=timezone.utc),
)
print(result)
print(result.trades_df().to_string())
client.close()
