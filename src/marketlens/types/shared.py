from __future__ import annotations

from enum import Enum
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict


class MarketStatus(str, Enum):
    ACTIVE = "active"
    CLOSED = "closed"
    RESOLVED = "resolved"
    PENDING = "pending"


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class Platform(str, Enum):
    POLYMARKET = "polymarket"
    KALSHI = "kalshi"


class Resolution(str, Enum):
    ONE_SECOND = "1s"
    FIVE_SECONDS = "5s"
    TEN_SECONDS = "10s"
    THIRTY_SECONDS = "30s"
    ONE_MINUTE = "1m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    ONE_HOUR = "1h"
    FOUR_HOURS = "4h"
    ONE_DAY = "1d"


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    model_config = ConfigDict(frozen=True)

    data: list[T]
    cursor: str | None = None
    has_more: bool = False
