"""Quickstart example for the MarketLens Python SDK."""

from marketlens import MarketLens

# Initialize client (reads MARKETLENS_API_KEY from env if not passed)
client = MarketLens()

# List active markets
for market in client.markets.list(status="active", limit=5):
    print(f"{market.question}  [{market.status}]  vol={market.volume}")

# Get a specific market
market = client.markets.get("your-market-id-here")
print(f"\n{market.question}")
print(f"  Outcomes: {[o.name for o in market.outcomes]}")

# Get recent trades
for trade in client.markets.trades(market.id, limit=10):
    print(f"  {trade.side} {trade.size} @ {trade.price}")

# Get current orderbook
book = client.orderbook.get(market.id)
print(f"\n  Best bid: {book.best_bid}  Best ask: {book.best_ask}  Spread: {book.spread}")

# Price impact analysis
avg_price = book.impact("BUY", "500.00")
print(f"  Market buy $500 → avg price: {avg_price}")

# Convert to DataFrame (requires pip install marketlens[pandas])
df = client.markets.candles(market.id, resolution="1h").to_dataframe()
print(f"\n  Candles shape: {df.shape}")

client.close()
