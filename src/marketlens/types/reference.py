from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ReferenceCandle(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    timestamp: int
    open: str
    high: str
    low: str
    close: str
    volume: str | None = None
