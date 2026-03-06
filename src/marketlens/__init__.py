"""MarketLens Python SDK — prediction market data for researchers and quant traders."""

from marketlens._client import AsyncMarketLens, MarketLens
from marketlens._constants import VERSION
from marketlens.exceptions import (
    APIError,
    AuthenticationError,
    ConnectionError,
    ForbiddenError,
    InvalidParameterError,
    MarketLensError,
    NotFoundError,
    RateLimitError,
    TimeoutError,
)
from marketlens.backtest import BacktestConfig, BacktestEngine, BacktestResult, Strategy
from marketlens.helpers.walk import AsyncOrderBookWalk, OrderBookWalk
from marketlens.types import (
    BookMetrics,
    Candle,
    DeltaEvent,
    Event,
    Market,
    MarketStatus,
    OrderBook,
    Outcome,
    Platform,
    PriceLevel,
    Resolution,
    Series,
    Side,
    SnapshotEvent,
    Trade,
    TradeEvent,
)

__version__ = VERSION

__all__ = [
    # Clients
    "MarketLens",
    "AsyncMarketLens",
    # Backtest
    "Strategy",
    "BacktestEngine",
    "BacktestConfig",
    "BacktestResult",
    # Types
    "Market",
    "Outcome",
    "Event",
    "Series",
    "Trade",
    "Candle",
    "OrderBook",
    "PriceLevel",
    "BookMetrics",
    "SnapshotEvent",
    "DeltaEvent",
    "TradeEvent",
    # Enums
    "MarketStatus",
    "Side",
    "Platform",
    "Resolution",
    # Helpers
    "OrderBookWalk",
    "AsyncOrderBookWalk",
    # Exceptions
    "MarketLensError",
    "APIError",
    "AuthenticationError",
    "ForbiddenError",
    "NotFoundError",
    "InvalidParameterError",
    "RateLimitError",
    "ConnectionError",
    "TimeoutError",
    # Version
    "__version__",
]
