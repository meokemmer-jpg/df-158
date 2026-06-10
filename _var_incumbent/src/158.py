from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from statistics import median
from typing import Any, Dict, Iterable, List, Optional


def _parse_ts(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        raise TypeError("timestamp must be a datetime or ISO-8601 string")
    value = value.replace("Z", "+00:00")
    return datetime.fromisoformat(value)


def _is_off_hours(ts: datetime, workday_start: int, workday_end: int) -> bool:
    return ts.hour < workday_start or ts.hour >= workday_end


def build_cadence_report(
    messages: Iterable[Dict[str, Any]],
    *,
    workday_start: int = 8,
    workday_end: int = 18,
) -> Dict[str, Any]:
    """
    Build Slack communication cadence metrics from message-like records.

    Each message must provide:
    - channel: str
    - user: str
    - ts: datetime or ISO-8601 string

    Response-time median is computed per channel using the elapsed seconds
    between consecutive messages from different users.
    """
    normalized: List[Dict[str, Any]] = []

    for raw in messages:
        channel = raw["channel"]
        user = raw["user"]
        ts = _parse_ts(raw["ts"])
        normalized.append({"channel": channel, "user": user, "ts": ts})

    normalized.sort(key=lambda item: item["ts"])

    messages_per_channel_per_day: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    response_times_by_channel: Dict[str, List[float]] = defaultdict(list)
    channel_totals: Counter[str] = Counter()
    off_hours_count = 0

    previous_by_channel: Dict[str, Dict[str, Any]] = {}

    for msg in normalized:
        channel = msg["channel"]
        user = msg["user"]
        ts = msg["ts"]
        day = ts.date().isoformat()

        messages_per_channel_per_day[channel][day] += 1
        channel_totals[channel] += 1

        if _is_off_hours(ts, workday_start, workday_end):
            off_hours_count += 1

        previous = previous_by_channel.get(channel)
        if previous is not None and previous["user"] != user:
            delta = (ts - previous["ts"]).total_seconds()
            if delta >= 0:
                response_times_by_channel[channel].append(delta)

        previous_by_channel[channel] = msg

    response_time_median = {
        channel: median(values) for channel, values in response_times_by_channel.items() if values
    }

    total_messages = len(normalized)
    off_hours_activity_pct = 0.0
    if total_messages:
        off_hours_activity_pct = round((off_hours_count / total_messages) * 100, 2)

    top_channels_activity = [
        {"channel": channel, "message_count": count}
        for channel, count in channel_totals.most_common()
    ]

    return {
        "messages_per_channel_per_day": {
            channel: dict(days) for channel, days in messages_per_channel_per_day.items()
        },
        "response_time_median_seconds": response_time_median,
        "off_hours_activity_pct": off_hours_activity_pct,
        "top_channels_activity": top_channels_activity,
        "total_messages": total_messages,
    }
# [CRUX-MK]
