import math
import re

from fastapi import HTTPException
from typing import Dict, Any, List, Tuple, Optional

from ..constants import METRIC_CPU_SECS, METRIC_THR_SECS
from ..db import get_db
from ..queries import SELECT_DATASET, SELECT_SAMPLES_RANGE
from ..utils.time_utils import parse_human_dt_utc, fmt_utc, round_down, parse_duration_to_secs

_DURATION_RE = re.compile(r"^\s*(\d+)\s*([a-zA-Z]*)\s*$")

def _parse_last_to_secs(s: Optional[str]) -> Optional[int]:
    """
    Parse 'last' strings like '1m', '1 min', '2h', '3 hours', '1d', '1 day'.
    Returns seconds, or None if invalid/empty.
    """
    if not s:
        return None
    m = _DURATION_RE.match(s.strip().lower())
    if not m:
        return None
    n = int(m.group(1))
    unit = (m.group(2) or "").strip()
    if unit in ("", "m", "min", "mins", "minute", "minutes"):
        return n * 60
    if unit in ("h", "hr", "hrs", "hour", "hours"):
        return n * 3600
    if unit in ("d", "day", "days"):
        return n * 86400
    return None

def get_raw(namespace: str, workload_type: str, workload_name: str, container_name: str,
            from_str: Optional[str], to_str: Optional[str], last: Optional[str],
            foreach: Optional[str] = None, agg_func: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch raw samples in the requested window.

    Precedence:
      1) If 'from'/'to' provided, use them.
      2) Else if 'last' is valid (e.g., '6h'), use [latest_ts - last + 1, latest_ts].
      3) Else (invalid/missing 'last'), return all data.

    Aggregation:
      - If agg_func is provided, foreach is mandatory.
      - agg_func in {min, max, avg} (case-insensitive).
      - foreach must be <= selected window (<= last, or <= (to-from+1)).
      - Counters (METRIC_CPU_SECS, METRIC_THR_SECS) are converted to rate() first.

    If no aggregation requested, returns raw points (original behavior).
    If aggregation requested, per-metric 'values' become [[bucket_end_utc, agg_value], ...]
    and an 'aggregation' section is included in the response.
    """
    conn = get_db()
    try:
        cur = conn.cursor()
        # Resolve dataset
        cur.execute(SELECT_DATASET, (namespace, workload_type, workload_name, container_name))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Dataset not found.")
        dataset_id = row["id"]

        # Time window selection
        start_ts: Optional[int] = None
        end_ts: Optional[int] = None
        window_secs_for_validation: Optional[int] = None
        last_secs_for_validation: Optional[int] = None

        if from_str or to_str:
            try:
                start_ts = parse_human_dt_utc(from_str) if from_str else None
                end_ts = parse_human_dt_utc(to_str) if to_str else None
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            if start_ts is not None and end_ts is not None and end_ts < start_ts:
                raise HTTPException(status_code=400, detail="'to' must be >= 'from'.")
            if start_ts is not None and end_ts is not None:
                window_secs_for_validation = end_ts - start_ts + 1
        else:
            last_secs = _parse_last_to_secs(last)
            if last_secs:
                cur.execute("SELECT MAX(ts_utc) AS max_ts FROM samples WHERE dataset_id = ?", (dataset_id,))
                mx = cur.fetchone()
                if not mx or mx["max_ts"] is None:
                    raise HTTPException(status_code=404, detail="No samples found.")
                latest = int(mx["max_ts"])
                start_ts = latest - last_secs + 1
                end_ts = latest
                window_secs_for_validation = last_secs
                last_secs_for_validation = last_secs
            # else: all data

        # Validate foreach/agg_func
        agg = None if not agg_func else agg_func.strip().lower()
        if agg is not None and agg not in {"min", "max", "avg"}:
            raise HTTPException(status_code=400, detail="agg_func must be one of: min, max, avg.")
        if agg is not None and not foreach:
            raise HTTPException(status_code=400, detail="foreach is required when agg_func is provided.")

        foreach_secs: Optional[int] = None
        if foreach:
            try:
                foreach_secs = parse_duration_to_secs(foreach, default_secs=None)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            if foreach_secs is None or foreach_secs <= 0:
                raise HTTPException(status_code=400, detail="Invalid 'foreach' duration.")

        if agg is not None and foreach_secs:
            if window_secs_for_validation is not None and foreach_secs > window_secs_for_validation:
                raise HTTPException(status_code=400, detail="'foreach' must be <= selected time range.")
            if last_secs_for_validation is not None and foreach_secs > last_secs_for_validation:
                raise HTTPException(status_code=400, detail="'foreach' must be <= 'last' duration.")

        # Fetch rows
        time_where = ""
        params = [dataset_id]
        if start_ts is not None:
            time_where += " AND ts_utc >= ?";
            params.append(start_ts)
        if end_ts is not None:
            time_where += " AND ts_utc <= ?";
            params.append(end_ts)
        sql = SELECT_SAMPLES_RANGE.format(time_where=time_where)
        cur.execute(sql, params)
        rows = cur.fetchall()
        if not rows:
            raise HTTPException(status_code=404, detail="No samples found for the requested time range.")

        # Build series
        series: Dict[str, List[Tuple[int, float]]] = {}
        first_ts = None;
        last_ts = None
        for r in rows:
            ts = int(r["ts_utc"]);
            m = r["metric"];
            v = float(r["value"])
            if first_ts is None or ts < first_ts: first_ts = ts
            if last_ts is None or ts > last_ts:  last_ts = ts
            series.setdefault(m, []).append((ts, v))
        for m in series: series[m].sort(key=lambda x: x[0])

        time_window = {
            "start": fmt_utc(first_ts),
            "end": fmt_utc(last_ts),
            "start_utc_secs": first_ts,
            "end_utc_secs": last_ts,
        }

        # No aggregation -> return raw points
        if agg is None:
            metrics: Dict[str, Dict[str, Any]] = {}
            for m, pts in series.items():
                metrics[m] = {"metric": m, "values": [[ts, v] for ts, v in pts]}
            return {
                "namespace": namespace,
                "workload_type": workload_type,
                "workload_name": workload_name,
                "container_name": container_name,
                "time_window": time_window,
                "metrics": metrics,
            }

        # --- Aggregation path ---
        # Prepare per-sample values: counters -> rate(), gauges -> raw
        prepared: Dict[str, List[Tuple[int, float]]] = {}
        counters = {METRIC_CPU_SECS, METRIC_THR_SECS}
        for metric, pts in series.items():
            out: List[Tuple[int, float]] = []
            if metric in counters:
                prev_ts: Optional[int] = None
                prev_val: Optional[float] = None
                for ts, val in pts:
                    if prev_ts is not None and ts > prev_ts and prev_val is not None and val >= prev_val:
                        out.append((ts, (val - prev_val) / (ts - prev_ts)))  # rate/sec anchored at current ts
                    prev_ts, prev_val = ts, val
            else:
                out = pts[:]  # gauge pass-through
            if out:
                prepared[metric] = out
        if not prepared:
            raise HTTPException(status_code=404, detail="No usable samples after preprocessing.")

        assert foreach_secs is not None

        # Anchor windows to the RAW set: walk BACKWARD from actual_last
        sel_first = min(ts for pts in prepared.values() for ts, _ in pts)
        sel_last = max(ts for pts in prepared.values() for ts, _ in pts)

        def do_agg(vals: List[float]) -> float:
            if not vals: return 0.0
            if agg == "min": return min(vals)
            if agg == "max": return max(vals)
            return sum(vals) / len(vals)

        # Build non-overlapping windows: [..., [w_start, w_end], ..., ending at sel_last]
        windows: List[Tuple[int, int]] = []
        cur_end = sel_last
        while cur_end >= sel_first:
            w_start = max(sel_first, cur_end - foreach_secs + 1)  # clamp to raw start
            windows.append((w_start, cur_end))
            cur_end = w_start - 1
        windows.reverse()  # chronological order

        # For each metric, aggregate per window
        metrics_out: Dict[str, Dict[str, Any]] = {}
        for m in sorted(prepared.keys()):
            pts = prepared[m]  # list[(ts, val)], sorted by ts
            values: List[List[float]] = []
            i = 0  # pointer into pts
            for w_start, w_end in windows:
                # collect points in [w_start, w_end]
                bucket_vals: List[float] = []
                bucket_last_ts: Optional[int] = None
                # advance i until within window (pts are sorted)
                while i < len(pts) and pts[i][0] < w_start:
                    i += 1
                j = i
                while j < len(pts) and pts[j][0] <= w_end:
                    ts, v = pts[j]
                    bucket_vals.append(v)
                    bucket_last_ts = ts  # last actual ts in this window
                    j += 1
                # don't move i past window; next window may overlap earlier indices only if clamped by sel_first,
                # but our windows are non-overlapping and move forward, so set i = j for efficiency
                i = j
                if bucket_vals:
                    values.append([bucket_last_ts, float(do_agg(bucket_vals))])
            if values:
                metrics_out[m] = {"metric": m, "values": values}

        if not metrics_out:
            raise HTTPException(status_code=404,
                                detail="No aggregated values produced for the requested 'foreach' window.")


        # --- Prometheus API style return ---
        results = []
        for metric_name, mdata in metrics_out.items() if agg else series.items():
            if agg:
                values = [[ts, str(val)] for ts, val in mdata["values"]]
            else:
                values = [[ts, str(val)] for ts, val in mdata]

            results.append({
                "metric": {
                    "__name__": metric_name,
                    "namespace": namespace,
                    workload_type: workload_name,   # e.g. "deployment": "nginx-deployment"
                    "container": container_name
                },
                "values": values
            })

        return {
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": results
            }
        }


        # return {
        #     "namespace": namespace,
        #     "workload_type": workload_type,
        #     "workload_name": workload_name,
        #     "container_name": container_name,
        #     "aggregation": {
        #         "foreach": foreach,
        #         "agg_func": agg,
        #     },
        #     "time_window": {
        #         "start": fmt_utc(sel_first),
        #         "end": fmt_utc(sel_last),
        #         "start_utc_secs": sel_first,
        #         "end_utc_secs": sel_last,
        #     },
        #     "metrics": metrics_out,
        # }
    finally:
        conn.close()
