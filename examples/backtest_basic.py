"""Buy YES on tight spread, settle at resolution — minimal backtest example.

Backtests a single resolved market by ID.
"""

from marketlens import MarketLens
from marketlens.backtest import Strategy

class BuyOnTightSpread(Strategy):
    def on_book(self, ctx, market, book):
        if ctx.position().side == "FLAT" and book.spread_bps() and book.spread_bps() < 200:
            ctx.buy_yes(size="100")


client = MarketLens()
result = client.backtest(
    BuyOnTightSpread(),
    "9bc96c99-b036-50fd-85f7-bb4f5ae049e2",
)
print(result)
client.close()
