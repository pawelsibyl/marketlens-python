# MarketLens Python SDK

Historical and real-time prediction market data — full L2 orderbook reconstruction, microstructure analytics, and backtesting primitives for Polymarket.

```bash
pip install marketlens
```

```python
from marketlens import MarketLens

client = MarketLens(api_key="mk_...")  # or set MARKETLENS_API_KEY env var
```

## L2 Orderbook Replay

Reconstruct tick-by-tick book state from the raw snapshot + delta stream. Every event yields a full `OrderBook` with computed spread, midpoint, depth, and imbalance — ready for microstructure research.

```python
from marketlens import MarketLens, OrderBookReplay

history = client.orderbook.history(market_id, after=start, before=end, include_trades=True)
replay = OrderBookReplay(history, market_id=market_id)

# Iterate event-by-event with full book state
for event, book in replay:
    print(f"t={event.t}  mid={book.midpoint}  spread={book.spread_bps():.0f}bps  imb={book.imbalance():.3f}")

# Or get everything as a DataFrame in one call
df = replay.to_dataframe()
# Columns: midpoint, spread, spread_bps, imbalance, weighted_midpoint,
#          bid_depth, ask_depth, bid_levels, ask_levels,
#          trade_price, trade_size, trade_side (on trade rows)
```

## OrderBook Analytics

Every `OrderBook` object — whether from a live snapshot or replayed from history — carries the same set of analytical methods:

```python
book = client.orderbook.get(market_id)

book.microprice()              # size-weighted mid from best level
book.weighted_midpoint(n=3)    # n-level weighted mid
book.spread_bps()              # spread in basis points
book.imbalance()               # full-book bid/ask imbalance [-1, 1]
book.imbalance(levels=3)       # top-of-book imbalance (better short-term signal)
book.impact("BUY", "1000")     # VWAP execution price for $1k market buy
book.slippage("BUY", "1000")   # slippage from mid for $1k order
book.depth_within("0.02")      # (bid_depth, ask_depth) within 2c of mid
```

## Series Walk — Backtesting Primitive

Walk through every market in a rolling series chronologically. Each `MarketSlot` has lazy loaders for candles, trades, orderbook, and full history — you only fetch what you use.

```python
from datetime import datetime, timezone

for slot in client.series.walk("btc-up-or-down-5m", status="resolved",
                                after=datetime(2026, 3, 2, 12, 0, tzinfo=timezone.utc),
                                before=datetime(2026, 3, 2, 14, 0, tzinfo=timezone.utc)):
    candles = slot.candles("1m").to_dataframe()     # OHLCV DataFrame
    book = slot.orderbook()                          # book at close_time
    replay_df = OrderBookReplay(                     # full L2 replay
        slot.history(include_trades=True), market_id=slot.market.id,
    ).to_dataframe()

    print(slot.market.question, slot.market.winning_outcome)
    print(f"  overlap={slot.overlap_with_prev}ms  gap={slot.gap_from_prev}ms")
```

## Resources

| Namespace | Methods |
|-----------|---------|
| `client.markets` | `list()` `get()` `trades()` `candles()` |
| `client.events` | `list()` `get()` `markets()` |
| `client.series` | `list()` `get()` `markets()` `walk()` |
| `client.orderbook` | `get()` `history()` `metrics()` |

All list methods return auto-paginating iterators. Chain `.to_list()` to collect or `.to_dataframe()` for a typed pandas DataFrame (decimal strings → `float64`, epoch ms → `datetime64[ns, UTC]`).

```python
# Candles as DataFrame
df = client.markets.candles(market_id, resolution="1h").to_dataframe()

# Trades with time filter
trades = client.markets.trades(market_id, after=start, before=end).to_list()

# Markets sorted by liquidity
top = client.markets.list(status="active", sort="-liquidity", limit=5).first_page()
```

## Async

Full async support — every resource, iterator, and replay helper has an async counterpart.

```python
from marketlens import AsyncMarketLens, AsyncOrderBookReplay

async with AsyncMarketLens() as client:
    async for slot in client.series.walk("btc-up-or-down-5m", status="resolved"):
        book = await slot.orderbook()
        print(book.microprice(), book.imbalance(levels=3))
```

## Examples

| Example | What it does |
|---------|-------------|
| [`microstructure.py`](examples/microstructure.py) | Replays one market's full L2 book — midpoint drift, microprice, imbalance, spread, trade flow |
| [`execution_cost.py`](examples/execution_cost.py) | Live book analytics — depth, spread, impact/slippage table across order sizes |
| [`series_backtest.py`](examples/series_backtest.py) | Momentum backtest over a rolling series with per-trade P&L |

## License

MIT
