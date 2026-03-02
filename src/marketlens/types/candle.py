from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Candle(BaseModel):
    model_config = ConfigDict(frozen=True)

    open_time: int | None = None
    close_time: int | None = None
    open: str | None = None
    high: str | None = None
    low: str | None = None
    close: str | None = None
    vwap: str | None = None
    volume: str | None = None
    trade_count: int
