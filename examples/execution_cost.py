"""Analyze execution costs across order sizes on a live order book."""

from marketlens import MarketLens

client = MarketLens()
market = client.markets.list(status="active", sort="-liquidity", limit=1).first_page()[0]
book = client.orderbook.get(market.id)

print(f"{market.question}")
print(f"  {book.bid_levels} bids ({book.bid_depth} USD)  {book.ask_levels} asks ({book.ask_depth} USD)")
print(f"  spread: {book.spread} ({book.spread_bps():.0f} bps)  midpoint: {book.midpoint}")
print(f"  microprice: {book.microprice()}  weighted mid: {book.weighted_midpoint(n=3)}")
print(f"  imbalance: {book.imbalance():.3f} (full book)  {book.imbalance(levels=3):.3f} (top 3)")

bid_near, ask_near = book.depth_within("0.02")
print(f"  depth within 2c of mid: {bid_near} bid / {ask_near} ask")

print(f"  {'size':>8}  {'avg fill':>10}  {'slippage':>10}  {'impact bps':>10}")
for size in ["100", "1000", "5000", "25000"]:
    avg = book.impact("BUY", size)
    slip = book.slippage("BUY", size)
    if avg and slip and book.midpoint:
        bps = float(slip) / float(book.midpoint) * 10_000
        print(f"  ${size:>7}  {avg:>10}  {slip:>10}  {bps:>9.1f}")
    else:
        print(f"  ${size:>7}  insufficient liquidity")
client.close()
