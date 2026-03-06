"""Browse strike-level markets in a non-rolling series."""

from itertools import islice

from marketlens import MarketLens

client = MarketLens()

for event in islice(client.series.events("ethereum-neg-risk-weekly"), 2):
    markets = client.events.markets(event.id).to_list()
    print(f"\n{event.title} ({len(markets)} strikes)")
    for m in markets:
        book = client.orderbook.get(m.id)
        print(f"  {m.question:<45} mid={book.midpoint}  imbalance={book.imbalance():.3f}")

client.close()
