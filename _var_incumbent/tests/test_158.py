import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
# [CRUX-MK]
import importlib

m158 = importlib.import_module("158")
build_cadence_report = m158.build_cadence_report


def test_build_cadence_report_core_metrics():
    messages = [
        {"channel": "#ops", "user": "alice", "ts": "2026-06-08T07:30:00"},
        {"channel": "#ops", "user": "bob", "ts": "2026-06-08T08:00:00"},
        {"channel": "#ops", "user": "alice", "ts": "2026-06-08T08:15:00"},
        {"channel": "#ops", "user": "alice", "ts": "2026-06-09T19:00:00"},
        {"channel": "#eng", "user": "cara", "ts": "2026-06-08T09:00:00"},
        {"channel": "#eng", "user": "dan", "ts": "2026-06-08T09:30:00"},
        {"channel": "#eng", "user": "cara", "ts": "2026-06-08T10:00:00"},
        {"channel": "#eng", "user": "dan", "ts": "2026-06-08T10:30:00"},
        {"channel": "#random", "user": "eve", "ts": "2026-06-08T23:00:00"},
    ]

    report = build_cadence_report(messages)

    assert report["total_messages"] == 9

    assert report["messages_per_channel_per_day"] == {
        "#ops": {"2026-06-08": 3, "2026-06-09": 1},
        "#eng": {"2026-06-08": 4},
        "#random": {"2026-06-08": 1},
    }

    assert report["response_time_median_seconds"]["#ops"] == 1350.0
    assert report["response_time_median_seconds"]["#eng"] == 1800.0
    assert "#random" not in report["response_time_median_seconds"]

    assert report["off_hours_activity_pct"] == 33.33

    assert report["top_channels_activity"] == [
        {"channel": "#ops", "message_count": 4},
        {"channel": "#eng", "message_count": 4},
        {"channel": "#random", "message_count": 1},
    ]

