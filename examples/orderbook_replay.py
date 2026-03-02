"""Reconstruct full orderbook state from the history event stream."""

from datetime import datetime, timezone
from marketlens import MarketLens, OrderBookReplay, SnapshotEvent, DeltaEvent, TradeEvent

client = MarketLens()

market_id = "your-market-id-here"
start = datetime(2025, 3, 1, tzinfo=timezone.utc)
end = datetime(2025, 3, 1, 0, 10, tzinfo=timezone.utc)  # 10 minutes

# Fetch history with trades interleaved
history = client.orderbook.history(market_id, after=start, before=end, include_trades=True)

# Option 1: Iterate events with full book state
for event, book in OrderBookReplay(history, market_id=market_id):
    label = event.type.upper()
    line = f"t={event.t}  spread={book.spread}  mid={book.midpoint}  imbalance={book.imbalance():.4f}"

    if isinstance(event, TradeEvent):
        line += f"  TRADE {event.side} {event.size} @ {event.price}"
    elif isinstance(event, DeltaEvent):
        line += f"  DELTA {event.side} {event.price}={event.size}"
    elif isinstance(event, SnapshotEvent):
        line += f"  SNAP {'reseed' if event.is_reseed else 'normal'}"

    print(f"[{label:8s}] {line}")

# Option 2: Get a DataFrame of book metrics over time (re-fetch needed)
history = client.orderbook.history(market_id, after=start, before=end, include_trades=True)
df = OrderBookReplay(history, market_id=market_id).to_dataframe()
print(f"\nReplay DataFrame: {len(df)} rows")
print(df[["best_bid", "best_ask", "spread", "imbalance"]].describe())

client.close()
