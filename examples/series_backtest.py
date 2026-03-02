"""Momentum backtest: if prev market's last candle > 0.50, buy "Up" at book impact price."""

from datetime import datetime, timezone

from marketlens import MarketLens

SERIES = "btc-up-or-down-5m"
STAKE = 100.0
SINCE = datetime(2026, 3, 2, 12, 0, tzinfo=timezone.utc)
UNTIL = datetime(2026, 3, 2, 14, 0, tzinfo=timezone.utc)

client = MarketLens()

pnl = 0.0
wins = 0
trades = 0
prev_close: float | None = None

for slot in client.series.walk(SERIES, status="resolved", after=SINCE, before=UNTIL):
    m = slot.market
    if m.winning_outcome is None:
        continue

    candles = slot.candles("1m").to_dataframe()
    if candles.empty:
        prev_close = None
        continue
    last_close = float(candles["close"].iloc[-1])

    if prev_close is not None and prev_close > 0.50:
        book = slot.orderbook()
        entry = book.impact("BUY", str(STAKE))
        if entry is not None:
            payout = 1.0 if m.winning_outcome == "Up" else 0.0
            trade_pnl = (payout - float(entry)) * STAKE
            pnl += trade_pnl
            trades += 1
            wins += payout == 1.0
            print(f"  {m.question:<55} entry={entry}  pnl={trade_pnl:+.2f}")

    prev_close = last_close

print(f"\n{trades} trades  win rate {wins}/{trades} ({wins / trades * 100:.1f}%)  cumulative P&L ${pnl:+.2f}")
client.close()
