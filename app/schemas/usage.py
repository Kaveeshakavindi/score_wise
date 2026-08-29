from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class UsageSummaryOut(BaseModel):
    tokens_used_today: int
    # Both null when no budget is configured (the default) -- "unlimited",
    # not "zero remaining".
    daily_budget: int | None
    tokens_remaining: int | None
    resets_at: datetime
