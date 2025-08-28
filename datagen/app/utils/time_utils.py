from datetime import datetime, timezone
import re

_IN_FORMATS = [
    "%d-%m-%YT%H:%M:%S",
    "%d-%m-%Y %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
]

_DURATION_RE = re.compile(r"^\s*(\d+)\s*([a-zA-Z]*)\s*$")

def parse_human_dt_utc(s: str) -> int:
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1]
    for fmt in _IN_FORMATS:
        try:
            dt = datetime.strptime(s, fmt)
            return int(dt.replace(tzinfo=timezone.utc).timestamp())
        except ValueError:
            continue
    raise ValueError("Invalid datetime format. Use dd-mm-yyyyTHH:MM:SS or yyyy-mm-ddTHH:MM:SS.")

def fmt_utc(ts: int) -> str:
    return datetime.utcfromtimestamp(ts).strftime("%d-%m-%YT%H:%M:%S")

def round_down(ts: int, step: int) -> int:
    return ts - (ts % step)

def parse_duration_to_secs(s: str | None, default_secs: int) -> int:
    if not s:
        return default_secs
    m = _DURATION_RE.match(s.lower())
    if not m:
        raise ValueError("Invalid duration.")
    n = int(m.group(1)); unit = m.group(2).strip()
    if unit in ("", "m", "min", "mins", "minute", "minutes"):
        return n * 60
    if unit in ("h", "hr", "hour", "hours"):
        return n * 3600
    if unit in ("d", "day", "days"):
        return n * 86400
    raise ValueError("Invalid duration unit. Use minutes (m), hours (h), or days (d).")
