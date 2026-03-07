from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Series(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    platform: str
    platform_series_id: str
    title: str
    recurrence: str | None = None
    category: str | None = None
    is_rolling: bool
    structured_type: str | None = None
    market_count: int
    first_market_close: int | None = None
    last_market_close: int | None = None
