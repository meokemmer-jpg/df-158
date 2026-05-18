
# K16: Concurrent-Spawn-Mutex (fcntl-based, Trinity-CONSERVATIVE 2026-05-17)
def k16_lock_or_exit(df_name: str):
    """Acquire exclusive lock or exit(3). Prevents concurrent DF runs."""
    import fcntl, os, sys
    lock_path = f"/tmp/df-trinity-{df_name}.lock"
    fd = os.open(lock_path, os.O_CREAT | os.O_WRONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except BlockingIOError:
        sys.exit(3)


# K13: External-Anchor-Mock-RFC3161 (Trinity-CONSERVATIVE 2026-05-17)
def k13_anchor(payload_hash: str) -> dict:
    """Mock RFC3161-style timestamp anchor."""
    from datetime import datetime, timezone
    return {
        "anchor_type": "rfc3161-mock",
        "iso_ts": datetime.now(timezone.utc).isoformat(),
        "payload_hash": payload_hash,
    }


# K12: HMAC-SHA256-Provenance (Trinity-CONSERVATIVE 2026-05-17)
def k12_provenance(payload: bytes, key: bytes = b"df-trinity-conservative-v1") -> dict:
    """Returns payload_hash + HMAC-SHA256 signature."""
    import hashlib, hmac
    return {
        "payload_hash": hashlib.sha256(payload).hexdigest(),
        "hmac_sha256": hmac.new(key, payload, hashlib.sha256).hexdigest(),
    }

"""OPS-Slack-Cadence-Tracker: counter-only DF-158 engine."""

import re
import os
import json
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from datetime import datetime, timezone


DF_DIR = Path(__file__).parent
LOCK_DIR = Path("/tmp/df-158.lock")
DF_ID = "158"
DECISION_KEYWORDS_REGEX = re.compile(
    r"\b(entscheid[a-z]*|empfehl(?:e|en|t|st)|sollt(?:e|en|est)|recommend[a-z]*|decid[a-z]*|advis[a-z]*|propos[a-z]*)\b",
    re.IGNORECASE,
)


@dataclass
class TrackerOutput:
    welle: str = "25"
    df: str = "DF-158"
    iso_timestamp: str = ""
    source: str = "mock"
    messages_per_day: int = 0
    channels_active: int = 0
    response_time_avg_minutes: float = 0
    after_hours_pct: float = 0
    cadence_per_channel: dict = field(default_factory=dict)


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _file_stable(path, min_age_sec=300) -> bool:
    p = Path(path)
    if not p.exists() or not p.is_file():
        return False
    try:
        return (time.time() - p.stat().st_mtime) >= min_age_sec
    except OSError:
        return False


def _remove_lock_dir() -> None:
    if not LOCK_DIR.exists():
        return
    try:
        for child in LOCK_DIR.iterdir():
            if child.is_file() or child.is_symlink():
                child.unlink()
            elif child.is_dir():
                for nested in child.iterdir():
                    if nested.is_file() or nested.is_symlink():
                        nested.unlink()
                child.rmdir()
        LOCK_DIR.rmdir()
    except OSError:
        pass


def acquire_lock_with_identity() -> bool:
    stale_after_sec = 6 * 60 * 60
    try:
        LOCK_DIR.mkdir(mode=0o700)
    except FileExistsError:
        try:
            age = time.time() - LOCK_DIR.stat().st_mtime
        except OSError:
            return False
        if age < stale_after_sec:
            return False
        _remove_lock_dir()
        try:
            LOCK_DIR.mkdir(mode=0o700)
        except OSError:
            return False
    except OSError:
        return False

    identity = {
        "df": DF_ID,
        "pid": os.getpid(),
        "created_at": iso_now(),
        "cwd": str(Path.cwd()),
    }
    try:
        (LOCK_DIR / "identity.json").write_text(
            json.dumps(identity, sort_keys=True, indent=2),
            encoding="utf-8",
        )
    except OSError:
        release_lock()
        return False
    return True


def release_lock() -> None:
    _remove_lock_dir()


def k17_pre_action_verification(anchors) -> dict:
    missing = []
    for anchor in anchors or []:
        value = str(anchor).strip()
        if value and not Path(value).exists():
            missing.append(value)

    env_tag = os.environ.get("DF_158_ENV_TAG", "mock").strip() or "mock"
    result = {
        "ok": not missing,
        "missing_anchors": missing,
        "env_tag": env_tag,
    }
    assert_no_decision_keywords(json.dumps(result, sort_keys=True))
    return result


def _is_real_api_enabled() -> bool:
    value = os.environ.get("DF_158_REAL_API_ENABLED", "false")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def scan_output_for_decision_keywords(text) -> list:
    if text is None:
        return []
    found = DECISION_KEYWORDS_REGEX.findall(str(text))
    normalized = []
    for item in found:
        word = item if isinstance(item, str) else item[0]
        low = word.lower()
        if low not in normalized:
            normalized.append(low)
    return normalized


def assert_no_decision_keywords(output) -> None:
    hits = scan_output_for_decision_keywords(output)
    if hits:
        raise ValueError("Q_0/K_0 violation: decision keyword(s) detected: " + ", ".join(hits))


def _safe_int(value, default=0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _counter_payload_from_env() -> dict:
    raw = os.environ.get("DF_158_TRACKER_INPUT_JSON", "").strip()
    if not raw:
        return {}
    assert_no_decision_keywords(raw)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def collect_tracker_output() -> TrackerOutput:
    data = _counter_payload_from_env() if _is_real_api_enabled() else {}
    cadence = data.get("cadence_per_channel", {})
    if not isinstance(cadence, dict):
        cadence = {}

    clean_cadence = {}
    for key, value in cadence.items():
        channel_key = str(key)
        assert_no_decision_keywords(channel_key)
        clean_cadence[channel_key] = _safe_int(value, 0)

    output = TrackerOutput(
        iso_timestamp=iso_now(),
        source="real" if _is_real_api_enabled() else "mock",
        messages_per_day=_safe_int(data.get("messages_per_day", 0), 0),
        channels_active=_safe_int(data.get("channels_active", 0), 0),
        response_time_avg_minutes=_safe_float(data.get("response_time_avg_minutes", 0.0), 0.0),
        after_hours_pct=_safe_float(data.get("after_hours_pct", 0.0), 0.0),
        cadence_per_channel=clean_cadence,
    )
    assert_no_decision_keywords(json.dumps(asdict(output), sort_keys=True))
    return output


def _anchors_from_env() -> list:
    raw = os.environ.get("DF_158_ANCHORS", "")
    return [part.strip() for part in raw.split(",") if part.strip()]


def main() -> int:
    if not acquire_lock_with_identity():
        return 3

    try:
        pav = k17_pre_action_verification(_anchors_from_env())
        if not pav.get("ok"):
            return 3

        tracker = collect_tracker_output()
        report = {
            "tracker": asdict(tracker),
            "k17_pre_action_verification": pav,
        }
        rendered = json.dumps(report, sort_keys=True, indent=2)
        assert_no_decision_keywords(rendered)

        date_tag = datetime.now(timezone.utc).date().isoformat()
        reports_dir = DF_DIR / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / f"df-158-{date_tag}.json"
        report_path.write_text(rendered + "\n", encoding="utf-8")
        return 0
    except (OSError, ValueError):
        return 3
    finally:
        release_lock()


if __name__ == "__main__":
    sys.exit(main())