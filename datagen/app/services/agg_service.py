from typing import Dict, Any, List, Tuple, Optional
from fastapi import HTTPException
from ..db import get_db
from ..queries import SELECT_DATASET, SELECT_SAMPLES_RANGE
from ..utils.time_utils import parse_human_dt_utc, fmt_utc, round_down, parse_duration_to_secs
from ..constants import DEFAULT_AGG
from ..constants import METRIC_CPU_SECS, METRIC_THR_SECS

def get_agg(namespace: str, workload_type: str, workload_name: str, container_name: str,
            agg_time: Optional[str], from_str: Optional[str], to_str: Optional[str]) -> Dict[str, Any]:
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(SELECT_DATASET, (namespace, workload_type, workload_name, container_name))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Dataset not found.")
        dataset_id = row["id"]

        try:
            window = parse_duration_to_secs(agg_time, default_secs=15*60)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        try:
            start_ts = parse_human_dt_utc(from_str) if from_str else None
            end_ts   = parse_human_dt_utc(to_str) if to_str else None
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        if start_ts is not None and end_ts is not None and end_ts < start_ts:
            raise HTTPException(status_code=400, detail="'to' must be >= 'from'.")

        time_where = ""
        params = [dataset_id]
        if start_ts is not None:
            time_where += " AND ts_utc >= ?"; params.append(start_ts)
        if end_ts is not None:
            time_where += " AND ts_utc <= ?"; params.append(end_ts)

        cur.execute(SELECT_SAMPLES_RANGE.format(time_where=time_where), params)
        rows = cur.fetchall()
        if not rows:
            raise HTTPException(status_code=404, detail="No samples found for the requested time range.")

        # Build per metric series
        series: Dict[str, List[Tuple[int, float]]] = {}
        for r in rows:
            series.setdefault(r["metric"], []).append((int(r["ts_utc"]), float(r["value"])))
        for m in series: series[m].sort(key=lambda x: x[0])

        # Prepare values: counters -> rate(), gauges -> raw
        prepared: Dict[str, List[Tuple[int, float]]] = {}
        counters = {METRIC_CPU_SECS, METRIC_THR_SECS}
        for metric, pts in series.items():
            out = []
            if metric in counters:
                prev_ts = prev_val = None
                for ts, val in pts:
                    if prev_ts is not None and ts > prev_ts and prev_val is not None and val >= prev_val:
                        out.append((ts, (val - prev_val) / (ts - prev_ts)))
                    prev_ts, prev_val = ts, val
            else:
                out = pts[:]
            if out: prepared[metric] = out
        if not prepared:
            raise HTTPException(status_code=404, detail="No usable samples after preprocessing.")

        base = round_down(min(ts for pts in prepared.values() for ts,_ in pts) if start_ts is None else start_ts, window)

        buckets_internal: Dict[int, Dict[str, Any]] = {}
        def add_point(metric: str, ts: int, val: float):
            w_start = ((ts - base)//window)*window + base
            w_end = w_start + window
            b = buckets_internal.setdefault(w_start, {"start": w_start, "end": w_end, "metrics": {}})
            st = b["metrics"].setdefault(metric, {"min": val, "max": val, "sum": 0.0, "count": 0})
            st["min"] = min(st["min"], val); st["max"] = max(st["max"], val)
            st["sum"] += val; st["count"] += 1

        for m, pts in prepared.items():
            for ts, v in pts: add_point(m, ts, v)

        out_buckets: Dict[str, Any] = {}
        for w_start in sorted(buckets_internal.keys()):
            b = buckets_internal[w_start]; w_end = b["end"]
            metrics_out = { m: { "min": st["min"], "max": st["max"], "avg": (st["sum"]/st["count"]) if st["count"] else 0.0 }
                            for m, st in b["metrics"].items() }
            out_buckets[fmt_utc(w_end)] = {
                "interval_start_time": fmt_utc(b["start"]),
                "interval_end_time":   fmt_utc(w_end),
                "interval_start_utc":  b["start"],
                "interval_end_utc":    w_end,
                "metrics": metrics_out
            }

        def pretty(w:int)->str:
            if w%86400==0: return f"{w//86400}d"
            if w%3600==0:  return f"{w//3600}h"
            return f"{w//60}m"

        return {
            "namespace": namespace,
            "workload_type": workload_type,
            "workload_name": workload_name,
            "container_name": container_name,
            "agg_time": pretty(window),
            "buckets": out_buckets
        }
    finally:
        conn.close()
