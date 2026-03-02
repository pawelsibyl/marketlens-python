"""Does top-of-book imbalance predict direction in btc-up-or-down-5m?

Replays the first 100 resolved markets. For each, computes mean top-3
imbalance across all L2 updates, then checks if sign matches outcome.
"""

from marketlens import MarketLens, OrderBookReplay

SERIES = "btc-up-or-down-5m"
N_MARKETS = 100
client = MarketLens()

correct = 0
total = 0

for slot in client.series.walk(SERIES, status="resolved"):
    if total >= N_MARKETS:
        break

    m = slot.market
    if m.winning_outcome is None:
        continue

    imbalances = [
        imb
        for _, book in OrderBookReplay(slot.history(), market_id=m.id)
        if (imb := book.imbalance(levels=3)) is not None
    ]
    if not imbalances:
        continue

    mean_imb = sum(imbalances) / len(imbalances)
    predicted = "Up" if mean_imb > 0 else "Down"
    total += 1
    correct += predicted == m.winning_outcome

print(f"Top-3 imbalance signal — {correct}/{total} correct ({correct / total * 100:.1f}%, baseline 50%)")
client.close()
