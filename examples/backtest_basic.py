"""Minimal backtest — buy YES on tight spread, settle at resolution."""

from datetime import datetime, timezone

from marketlens import MarketLens
from marketlens.backtest import Strategy


class BuyOnTightSpread(Strategy):
    def on_book(self, ctx, market, book):
        if ctx.position().side == "FLAT" and (s := book.spread_bps()) and s < 1000:
            ctx.buy_yes(size="100")


client = MarketLens()
result = client.backtest(
    # BTC Up or Down 5m — walk a few resolved markets in the series
    BuyOnTightSpread(), "btc-up-or-down-5m",
    initial_cash="10000.0000",
    after=datetime(2026, 3, 5, 10, 0, tzinfo=timezone.utc),
    before=datetime(2026, 3, 5, 10, 15, tzinfo=timezone.utc),
)
print(result)
client.close()
