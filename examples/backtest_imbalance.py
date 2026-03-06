"""Trade order book imbalance signal, exit before settlement.

Enters once per market when imbalance is strong, exits when signal fades.
"""

from datetime import datetime, timezone

from marketlens import MarketLens
from marketlens.backtest import Strategy

class ImbalanceTrader(Strategy):
    def __init__(self, entry=0.3, exit_at=0.05):
        self.entry = entry
        self.exit_at = exit_at
        self._traded = False

    def on_market_start(self, ctx, market, book):
        self._traded = False

    def on_book(self, ctx, market, book):
        pos = ctx.position()
        imb = book.imbalance(levels=3)
        if imb is None:
            return

        if pos.side == "FLAT" and not self._traded:
            if imb > self.entry:
                ctx.buy_yes(size="200")
                self._traded = True
            elif imb < -self.entry:
                ctx.buy_no(size="200")
                self._traded = True
        elif pos.side == "YES" and imb < self.exit_at:
            ctx.sell_yes(size=pos.shares)
        elif pos.side == "NO" and imb > -self.exit_at:
            ctx.sell_no(size=pos.shares)


client = MarketLens()
result = client.backtest(
    ImbalanceTrader(),
    "btc-up-or-down-5m",
    after=datetime(2026, 3, 5, 10, 0, tzinfo=timezone.utc),
    before=datetime(2026, 3, 5, 10, 3, tzinfo=timezone.utc),
    fee_rate_bps=200,
    slippage_bps=5,
)
print(result)
print()
print("Trades:")
print(result.trades_df().to_string())
client.close()
