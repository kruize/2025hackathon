from typing import Dict, Any, List, Tuple, Optional
from fastapi import HTTPException
import math
from ..db import get_db
from ..queries import SELECT_DATASET_ID, SELECT_SAMPLES_RANGE
from ..utils.time_utils import parse_human_dt_utc, round_down, fmt_utc, parse_duration_to_secs
from ..utils.stats import percentile
from ..constants import DEFAULT_REC_FREQ_SECS, MAX_REC_FREQ_SECS, METRIC_CPU_SECS, METRIC_THR_SECS, METRIC_MEM_USAGE

def get_recommendations(namespace: str, workload_type: str, workload_name: str, container_name: str,
                        rec_freq: Optional[str], from_str: Optional[str], to_str: Optional[str]) -> Dict[str, Any]:
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(SELECT_DATASET_ID, (namespace, workload_type, workload_name, container_name))
        row = cur.fetchone()
        if not row: raise HTTPException(status_code=404, detail="Dataset not found.")
        dataset_id = int(row["id"])

        try:
            freq_secs = parse_duration_to_secs(rec_freq, DEFAULT_REC_FREQ_SECS)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        if freq_secs > MAX_REC_FREQ_SECS:
            raise HTTPException(status_code=400, detail="rec_freq must be <= 1d (24h).")

        try:
            start_ts = parse_human_dt_utc(from_str) if from_str else None
            end_ts   = parse_human_dt_utc(to_str) if to_str else None
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        if start_ts is not None and end_ts is not None:
            if end_ts < start_ts:
                raise HTTPException(status_code=400, detail="'to' must be >= 'from'.")
            if (end_ts - start_ts + 1) < freq_secs:
                raise HTTPException(status_code=400, detail="('to' - 'from') must be at least rec_freq.")

        # Fetch samples
        time_where = ""
        params = [dataset_id]
        if start_ts is not None: time_where += " AND ts_utc >= ?"; params.append(start_ts)
        if end_ts is not None:   time_where += " AND ts_utc <= ?"; params.append(end_ts)
        cur.execute(SELECT_SAMPLES_RANGE.format(time_where=time_where), params)
        rows = cur.fetchall()
        if not rows: raise HTTPException(status_code=404, detail="No samples found for the requested time range.")

        # Series
        series: Dict[str, List[Tuple[int,float]]] = {}
        for r in rows:
            series.setdefault(r["metric"], []).append((int(r["ts_utc"]), float(r["value"])))
        for m in series: series[m].sort(key=lambda x:x[0])

        # Prepare: counters -> rate, gauges -> raw
        prepared: Dict[str, List[Tuple[int,float]]] = {}
        counters = {METRIC_CPU_SECS, METRIC_THR_SECS}
        for metric, pts in series.items():
            out = []
            if metric in counters:
                prev_ts = prev_val = None
                for ts,val in pts:
                    if prev_ts is not None and ts>prev_ts and prev_val is not None and val>=prev_val:
                        out.append((ts, (val-prev_val)/(ts-prev_ts)))
                    prev_ts, prev_val = ts, val
            else:
                out = pts[:]
            if out: prepared[metric]=out
        if not prepared:
            raise HTTPException(status_code=404, detail="No usable samples after preprocessing.")

        overall_min = min(ts for pts in prepared.values() for ts,_ in pts)
        overall_max = max(ts for pts in prepared.values() for ts,_ in pts)
        base = round_down(start_ts if start_ts is not None else overall_min, freq_secs)

        def values_in_range(pts: List[Tuple[int,float]], a:int, b:int)->List[float]:
            return [v for (ts,v) in pts if a <= ts <= b]

        recs: Dict[str, Any] = {}
        window_end = round_down(end_ts if end_ts is not None else overall_max, freq_secs)
        t = base + freq_secs - 1
        if t < (start_ts if start_ts is not None else overall_min):
            t = round_down((start_ts if start_ts is not None else overall_min), freq_secs) + freq_secs - 1

        SHORT = 24*3600; MED=7*24*3600; LONG=15*24*3600

        while t <= window_end:
            window_start = t - (freq_secs - 1)
            end_key = fmt_utc(t)

            def build_term(duration_secs:int)->Dict[str,Any]:
                term_start = t - (duration_secs - 1); term_end=t
                cpu_vals = values_in_range(prepared.get(METRIC_CPU_SECS, []), term_start, term_end)
                thr_vals = values_in_range(prepared.get(METRIC_THR_SECS, []), term_start, term_end)
                mem_vals = values_in_range(prepared.get(METRIC_MEM_USAGE, []), term_start, term_end)

                if not cpu_vals and not mem_vals:
                    return { "duration_in_hours": round(duration_secs/3600.0,3), "recommendation_engines": {} }

                p60_cpu = percentile(cpu_vals, 60) if cpu_vals else float("nan")
                p98_cpu = percentile(cpu_vals, 98) if cpu_vals else float("nan")
                max_thr = max(thr_vals) if thr_vals else 0.0
                max_mem_bytes = max(mem_vals) if mem_vals else float("nan")

                cost_cpu = max((0.0 if math.isnan(p60_cpu) else p60_cpu) + max_thr, 0.0)
                perf_cpu = max((0.0 if math.isnan(p98_cpu) else p98_cpu) + max_thr, 0.0)

                mib = 1024.0*1024.0
                cost_mem_mib = 0.0 if math.isnan(max_mem_bytes) else (max_mem_bytes/mib)
                perf_mem_mib = cost_mem_mib

                engines = {}
                if cpu_vals or mem_vals:
                    engines["cost"] = {"config":{"requests":{"memory":{"amount":round(cost_mem_mib,2),"format":"MiB"},
                                                             "cpu":{"amount":round(cost_cpu,3),"format":"cores"}},
                                                 "limits":  {"memory":{"amount":round(cost_mem_mib,2),"format":"MiB"},
                                                             "cpu":{"amount":round(cost_cpu,3),"format":"cores"}}}}
                    engines["performance"] = {"config":{"requests":{"memory":{"amount":round(perf_mem_mib,2),"format":"MiB"},
                                                                    "cpu":{"amount":round(perf_cpu,3),"format":"cores"}},
                                                        "limits":  {"memory":{"amount":round(perf_mem_mib,2),"format":"MiB"},
                                                                    "cpu":{"amount":round(perf_cpu,3),"format":"cores"}}}}
                return { "duration_in_hours": round(duration_secs/3600.0,3),
                         "recommendation_engines": engines }

            recs[end_key] = {
                "interval_start_time": fmt_utc(window_start),
                "interval_end_time": fmt_utc(t),
                "interval_start_utc": window_start,
                "interval_end_utc": t,
                "recommendation_terms": {
                    "short_term":  build_term(SHORT),
                    "medium_term": build_term(MED),
                    "long_term":   build_term(LONG),
                }
            }
            t += freq_secs

        def pretty(w:int)->str:
            if w%86400==0: return f"{w//86400}d"
            if w%3600==0:  return f"{w//3600}h"
            return f"{w//60}m"

        return {
            "namespace": namespace,
            "workload_type": workload_type,
            "workload_name": workload_name,
            "container_name": container_name,
            "rec_freq": pretty(freq_secs),
            "recommendations": recs
        }
    finally:
        conn.close()
