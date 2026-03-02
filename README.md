# MarketLens Python SDK

Python client for the [MarketLens](https://marketlens.com) prediction market data API. Covers all data query endpoints with sync/async clients, auto-pagination, and orderbook reconstruction helpers.

## Install

```bash
pip install marketlens
```

## Quick Start

```python
from marketlens import MarketLens

client = MarketLens(api_key="mk_...")  # or set MARKETLENS_API_KEY env var

# List markets
for market in client.markets.list(status="active", limit=10):
    print(market.question, market.volume)

# Get orderbook
book = client.orderbook.get(market_id)
print(book.best_bid, book.best_ask, book.spread)

# Price impact
avg_price = book.impact("BUY", "500.00")

# Candles as DataFrame
df = client.markets.candles(market_id, resolution="1h").to_dataframe()
```

## Examples

Backtesting-oriented examples against the real `btc-up-or-down-5m` series (770+ resolved markets):

| Example | Question it answers |
|---------|---------------------|
| [`microstructure.py`](examples/microstructure.py) | What does the book look like tick-by-tick? Does imbalance predict direction? |
| [`execution_cost.py`](examples/execution_cost.py) | What does it cost to trade these markets? (spread/slippage distributions) |
| [`series_backtest.py`](examples/series_backtest.py) | Does prior market momentum predict the next market's direction? |

## Async

```python
from marketlens import AsyncMarketLens

async with AsyncMarketLens() as client:
    market = await client.markets.get(market_id)
    async for trade in client.markets.trades(market_id, after=start, before=end):
        print(trade.price, trade.size)
```

## Resources

| Namespace | Methods |
|-----------|---------|
| `client.markets` | `.list()`, `.get()`, `.trades()`, `.candles()` |
| `client.events` | `.list()`, `.get()`, `.markets()` |
| `client.series` | `.list()`, `.get()`, `.markets()`, `.walk()` |
| `client.orderbook` | `.get()`, `.history()`, `.metrics()` |

All list methods return auto-paginating iterators. Call `.to_list()` to collect or `.to_dataframe()` for pandas.

## Orderbook Replay

Reconstruct full book state from the raw event stream:

```python
from marketlens import MarketLens, OrderBookReplay

client = MarketLens()
history = client.orderbook.history(market_id, after=start, before=end, include_trades=True)

for event, book in OrderBookReplay(history, market_id=market_id):
    print(f"t={event.t}  spread={book.spread}  mid={book.midpoint}")
```

## OrderBook Helpers

```python
book = client.orderbook.get(market_id)

# Microprice (size-weighted mid from best levels)
book.microprice()                   # alias for weighted_midpoint(1)

# Spread in basis points
book.spread_bps()                   # spread / midpoint * 10_000

# Top-of-book imbalance (better short-term predictor than full-book)
book.imbalance(levels=3)            # top-3 levels only
book.imbalance()                    # full book (default)

# Volume-weighted avg execution price for a $500 market buy
book.impact("BUY", "500.00")

# Liquidity within 5 cents of midpoint
bid_depth, ask_depth = book.depth_within("0.05")

# Slippage from mid for a $1000 order
book.slippage("BUY", "1000.00")
```

## Timestamps

All timestamp parameters accept both `int` (ms epoch) and `datetime`:

```python
from datetime import datetime, timezone

client.markets.trades(market_id, after=datetime(2025, 1, 1, tzinfo=timezone.utc))
client.markets.trades(market_id, after=1735689600000)  # same
```

## Exceptions

```python
from marketlens import NotFoundError, RateLimitError

try:
    client.markets.get("nonexistent")
except NotFoundError as e:
    print(e.code, e.message)
except RateLimitError as e:
    print(f"Retry after {e.retry_after}s")
```

## License

MIT
