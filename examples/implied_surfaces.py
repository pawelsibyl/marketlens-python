"""Implied probability surfaces from multi-strike prediction markets.

Fetches survival curves, density distributions, and barrier probabilities
derived from live L2 order book midpoints. Updated every 5 minutes.
"""

from marketlens import MarketLens

client = MarketLens()

for surface in client.signals.surfaces(underlying="BTC"):
    print(f"\n{surface.series_title}  [{surface.surface_type}]")
    print(f"  implied mean={surface.implied_mean}  vol={surface.implied_vol}%  skew={surface.implied_skew}")

    if surface.surface_type == "survival":
        for s in surface.survival_strikes():
            fitted = f"{s.fitted_prob:.3f}"
            raw = f"{s.raw_prob:.3f}"
            flag = " *" if abs(s.fitted_prob - s.raw_prob) > 0.01 else ""
            print(f"  K={s.strike:>10,.0f}  P(above)={fitted}  (raw {raw}){flag}")

    elif surface.surface_type == "density":
        for b in surface.density_buckets():
            lo = f"${b.lower:,.0f}" if b.lower else "<tail"
            hi = f"${b.upper:,.0f}" if b.upper else "tail>"
            print(f"  {lo:>10}-{hi:<10}  p={b.normalized_prob:.3f}  (raw {b.prob:.3f})")

    elif surface.surface_type == "barrier":
        for b in surface.barrier_strikes():
            print(f"  {b.direction:>8} ${b.strike:>10,.0f}  P={b.fitted_prob:.3f}  (raw {b.raw_prob:.3f})")

client.close()
