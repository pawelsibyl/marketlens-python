"""Backtest bid-ask spread over time using orderbook metrics."""

from datetime import datetime, timezone
from marketlens import MarketLens

client = MarketLens()

market_id = "your-market-id-here"
start = datetime(2025, 3, 1, tzinfo=timezone.utc)
end = datetime(2025, 3, 2, tzinfo=timezone.utc)

# Fetch 5-minute orderbook metrics — columns are already float/datetime
df = client.orderbook.metrics(
    market_id, after=start, before=end, resolution="5m"
).to_dataframe()

print(f"Samples: {len(df)}")
print(f"Avg spread: {df['spread'].mean():.4f}")
print(f"Avg midpoint: {df['midpoint'].mean():.4f}")
print(f"Avg bid depth: {df['bid_depth'].mean():.2f}")
print(f"Avg ask depth: {df['ask_depth'].mean():.2f}")

# Identify periods of wide spread
wide = df[df["spread"] > 0.05]
if not wide.empty:
    print(f"\nWide spread periods (>5 cents): {len(wide)}")
    print(wide[["spread", "bid_depth", "ask_depth"]].head(10))

client.close()
