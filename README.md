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
from datetime import datetime, timezone
from marketlens import MarketLens

client = MarketLens()

for market, book in client.orderbook.walk(market_id, after=start, before=end):
    print(f"mid={book.midpoint}  spread={book.spread_bps():.0f}bps")

# Or as a DataFrame
df = client.orderbook.walk(market_id, after=start, before=end).to_dataframe()
# Columns: midpoint, spread, spread_bps, imbalance, weighted_midpoint,
#          bid_depth, ask_depth, market_id, winning_outcome
```

## Series Backtesting

Walk every market in a rolling series chronologically — same `orderbook.walk()` interface, just pass a series slug instead of a market ID.

```python
for market, book in client.orderbook.walk(
    "btc-up-or-down-5m", status="resolved",
    after=datetime(2026, 3, 5, 8, 40, tzinfo=timezone.utc),
    before=datetime(2026, 3, 5, 8, 45, tzinfo=timezone.utc),
):
    if (spread := book.spread_bps()) and spread < 200:
        entry = book.impact("BUY", "100")
        # ...
```

## Browse Series Events

Non-rolling series (e.g. weekly strike groups) are browsed by event:

```python
for event in client.series.events("bitcoin-hit-price-weekly"):
    markets = client.events.markets(event.id).to_list()
    print(f"{event.title} — {len(markets)} strikes")
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
| `client.series` | `list()` `get()` `markets()` `walk()` `events()` |
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
    async for market, book in await client.orderbook.walk(market_id, after=start, before=end):
        print(book.microprice(), book.imbalance(levels=3))
```

## Examples

| Example | Description |
|---------|-------------|
| [`single_market_replay.py`](examples/single_market_replay.py) | Replay a single market's order book tick by tick |
| [`microstructure.py`](examples/microstructure.py) | Feature matrix from L2 replay — imbalance vs outcome signal |
| [`series_backtest.py`](examples/series_backtest.py) | Spread-timing strategy with per-trade P&L across a rolling series |
| [`event_strikes.py`](examples/event_strikes.py) | Browse strike-level markets in a non-rolling series |
| [`execution_cost.py`](examples/execution_cost.py) | Live book depth, spread, impact/slippage across order sizes |

## License

MIT
