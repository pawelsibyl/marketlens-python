"""Replay a single market's order book and summarize via DataFrame."""

from datetime import datetime, timezone

from marketlens import MarketLens

client = MarketLens()

df = client.orderbook.walk(
    "a23fb05b-2b54-5b69-98b5-568ac3dd4f6b",
    after=datetime(2026, 3, 5, 10, 0, tzinfo=timezone.utc),
    before=datetime(2026, 3, 5, 10, 5, tzinfo=timezone.utc),
).to_dataframe()

print(f"{len(df)} book states")
print(df[["midpoint", "spread_bps", "imbalance"]].describe())
client.close()
