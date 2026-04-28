from __future__ import annotations

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

NEW_YORK_TZ = ZoneInfo("America/New_York")
REGULAR_MARKET_OPEN = time(9, 30)
REGULAR_MARKET_CLOSE = time(16, 0)


def is_regular_us_market_hours(value: datetime) -> bool:
    if value.tzinfo is None:
        aware = value.replace(tzinfo=timezone.utc)
    else:
        aware = value.astimezone(timezone.utc)
    eastern = aware.astimezone(NEW_YORK_TZ)
    current_time = eastern.time()
    return REGULAR_MARKET_OPEN <= current_time < REGULAR_MARKET_CLOSE
