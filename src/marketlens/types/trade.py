from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Trade(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    market_id: str
    platform: str
    price: str | None = None
    size: str | None = None
    side: str
    platform_timestamp: int | None = None
    collected_at: int | None = None
    fee_rate_bps: str | None = None
