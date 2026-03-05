"""Microstructure feature matrix from L2 replay."""

from datetime import datetime, timezone

from marketlens import MarketLens

client = MarketLens()

df = client.orderbook.walk(
    "btc-up-or-down-5m",
    status="resolved",
    after=datetime(2026, 3, 5, 8, 40, tzinfo=timezone.utc),
    before=datetime(2026, 3, 5, 8, 45, tzinfo=timezone.utc),
).to_dataframe()

features = df.groupby("market_id").agg(
    outcome=("winning_outcome", "first"),
    imbalance=("imbalance", "mean"),
    spread_bps=("spread_bps", "mean"),
    mid_start=("midpoint", "first"),
    mid_end=("midpoint", "last"),
)
features["return"] = features["mid_end"] / features["mid_start"] - 1
features["won_up"] = features["outcome"] == "Up"

bullish = features[features["imbalance"] > 0]["won_up"].mean()
bearish = features[features["imbalance"] < 0]["won_up"].mean()
print(f"{len(features)} markets, {len(df):,} book states")
print(f"Imbalance > 0 → Up won {bullish:.0%} | Imbalance < 0 → Up won {bearish:.0%}")
client.close()
