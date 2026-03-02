"""DataFrame conversion with proper type coercion.

Turns decimal-string prices into floats, epoch-ms timestamps into
``datetime64[ns, UTC]``, and sets a sensible index — so the user gets an
analysis-ready DataFrame from every ``to_dataframe()`` call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

import pandas as pd
from pydantic import BaseModel


@dataclass(frozen=True)
class _DFConfig:
    """Declares how to coerce a model's fields for DataFrame output."""
    numeric: tuple[str, ...] = ()
    timestamps: tuple[str, ...] = ()
    index: str | None = None
    exclude: tuple[str, ...] = ()


# Lazy registry — populated on first access to avoid import-time circular deps.
_REGISTRY: dict[type, _DFConfig] | None = None


def _get_registry() -> dict[type, _DFConfig]:
    global _REGISTRY
    if _REGISTRY is not None:
        return _REGISTRY

    from marketlens.types.candle import Candle
    from marketlens.types.event import Event
    from marketlens.types.market import Market
    from marketlens.types.orderbook import BookMetrics, OrderBook
    from marketlens.types.series import Series
    from marketlens.types.trade import Trade

    _REGISTRY = {
        Candle: _DFConfig(
            numeric=("open", "high", "low", "close", "vwap", "volume"),
            timestamps=("open_time", "close_time"),
            index="open_time",
        ),
        Trade: _DFConfig(
            numeric=("price", "size"),
            timestamps=("platform_timestamp", "collected_at"),
            index="platform_timestamp",
        ),
        BookMetrics: _DFConfig(
            numeric=("best_bid", "best_ask", "spread", "midpoint", "bid_depth", "ask_depth"),
            timestamps=("t",),
            index="t",
        ),
        Market: _DFConfig(
            numeric=("tick_size", "volume", "liquidity"),
            timestamps=("open_time", "close_time", "resolved_at", "platform_resolved_at", "created_at", "updated_at"),
            exclude=("outcomes",),
        ),
        Event: _DFConfig(
            timestamps=("start_date", "end_date", "created_at", "updated_at"),
        ),
        Series: _DFConfig(
            timestamps=("first_market_close", "last_market_close"),
        ),
    }
    return _REGISTRY


def models_to_dataframe(items: Sequence[BaseModel], model_cls: type | None = None) -> pd.DataFrame:
    """Convert a sequence of Pydantic models to a properly-typed DataFrame.

    - Decimal-string fields (prices, sizes, volumes) → ``float64``
    - Epoch-ms timestamp fields → ``datetime64[ns, UTC]``
    - Sets a natural time-based index when one exists
    """

    if not items:
        return pd.DataFrame()

    model_cls = model_cls or type(items[0])
    registry = _get_registry()
    config = registry.get(model_cls)

    rows = []
    for item in items:
        d = item.model_dump()
        if config:
            for k in config.exclude:
                d.pop(k, None)
        rows.append(d)

    df = pd.DataFrame(rows)

    if config is None:
        return df

    # Coerce numeric-string columns to float
    for col in config.numeric:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Coerce epoch-ms columns to datetime
    for col in config.timestamps:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], unit="ms", utc=True, errors="coerce")

    # Set index
    if config.index and config.index in df.columns:
        df = df.set_index(config.index)

    return df
