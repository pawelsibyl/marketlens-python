"""Enter each market when spread tightens below threshold.

Uses orderbook.walk() with a rolling series slug — markets form a
continuous chain where each close feeds into the next open.
"""

from datetime import datetime, timezone

from marketlens import MarketLens

client = MarketLens()
pnl, trades, wins = 0.0, 0, 0
current_id, entered = None, False

for market, book in client.orderbook.walk(
    "btc-up-or-down-5m",
    after=datetime(2026, 3, 5, 8, 40, tzinfo=timezone.utc),
    before=datetime(2026, 3, 5, 8, 43, tzinfo=timezone.utc),
):
    if market.id != current_id:
        current_id, entered = market.id, False
    if entered or market.winning_outcome is None:
        continue
    if (spread := book.spread_bps()) and spread < 200:
        if entry := book.impact("BUY", "100"):
            payout = 1.0 if market.winning_outcome == "Up" else 0.0
            pnl += (payout - float(entry)) * 100
            trades += 1
            wins += payout == 1.0
            entered = True

print(f"{trades} trades | {wins/max(trades,1)*100:.0f}% win rate | P&L ${pnl:+.2f}")
client.close()
