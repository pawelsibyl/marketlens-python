"""Replay a single market's order book tick by tick."""

from datetime import datetime, timezone

from marketlens import MarketLens

client = MarketLens()

market_id = "a23fb05b-2b54-5b69-98b5-568ac3dd4f6b"
start = datetime(2026, 3, 5, 10, 0, tzinfo=timezone.utc)
end = datetime(2026, 3, 5, 10, 5, tzinfo=timezone.utc)

for market, book in client.orderbook.walk(market_id, after=start, before=end):
    print(f"  mid={book.midpoint}  spread={book.spread_bps():.0f}bps  imbalance={book.imbalance():.3f}")

# Or as a DataFrame
df = client.orderbook.walk(market_id, after=start, before=end).to_dataframe()
print(f"\n{len(df)} book states")
print(df[["midpoint", "spread_bps", "imbalance"]].describe())

client.close()
