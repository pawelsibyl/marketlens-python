"""Multi-market backtesting audit — fast, targeted tests.

Uses 2s windows for rolling crypto markets (~300-700 events) and
30s windows for structured markets (~1-5 events per strike).
All tests should complete in seconds.
"""
import os, sys, time
from decimal import Decimal
from datetime import datetime, timezone

os.environ['MARKETLENS_API_KEY'] = 'mk_86d4426fa515d340b00550cfca0ea22f'
sys.stdout.reconfigure(line_buffering=True)

from marketlens import MarketLens
from marketlens.backtest import Strategy

BASE = 'http://89.167.64.221:8000/v1'

# ── Rolling 5m markets ──
# Slot A: 15:55-16:00 UTC (for pure-rolling tests)
BTC_M1 = '8e15d535-4d76-5768-9228-fff40a742b7a'  # win=0 (YES wins)
ETH_M1 = 'e53bdeb6-b110-51b1-a552-9a8e337e5929'  # win=0
ETH_M2 = 'b38824b1-4444-5ede-872e-46922d388506'  # win=1 (NO wins)
SOL_M1 = '128bc32e-798c-50eb-9b46-6a20988611e2'  # win=0

# Slot B: 16:15-16:20 UTC (overlaps with structured data, for mixed tests)
BTC_MB = '633bfaf2-00dd-59b1-9233-0b4587fa55d7'  # win=0
ETH_MB = 'd9ac299d-4a14-5f16-8cb4-82cdb19d3139'  # win=0
SOL_MB = '310cec24-a201-52f7-b508-d2012dfaed75'  # win=1

# Series IDs
BTC_SERIES = '79e1c1db-2392-50bd-9219-85cc05c1355d'
ETH_SERIES = '3646ad0d-9de8-5d89-8f48-4c150e0e66d3'
SOL_SERIES = 'ac7ea6cf-140a-5d19-8712-8aeb852128f4'

# Structured: Bitcoin Hit Price Daily (barrier) — 1 event on March 8, 11 markets
STRUCT_SERIES = 'b3ff0275-62cf-5f97-a36c-cf7c6cb120fb'

# Time windows
# Slot A: 2s for pure-rolling tests
ROLL_AFTER  = datetime(2026, 3, 8, 15, 55, 0, tzinfo=timezone.utc)
ROLL_BEFORE = datetime(2026, 3, 8, 15, 55, 2, tzinfo=timezone.utc)

# Slot B: 2s window where both structured barrier data AND rolling 16:15 markets exist
MIX_AFTER  = datetime(2026, 3, 8, 16, 19, 41, tzinfo=timezone.utc)
MIX_BEFORE = datetime(2026, 3, 8, 16, 19, 43, tzinfo=timezone.utc)

# ── Test helpers ──
PASS = FAIL = 0
ISSUES = []

def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        ISSUES.append((name, detail))
        print(f"  FAIL: {name} -- {detail}")

def timed(label):
    class Timer:
        def __enter__(self):
            self.t0 = time.time()
            return self
        def __exit__(self, *a):
            elapsed = time.time() - self.t0
            print(f"  ({elapsed:.1f}s) {label}")
            if elapsed > 10:
                print(f"  WARNING: slow! ({elapsed:.0f}s)")
    return Timer()


# ── Strategies ──

class BuyOnce(Strategy):
    """Buy 50 YES on first book of each market."""
    def on_market_start(self, ctx, market, book):
        self._bought = False
    def on_book(self, ctx, market, book):
        if not self._bought and ctx.position().side == "FLAT":
            ctx.buy_yes(size="50")
            self._bought = True


class CrossMarketTrader(Strategy):
    """On seeing src market, places order on tgt market."""
    def __init__(self, src, tgt):
        self.src, self.tgt, self._done = src, tgt, False
    def on_book(self, ctx, market, book):
        if market.id == self.src and not self._done and book.midpoint:
            ctx.buy_yes(size="50", market_id=self.tgt)
            self._done = True


class BooksTracker(Strategy):
    """Tracks max concurrent books and unique market IDs seen. Optionally buys."""
    def __init__(self, buy=False):
        self.max_books = 0
        self.market_ids = set()
        self.market_start_count = 0
        self._buy = buy
        self._bought_mkts: set = set()
    def on_market_start(self, ctx, market, book):
        self.market_start_count += 1
    def on_book(self, ctx, market, book):
        self.max_books = max(self.max_books, len(ctx.books))
        self.market_ids.add(market.id)
        if self._buy and market.id not in self._bought_mkts:
            if ctx.position().side == "FLAT":
                ctx.buy_yes(size="50")
                self._bought_mkts.add(market.id)


class PropChecker(Strategy):
    """Verifies ctx properties and backwards-compat aliases."""
    def __init__(self):
        self.new_ok = self.old_ok = True
        self.books_has_self = True
    def on_book(self, ctx, market, book):
        try:
            assert ctx.market.id == market.id
            assert ctx.book is book
            assert ctx.time > 0
            assert market.id in ctx.books
        except: self.new_ok = False
        try:
            assert ctx.current_market.id == market.id
            assert ctx.current_book is book
            assert ctx.current_time > 0
            assert market.id in ctx.event_books
        except: self.old_ok = False
        if market.id not in ctx.books:
            self.books_has_self = False


# ── Connect ──
c = MarketLens(base_url=BASE)
print("Connected.\n")


# ════════════════════════════════════════════════════
#  SINGLE INPUTS
# ════════════════════════════════════════════════════

print("=" * 60)
print("SINGLE INPUTS")
print("=" * 60)

# T1: Single market UUID
print("\n--- T1: Single market UUID ---")
with timed("single market"):
    r = c.backtest(BuyOnce(), BTC_M1, initial_cash="10000", after=ROLL_AFTER, before=ROLL_BEFORE)
check("has settlements", len(r._settlements) > 0, f"{len(r._settlements)}")
check("has trades", r.total_trades > 0, f"{r.total_trades}")
if r._settlements:
    s = r._settlements[0]
    check("market_id correct", s.market_id == BTC_M1)
    check("series_id populated", s.series_id is not None, f"{s.series_id}")
    expected = (Decimal(s.settlement_price) - Decimal(s.avg_entry_price)) * Decimal(s.shares)
    check("pnl math", Decimal(s.pnl) == expected.quantize(Decimal("0.0001")),
          f"expected={expected} actual={s.pnl}")

# T2: Single rolling series
print("\n--- T2: Single rolling series ---")
with timed("rolling series"):
    r = c.backtest(BuyOnce(), SOL_SERIES, initial_cash="10000", after=ROLL_AFTER, before=ROLL_BEFORE)
check("has settlements", len(r._settlements) > 0, f"{len(r._settlements)}")
check("series_id on settlement", any(s.series_id == SOL_SERIES for s in r._settlements))

# T3: Single structured series
print("\n--- T3: Single structured series ---")
with timed("structured series"):
    bt = BooksTracker()
    r = c.backtest(bt, STRUCT_SERIES, initial_cash="10000",
                   after=MIX_AFTER, before=MIX_BEFORE)
check("no crash", True)
check("saw multiple markets", len(bt.market_ids) >= 2, f"saw {len(bt.market_ids)}")
check("books had sibling strikes", bt.max_books >= 2, f"max={bt.max_books}")
check("on_market_start fired per market", bt.market_start_count >= 2,
      f"starts={bt.market_start_count}")


# ════════════════════════════════════════════════════
#  PAIRS
# ════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("PAIRS")
print("=" * 60)

# T4: Two market UUIDs (different outcomes)
print("\n--- T4: Two market UUIDs (win=0 + win=1) ---")
with timed("two markets"):
    r = c.backtest(BuyOnce(), [BTC_M1, ETH_M2], initial_cash="10000",
                   after=ROLL_AFTER, before=ROLL_BEFORE)
settled = {s.market_id for s in r._settlements}
check("both settled", BTC_M1 in settled and ETH_M2 in settled, f"{settled}")
btc_s = [s for s in r._settlements if s.market_id == BTC_M1]
eth_s = [s for s in r._settlements if s.market_id == ETH_M2]
if btc_s: check("BTC YES profits (win=0)", Decimal(btc_s[0].pnl) > 0, f"{btc_s[0].pnl}")
if eth_s: check("ETH YES loses (win=1)", Decimal(eth_s[0].pnl) < 0, f"{eth_s[0].pnl}")
check("shared cash", Decimal(r._portfolio.cash) < Decimal("20000"))

# T5: str vs [str] equivalence
print("\n--- T5: str vs [str] equivalence ---")
with timed("two runs"):
    ra = c.backtest(BuyOnce(), BTC_M1, initial_cash="10000", after=ROLL_AFTER, before=ROLL_BEFORE)
    rb = c.backtest(BuyOnce(), [BTC_M1], initial_cash="10000", after=ROLL_AFTER, before=ROLL_BEFORE)
check("same pnl", ra.total_pnl == rb.total_pnl, f"{ra.total_pnl} vs {rb.total_pnl}")
check("same trades", ra.total_trades == rb.total_trades)
check("same fees", ra.total_fees == rb.total_fees)

# T6: Two rolling series
print("\n--- T6: Two rolling series ---")
with timed("two series"):
    r = c.backtest(BuyOnce(), [BTC_SERIES, SOL_SERIES], initial_cash="10000",
                   after=ROLL_AFTER, before=ROLL_BEFORE)
bs = r.by_series()
check("by_series has 2+ groups", len(bs) >= 2, f"{len(bs)}: {list(bs.keys())}")
check("has settlements", len(r._settlements) >= 2, f"{len(r._settlements)}")

# T7: Rolling series + market UUID
print("\n--- T7: Rolling series + market UUID ---")
with timed("series + uuid"):
    r = c.backtest(BuyOnce(), [SOL_SERIES, BTC_M1], initial_cash="10000",
                   after=ROLL_AFTER, before=ROLL_BEFORE)
settled = {s.market_id for s in r._settlements}
check("BTC market settled", BTC_M1 in settled, f"{settled}")
check("2+ markets settled", len(settled) >= 2, f"{len(settled)}")

# T8: Structured series + market UUID
print("\n--- T8: Structured series + market UUID ---")
with timed("struct + uuid"):
    bt = BooksTracker(buy=True)
    r = c.backtest(bt, [STRUCT_SERIES, BTC_MB], initial_cash="10000",
                   after=MIX_AFTER, before=MIX_BEFORE)
check("no crash", True)
check("BTC market in settlements", BTC_MB in {s.market_id for s in r._settlements},
      f"settled: {[s.market_id[:8] for s in r._settlements]}")
check("saw structured + rolling mkts", len(bt.market_ids) >= 3,
      f"saw {len(bt.market_ids)}")

# T9: Structured series + rolling series
print("\n--- T9: Structured series + rolling series ---")
with timed("struct + rolling"):
    bt = BooksTracker(buy=True)
    r = c.backtest(bt, [STRUCT_SERIES, SOL_SERIES], initial_cash="10000",
                   after=MIX_AFTER, before=MIX_BEFORE)
check("no crash", True)
check("SOL in settlements", any(s.series_id == SOL_SERIES for s in r._settlements),
      f"series_ids={[s.series_id[:8] if s.series_id else None for s in r._settlements]}")
check("saw structured markets", len(bt.market_ids) >= 3, f"saw {len(bt.market_ids)}")


# ════════════════════════════════════════════════════
#  TRIPLES
# ════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("TRIPLES")
print("=" * 60)

# T10: Three market UUIDs
print("\n--- T10: Three market UUIDs ---")
with timed("three markets"):
    r = c.backtest(BuyOnce(), [BTC_M1, ETH_M2, SOL_M1], initial_cash="10000",
                   after=ROLL_AFTER, before=ROLL_BEFORE)
settled = {s.market_id for s in r._settlements}
check("all 3 settled", len(settled) == 3, f"{len(settled)}: {[m[:8] for m in settled]}")
for s in r._settlements:
    tag = s.market_id[:8]
    if s.market_id in (BTC_M1, SOL_M1):
        check(f"{tag} YES profits (win=0)", Decimal(s.pnl) > 0, f"{s.pnl}")
    elif s.market_id == ETH_M2:
        check(f"{tag} YES loses (win=1)", Decimal(s.pnl) < 0, f"{s.pnl}")

# T11: Structured + rolling + UUID
print("\n--- T11: Structured + rolling + UUID ---")
with timed("struct+rolling+uuid"):
    bt = BooksTracker(buy=True)
    r = c.backtest(bt, [STRUCT_SERIES, SOL_SERIES, BTC_MB], initial_cash="10000",
                   after=MIX_AFTER, before=MIX_BEFORE)
check("no crash", True)
check("BTC settled", BTC_MB in {s.market_id for s in r._settlements})
check("SOL series settled", any(s.series_id == SOL_SERIES for s in r._settlements))
check("struct series in settlements", any(
    s.series_id == STRUCT_SERIES for s in r._settlements
) or len(bt.market_ids) >= 3,
    f"ids={len(bt.market_ids)} settl={len(r._settlements)}")

# T12: Three rolling series
print("\n--- T12: Three rolling series ---")
with timed("three series"):
    r = c.backtest(BuyOnce(), [BTC_SERIES, ETH_SERIES, SOL_SERIES], initial_cash="10000",
                   after=ROLL_AFTER, before=ROLL_BEFORE)
bs = r.by_series()
check("3 series groups", len(bs) >= 3, f"{len(bs)}: {list(bs.keys())}")
series_pnl = sum(Decimal(v['total_pnl']) for v in bs.values())
settle_pnl = sum(Decimal(s.pnl) - Decimal(s.fees) for s in r._settlements)
check("by_series pnl == settlement pnl", series_pnl == settle_pnl,
      f"{series_pnl} vs {settle_pnl}")


# ════════════════════════════════════════════════════
#  CROSS-CUTTING CONCERNS
# ════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("CROSS-CUTTING CONCERNS")
print("=" * 60)

# T13: ctx property renames + backwards compat
print("\n--- T13: Context properties ---")
with timed("prop check"):
    pc = PropChecker()
    c.backtest(pc, [BTC_M1, ETH_M1], initial_cash="10000", after=ROLL_AFTER, before=ROLL_BEFORE)
check("new names (market/book/time/books)", pc.new_ok)
check("old aliases (current_*/event_books)", pc.old_ok)
check("books contains current market", pc.books_has_self)

# T14: ctx.books tracks multiple concurrent markets
print("\n--- T14: ctx.books multi-market ---")
with timed("books tracker"):
    bt = BooksTracker()
    c.backtest(bt, [BTC_M1, ETH_M1], initial_cash="10000", after=ROLL_AFTER, before=ROLL_BEFORE)
check("saw both markets", len(bt.market_ids) == 2, f"{bt.market_ids}")
check("books had 2 entries", bt.max_books >= 2, f"max={bt.max_books}")

# T15: Cross-market ordering
print("\n--- T15: Cross-market order via market_id ---")
with timed("cross-market"):
    r = c.backtest(CrossMarketTrader(BTC_M1, ETH_M1), [BTC_M1, ETH_M1],
                   initial_cash="10000", after=ROLL_AFTER, before=ROLL_BEFORE)
eth_orders = [o for o in r._orders if o.market_id == ETH_M1]
btc_orders = [o for o in r._orders if o.market_id == BTC_M1]
check("order on ETH (target)", len(eth_orders) > 0, f"{len(eth_orders)}")
check("no order on BTC (source)", len(btc_orders) == 0, f"{len(btc_orders)}")
eth_fills = [f for o in r._orders for f in o.fills if o.market_id == ETH_M1]
check("ETH fill happened", len(eth_fills) > 0, f"{len(eth_fills)}")

# T16: by_series PnL consistency
print("\n--- T16: by_series PnL consistency ---")
with timed("by_series"):
    r = c.backtest(BuyOnce(), [BTC_M1, ETH_M2, SOL_M1], initial_cash="10000",
                   after=ROLL_AFTER, before=ROLL_BEFORE)
bs = r.by_series()
check("by_series has entries", len(bs) > 0, f"{len(bs)}")
series_pnl = sum(Decimal(v['total_pnl']) for v in bs.values())
settle_pnl = sum(Decimal(s.pnl) - Decimal(s.fees) for s in r._settlements)
check("series pnl == settlement pnl", series_pnl == settle_pnl,
      f"{series_pnl} vs {settle_pnl}")
series_trades = sum(v['total_trades'] for v in bs.values())
check("series trades == total", series_trades == r.total_trades,
      f"{series_trades} vs {r.total_trades}")

# T17: settlements_df has series_id
print("\n--- T17: settlements_df series_id ---")
df = r.settlements_df()
if not df.empty:
    check("series_id column", 'series_id' in df.columns, f"{list(df.columns)}")
    check("series_id not all null", df['series_id'].notna().any())
else:
    check("settlements_df not empty", False, "empty df")

# T18: PnL correctness per settlement
print("\n--- T18: PnL correctness ---")
for s in r._settlements:
    entry = Decimal(s.avg_entry_price)
    settle = Decimal(s.settlement_price)
    shares = Decimal(s.shares)
    expected = (settle - entry) * shares
    actual = Decimal(s.pnl)
    check(f"PnL {s.market_id[:8]}",
          actual == expected.quantize(Decimal("0.0001")),
          f"expected={expected} actual={actual}")

# T19: Cash depletion with shared capital
print("\n--- T19: Shared cash depletion ---")
class BigBuyer(Strategy):
    def on_market_start(self, ctx, market, book): self._b = False
    def on_book(self, ctx, market, book):
        if not self._b and ctx.position().side == "FLAT":
            ctx.buy_yes(size="9000"); self._b = True

with timed("cash depletion"):
    r = c.backtest(BigBuyer(), [BTC_M1, ETH_M1], initial_cash="5000",
                   after=ROLL_AFTER, before=ROLL_BEFORE)
check("cash sharing limits fills", r.cash_rejected > 0 or r.total_trades <= 1,
      f"trades={r.total_trades} rejected={r.cash_rejected}")


# ════════════════════════════════════════════════════
#  EDGE CASES
# ════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("EDGE CASES")
print("=" * 60)

# T20: Empty list
print("\n--- T20: Empty list ---")
try:
    r = c.backtest(BuyOnce(), [], initial_cash="10000")
    check("empty list no crash", True)
    check("no trades", r.total_trades == 0)
except Exception as e:
    check("empty list handled", isinstance(e, ValueError), f"{type(e).__name__}: {e}")

# T21: Duplicate market
print("\n--- T21: Duplicate market ---")
with timed("duplicate"):
    r = c.backtest(BuyOnce(), [BTC_M1, BTC_M1], initial_cash="10000",
                   after=ROLL_AFTER, before=ROLL_BEFORE)
check("no crash", True)
print(f"  Info: trades={r.total_trades} settlements={len(r._settlements)}")

# T22: Invalid UUID in list
print("\n--- T22: Invalid UUID in list ---")
try:
    c.backtest(BuyOnce(), [BTC_M1, "nonexistent-00000000-0000-0000"],
               initial_cash="10000", after=ROLL_AFTER, before=ROLL_BEFORE)
    check("error raised", False, "no error")
except Exception as e:
    check("error raised for bad ID", True, f"{type(e).__name__}")


# ════════════════════════════════════════════════════
#  SUMMARY
# ════════════════════════════════════════════════════

print(f"\n{'=' * 60}")
print(f"AUDIT COMPLETE: {PASS} passed, {FAIL} failed")
if ISSUES:
    print(f"\nFAILURES:")
    for name, detail in ISSUES:
        print(f"  - {name}: {detail[:200]}")
print(f"{'=' * 60}")

c.close()
