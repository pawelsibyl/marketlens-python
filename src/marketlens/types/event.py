from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Event(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    platform: str
    platform_event_id: str
    title: str
    category: str | None = None
    series_id: str | None = None
    series_title: str | None = None
    series_recurrence: str | None = None
    market_count: int
    start_date: int | None = None
    end_date: int | None = None
    created_at: int | None = None
    updated_at: int | None = None
