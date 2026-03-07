"""Imbalance signal with early exit — enter on strong signal, exit when it fades."""

from datetime import datetime, timezone

from marketlens import MarketLens
from marketlens.backtest import Strategy


class ImbalanceTrader(Strategy):
    def on_market_start(self, ctx, market, book):
        self._traded = False

    def on_book(self, ctx, market, book):
        imb = book.imbalance(levels=3)
        if imb is None:
            return
        pos = ctx.position()
        if pos.side == "FLAT" and not self._traded:
            if imb > 0.3:
                ctx.buy_yes(size="200")
                self._traded = True
            elif imb < -0.3:
                ctx.buy_no(size="200")
                self._traded = True
        elif pos.side == "YES" and imb < 0.05:
            ctx.sell_yes(size=pos.shares)
        elif pos.side == "NO" and imb > -0.05:
            ctx.sell_no(size=pos.shares)


client = MarketLens()
result = client.backtest(
    ImbalanceTrader(), "sol-up-or-down-5m",
    after=datetime(2026, 3, 5, 10, 0, tzinfo=timezone.utc),
    before=datetime(2026, 3, 5, 10, 15, tzinfo=timezone.utc),
    initial_cash="10000.0000",
    fees="polymarket",
    slippage_bps=5,
)
print(result)
print(result.trades_df().to_string())
client.close()
