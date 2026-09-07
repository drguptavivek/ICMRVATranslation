from datetime import timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def format_datetime_for_display(value, timezone_name="Asia/Kolkata"):
    if value is None:
        return ""

    # SQLite may return a naive datetime even when the column is timezone-aware.
    # Timestamps in this application are always written in UTC.
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    try:
        display_timezone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        display_timezone = (
            timezone(timedelta(hours=5, minutes=30), "IST")
            if timezone_name == "Asia/Kolkata"
            else timezone.utc
        )

    return value.astimezone(display_timezone).strftime("%d %b %Y, %I:%M %p %Z")
