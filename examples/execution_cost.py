"""Live order book depth and execution cost analysis across order sizes."""

from marketlens import MarketLens

client = MarketLens()
book = client.orderbook.get("a23fb05b-2b54-5b69-98b5-568ac3dd4f6b")

print(f"mid={book.midpoint}  spread={book.spread} ({book.spread_bps():.0f}bps)")
print(f"microprice={book.microprice()}  weighted_mid={book.weighted_midpoint(n=3)}")
print(f"imbalance: full={book.imbalance():.3f}  top3={book.imbalance(levels=3):.3f}")

bid_near, ask_near = book.depth_within("0.02")
print(f"depth within 2c: {bid_near} bid / {ask_near} ask")

for size in ["100", "1000", "5000", "25000"]:
    avg = book.impact("BUY", size)
    slip = book.slippage("BUY", size)
    if avg and slip and book.midpoint:
        bps = float(slip) / float(book.midpoint) * 10_000
        print(f"  ${size:>6} → avg_fill={avg}  slippage={bps:.1f}bps")
    else:
        print(f"  ${size:>6} → insufficient liquidity")
client.close()
