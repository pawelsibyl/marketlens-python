"""Structured product walk — parallel strike books with live surface.

Every tick updates one strike market. walk.books holds the latest book
for ALL sibling strikes, and walk.surface() fits the implied distribution.
"""

from marketlens import MarketLens

client = MarketLens()

walk = client.orderbook.walk("ethereum-multi-strikes-weekly")
for market, book in walk:
    surface = walk.surface()
    if not surface:
        continue
    strikes = surface.survival_strikes()
    curve = "  ".join(f"${s.strike:,.0f}={s.fitted_prob:.3f}" for s in strikes)
    print(
        f"[{walk.event.title}]  {len(walk.books)}/{len(walk.markets)} strikes  "
        f"mean=${float(surface.implied_mean):,.0f}  cv={surface.implied_cv}%  {curve}"
    )

client.close()
