# MarketLens Python SDK

Historical and real-time prediction market data — full L2 orderbook reconstruction, microstructure analytics, and backtesting primitives for Polymarket.

```bash
pip install marketlens
```

```python
from marketlens import MarketLens

client = MarketLens(api_key="mk_...")  # or set MARKETLENS_API_KEY env var
```

## Order Book Replay

Replay full L2 book state for any market. Each tick yields `(Market, OrderBook)` — one line to go from market ID to book-level analysis.

```python
for market, book in client.orderbook.walk(market_id, after=start, before=end):
    print(f"mid={book.midpoint}  spread={book.spread_bps():.0f}bps")

# Or as a DataFrame
df = client.orderbook.walk(market_id, after=start, before=end).to_dataframe()
```

## Rolling Series

Walk every market in a rolling series chronologically — same `orderbook.walk()` interface, just pass a series slug instead of a market ID.

```python
for market, book in client.orderbook.walk("btc-up-or-down-5m", status="resolved"):
    if (spread := book.spread_bps()) and spread < 200:
        entry = book.impact("BUY", "100")
```

## Structured Products

Walk a structured product series (multi-strikes, neg-risk, barrier). All sibling strike markets are replayed in parallel — `walk.books` always holds the latest book for every strike, and `walk.surface()` fits the implied probability distribution at every tick.

```python
walk = client.orderbook.walk("btc-multi-strikes-weekly")
for market, book in walk:
    surface = walk.surface()
    if not surface:
        continue
    strikes = surface.survival_strikes()
    curve = "  ".join(f"${s.strike:,.0f}={s.fitted_prob:.3f}" for s in strikes)
    print(f"[{walk.event.title}] mean=${float(surface.implied_mean):,.0f}  {curve}")
```

Walk properties available during iteration:

| Property | Description |
|----------|-------------|
| `walk.books` | `{market_id: OrderBook}` — latest book for every sibling strike |
| `walk.markets` | `{market_id: Market}` — all strike markets in the current event |
| `walk.event` | Current `Event` (transitions automatically between events) |
| `walk.series` | Resolved `Series` |
| `walk.surface()` | `Surface` fitted from current book midpoints (same format as API) |

## Backtesting

Define a strategy by subclassing `Strategy` and implementing event hooks. Run it against any market, rolling series, or structured product — the engine replays L2 book data tick-by-tick with realistic execution simulation.

```python
from marketlens.backtest import Strategy

class BuyOnTightSpread(Strategy):
    def on_book(self, ctx, market, book):
        if ctx.position().side == "FLAT" and book.spread_bps() and book.spread_bps() < 200:
            ctx.buy_yes(size="100")

result = client.backtest(BuyOnTightSpread(), "btc-up-or-down-5m",
                         initial_cash="10000.0000",
                         after="2026-03-05T10:00Z", before="2026-03-05T10:05Z")
result.trades_df()       # per-fill DataFrame
result.settlements_df()  # per-market settlement P&L
result.equity_df()       # equity curve over time
```

### Strategy hooks

| Hook | Called when |
|------|------------|
| `on_book(ctx, market, book)` | Every book state change (snapshot or delta) |
| `on_trade(ctx, market, book, trade)` | Every historical trade |
| `on_fill(ctx, market, fill)` | Your order is filled |
| `on_market_start(ctx, market, book)` | A new market begins in the walk |
| `on_market_end(ctx, market)` | A market's data is exhausted, before settlement |
| `on_event_start(ctx, event, markets)` | A new event begins (structured products) |
| `on_event_end(ctx, event)` | All markets in an event are exhausted |

For structured product backtests, `ctx.event_books` gives the latest book for every sibling strike — the same cross-strike view as `walk.books`.

### Execution realism

| Parameter | Default | Description |
|-----------|---------|-------------|
| `initial_cash` | *required* | Starting capital (e.g. `"10000.0000"`) — buy orders exceeding cash are cancelled |
| `latency_ms` | `50` | Order-to-fill delay — orders fill against the book state N ms after submission |
| `limit_fill_rate` | `0.1` | Fraction of historical trade size that fills your limit order (queue position) |
| `slippage_bps` | `0` | Extra price penalty on market order fills (on top of L2 book walk) |
| `fees` | `"polymarket"` | Fee model — auto-detects per category (crypto vs sports). Set to `None` for zero fees |
| `max_fill_fraction` | `1.0` | Max fraction of each book level consumed per order |
| `include_trades` | `True` | Fetch trade data (required for limit order fills and `on_trade`) |

For full control, use `BacktestEngine` with `BacktestConfig` directly.

## Implied Probability Surfaces

Implied distributions extracted from multi-strike prediction markets — survival curves, density functions, and barrier probabilities, fitted via isotonic regression. Updated every 5 minutes via the API, or recomputed at every tick via `walk.surface()`.

```python
for surface in client.signals.surfaces(underlying="BTC"):
    if surface.surface_type == "survival":
        for s in surface.survival_strikes():
            print(f"  K={s.strike:>10,.0f}  P(above)={s.fitted_prob:.3f}")
    elif surface.surface_type == "density":
        for b in surface.density_buckets():
            print(f"  ${b.lower:,.0f}-${b.upper:,.0f}  p={b.normalized_prob:.3f}")
    elif surface.surface_type == "barrier":
        for b in surface.barrier_strikes():
            print(f"  {b.direction} ${b.strike:,.0f}  P={b.fitted_prob:.3f}")
```

| Type | Source | Fitting | Stats |
|------|--------|---------|-------|
| `survival` | Multi-strike "above $X" markets | PAVA monotone decreasing | `implied_mean`, `implied_cv`, `implied_skew` |
| `density` | Neg-risk range + tail markets | Normalized probabilities | `implied_mean`, `implied_cv`, `implied_skew` |
| `barrier` | Hit-price reach/dip markets | PAVA per direction | `implied_peak`, `implied_peak_cv`, `implied_trough`, `implied_trough_cv` |

## OrderBook Analytics

Every `OrderBook` — live snapshot or replayed — carries the same analytical methods:

```python
book = client.orderbook.get(market_id)

book.microprice()              # size-weighted mid from best level
book.weighted_midpoint(n=3)    # n-level weighted mid
book.spread_bps()              # spread in basis points
book.imbalance()               # full-book bid/ask imbalance [-1, 1]
book.imbalance(levels=3)       # top-of-book imbalance
book.impact("BUY", "1000")     # VWAP execution price for $1k market buy
book.slippage("BUY", "1000")   # slippage from mid for $1k order
book.depth_within("0.02")      # (bid_depth, ask_depth) within 2c of mid
```

## Resources

| Namespace | Methods |
|-----------|---------|
| `client.markets` | `list()` `get()` `trades()` `candles()` |
| `client.events` | `list()` `get()` `markets()` |
| `client.series` | `list()` `get()` `markets()` `walk()` `events()` |
| `client.orderbook` | `get()` `history()` `metrics()` `walk()` |
| `client.signals` | `surfaces()` `surface()` `history()` |

All list methods return auto-paginating iterators with `.to_list()` and `.to_dataframe()`.

```python
df = client.markets.candles(market_id, resolution="1h").to_dataframe()
trades = client.markets.trades(market_id, after=start, before=end).to_list()
top = client.markets.list(status="active", sort="-liquidity", limit=5).first_page()
```

## Async

Every resource, iterator, and replay helper has an async counterpart.

```python
from marketlens import AsyncMarketLens

async with AsyncMarketLens() as client:
    async for market, book in await client.orderbook.walk(market_id, after=start, before=end):
        print(book.microprice(), book.imbalance(levels=3))
```

## Examples

| Example | Description |
|---------|-------------|
| [`single_market_replay.py`](examples/single_market_replay.py) | Replay one market's L2 book and summarize via DataFrame |
| [`execution_cost.py`](examples/execution_cost.py) | Live book depth, spread, impact and slippage across order sizes |
| [`microstructure.py`](examples/microstructure.py) | Rolling series feature matrix — does imbalance predict outcome? |
| [`implied_surfaces.py`](examples/implied_surfaces.py) | Implied probability surfaces — survival, density, and barrier |
| [`event_strikes.py`](examples/event_strikes.py) | Structured product walk — parallel books with live surface fitting |
| [`backtest_basic.py`](examples/backtest_basic.py) | Minimal backtest — buy on tight spread, settle at resolution |
| [`series_backtest.py`](examples/series_backtest.py) | Rolling series backtest with spread-timing strategy |
| [`backtest_imbalance.py`](examples/backtest_imbalance.py) | Imbalance signal with early exit before settlement |
| [`backtest_limit_orders.py`](examples/backtest_limit_orders.py) | Market-making with limit orders and on_fill exit |
| [`backtest_surface.py`](examples/backtest_surface.py) | Surface mispricing — PAVA regression identifies underpriced strikes |

## License

MIT
