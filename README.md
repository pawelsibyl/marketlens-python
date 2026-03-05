# MarketLens Python SDK

Historical and real-time prediction market data — full L2 orderbook reconstruction, microstructure analytics, and backtesting primitives for Polymarket.

```bash
pip install marketlens
```

```python
from marketlens import MarketLens

client = MarketLens(api_key="mk_...")  # or set MARKETLENS_API_KEY env var
```

## Orderbook Walk — Series Backtesting

Replay full L2 book state across every market in a rolling series. Each tick yields `(Market, OrderBook)` — one line to go from series slug to book-level backtest.

```python
from datetime import datetime, timezone
from marketlens import MarketLens

client = MarketLens()

for market, book in client.orderbook.walk(
    "btc-up-or-down-5m", status="resolved",
    after=datetime(2026, 3, 5, 8, 40, tzinfo=timezone.utc),
    before=datetime(2026, 3, 5, 8, 45, tzinfo=timezone.utc),
):
    if (spread := book.spread_bps()) and spread < 200:
        entry = book.impact("BUY", "100")
        # ...
```

Or get everything as a DataFrame:

```python
df = client.orderbook.walk(
    "btc-up-or-down-5m", status="resolved",
    after=start, before=end,
).to_dataframe()
# Columns: midpoint, spread, spread_bps, imbalance, weighted_midpoint,
#          bid_depth, ask_depth, market_id, winning_outcome
```

## L2 Orderbook Replay

Reconstruct tick-by-tick book state from the raw snapshot + delta stream for a single market.

```python
from marketlens import OrderBookReplay

history = client.orderbook.history(market_id, after=start, before=end)

for event, book in OrderBookReplay(history, market_id=market_id):
    print(f"t={event.t}  mid={book.midpoint}  spread={book.spread_bps():.0f}bps")

# Or as a DataFrame
df = OrderBookReplay(history, market_id=market_id).to_dataframe()
```

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
| `client.series` | `list()` `get()` `markets()` `walk()` |
| `client.orderbook` | `get()` `history()` `metrics()` `walk()` |

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
    async for market, book in client.orderbook.walk("btc-up-or-down-5m", status="resolved"):
        print(book.microprice(), book.imbalance(levels=3))
```

## Examples

| Example | Description |
|---------|-------------|
| [`microstructure.py`](examples/microstructure.py) | Feature matrix from L2 replay — imbalance vs outcome signal |
| [`series_backtest.py`](examples/series_backtest.py) | Spread-timing strategy with per-trade P&L |
| [`execution_cost.py`](examples/execution_cost.py) | Live book depth, spread, impact/slippage across order sizes |

## License

MIT
