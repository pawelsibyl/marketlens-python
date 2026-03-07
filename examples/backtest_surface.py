"""Surface mispricing strategy on a structured product.

Fits an isotonic survival curve from all sibling strike midpoints at every
tick. When the fitted probability exceeds the raw midpoint by a threshold,
the strike is underpriced relative to the curve — buy YES.

Uses on_event_start for market metadata, ctx.event_books for cross-strike
state, and compute_surface for real-time PAVA regression.
"""

from datetime import datetime, timezone

from marketlens import MarketLens
from marketlens.backtest import Strategy
from marketlens.helpers.surface import compute_surface


class SurfaceMispricing(Strategy):
    def __init__(self, series, edge=0.02):
        self.series = series
        self.edge = edge

    def on_event_start(self, ctx, event, markets):
        self._mkts = {m.id: m for m in markets}
        self._traded = set()

    def on_book(self, ctx, market, book):
        if market.id in self._traded:
            return
        surface = compute_surface(ctx.event_books, self._mkts, self.series, ctx.event)
        if not surface:
            return
        for s in surface.survival_strikes():
            if s.market_id == market.id and s.fitted_prob - s.raw_prob > self.edge:
                ctx.buy_yes(size="100")
                self._traded.add(market.id)
                break


client = MarketLens()
series = client.series.get("tsla-multi-strikes-weekly")
result = client.backtest(
    SurfaceMispricing(series), "tsla-multi-strikes-weekly",
    initial_cash="10000.0000",
    after=datetime(2026, 3, 5, 10, 0, tzinfo=timezone.utc),
    before=datetime(2026, 3, 5, 10, 30, tzinfo=timezone.utc),
)
print(result)
print(result.trades_df().to_string())
print(result.settlements_df().to_string())
client.close()
