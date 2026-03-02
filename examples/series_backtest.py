"""Momentum backtest on btc-up-or-down-5m.

Signal: if the previous market's last 1m candle closed > 0.50, buy "Up"
on the next market at book impact() price. Binary P&L per trade.
"""

from marketlens import MarketLens

SERIES = "btc-up-or-down-5m"
STAKE = 100.0
client = MarketLens()

pnl = 0.0
wins = 0
trades = 0
prev_close: float | None = None

for slot in client.series.walk(SERIES, status="resolved"):
    m = slot.market
    if m.winning_outcome is None:
        continue

    candles = slot.candles("1m").to_dataframe()
    if candles.empty:
        prev_close = None
        continue
    last_close = float(candles["close"].iloc[-1])

    if prev_close is not None and prev_close > 0.50:
        avg = slot.orderbook().impact("BUY", str(STAKE))
        if avg is not None:
            entry = float(avg)
            payout = 1.0 if m.winning_outcome == "Up" else 0.0
            pnl += (payout - entry) * STAKE
            trades += 1
            wins += payout == 1.0

    prev_close = last_close

print(f"{trades} trades  win {wins}/{trades} ({wins / trades * 100:.1f}%)  P&L ${pnl:+.2f}")
client.close()
