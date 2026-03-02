"""Walk a rolling series and backtest a simple spread-based strategy.

Demonstrates the series.walk() pattern — the primary way to iterate
through related markets for backtesting.
"""

from marketlens import MarketLens, OrderBookReplay

client = MarketLens()

series_id = "btc-up-or-down-daily"

# Walk every resolved market in chronological order
for slot in client.series.walk(series_id, status="resolved"):
    m = slot.market
    print(f"\n--- {m.question} ---")
    print(f"  open={m.open_time}  close={m.close_time}  result={m.winning_outcome}")

    if slot.overlap_with_prev:
        print(f"  Overlap with prev: {slot.overlap_with_prev}ms")
    if slot.gap_from_prev:
        print(f"  Gap from prev: {slot.gap_from_prev}ms")

    # Load 1-minute candles as a DataFrame — types are already float/datetime
    df = slot.candles("1m").to_dataframe()
    if df.empty:
        continue

    print(f"  Candles: {len(df)} rows")
    print(f"  VWAP range: {df['vwap'].min():.4f} – {df['vwap'].max():.4f}")
    print(f"  Volume: {df['volume'].sum():.2f}")

    # Replay orderbook and get a book metrics DataFrame
    history = slot.history(include_trades=True)
    replay_df = OrderBookReplay(history, market_id=m.id).to_dataframe()
    if replay_df.empty:
        continue

    avg_spread = replay_df["spread"].mean()
    avg_imbalance = replay_df["imbalance"].mean()
    print(f"  Avg spread: {avg_spread:.4f}")
    print(f"  Avg imbalance: {avg_imbalance:+.4f}")

client.close()
