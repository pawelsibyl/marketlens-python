"""Spread and slippage distributions for a $100 BUY across btc-up-or-down-5m.

Samples each resolved market's book at the temporal midpoint and collects
spread_bps, slippage_bps, and entry price.
"""

from marketlens import MarketLens

SERIES = "btc-up-or-down-5m"
ORDER_SIZE = "100"
client = MarketLens()

spreads: list[float] = []
slippages: list[float] = []
entries: list[float] = []

for slot in client.series.walk(SERIES, status="resolved"):
    m = slot.market
    if m.open_time is None or m.close_time is None:
        continue

    book = slot.orderbook(at=(m.open_time + m.close_time) // 2)
    sbps = book.spread_bps()
    slip = book.slippage("BUY", ORDER_SIZE)
    avg = book.impact("BUY", ORDER_SIZE)
    if sbps is None or slip is None or avg is None or book.midpoint is None:
        continue

    spreads.append(sbps)
    slippages.append(float(slip) / float(book.midpoint) * 10_000)
    entries.append(float(avg))

spreads.sort()
slippages.sort()
entries.sort()
n = len(spreads)

def pct(lst: list[float], p: float) -> float:
    return lst[min(int(len(lst) * p), len(lst) - 1)]

print(f"${ORDER_SIZE} BUY across {n} markets")
print(f"  spread   — median {pct(spreads, .5):.0f}  p95 {pct(spreads, .95):.0f}  max {spreads[-1]:.0f} bps")
print(f"  slippage — median {pct(slippages, .5):.1f}  p95 {pct(slippages, .95):.1f}  max {slippages[-1]:.1f} bps")
print(f"  entry    — [{entries[0]:.4f}, {pct(entries, .5):.4f}, {entries[-1]:.4f}]")
client.close()
