"""Replay a single market's full L2 book and extract microstructure signals."""

from datetime import datetime, timezone

from marketlens import MarketLens, OrderBookReplay

client = MarketLens()

# Grab one recently resolved BTC 5-min market
slot = next(client.series.walk(
    "btc-up-or-down-5m", status="resolved", after=datetime(2026, 3, 2, tzinfo=timezone.utc),
))

df = OrderBookReplay(slot.history(include_trades=True), market_id=slot.market.id).to_dataframe()

trades = df[df["event_type"] == "trade"]
books = df[df["event_type"] != "trade"].dropna(subset=["midpoint"])

print(f"{slot.market.question}  ->  {slot.market.winning_outcome}")
print(f"  {len(books):,} book updates, {len(trades):,} trades over {(df.index[-1] - df.index[0]).total_seconds():.0f}s")
print(f"  midpoint drift:  {books['midpoint'].iloc[0]:.4f} -> {books['midpoint'].iloc[-1]:.4f}")
print(f"  microprice mean: {books['weighted_midpoint'].mean():.4f}  (vs midpoint {books['midpoint'].mean():.4f})")
print(f"  imbalance:       mean={books['imbalance'].mean():+.3f}  std={books['imbalance'].std():.3f}")
print(f"  spread:          mean={books['spread'].mean():.4f}  ({books['spread_bps'].mean():.0f} bps)")
if not trades.empty:
    print(f"  trades:          {trades['trade_size'].sum():,.0f} USD  avg size {trades['trade_size'].mean():.1f}")
client.close()
