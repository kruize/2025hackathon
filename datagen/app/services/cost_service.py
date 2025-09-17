# app/services/cost_service.py
import traceback
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from typing import Dict, Callable, Tuple

from fastapi import HTTPException

from app.constants import DEFAULT_REQUESTS_LIMITS, COST_PER_HR_PER_VCPU
from app.db import get_db
from app.queries import DATASET_LIST, COST_COUNTS_RANGE  # same shape as your METRIC_COUNTS_RANGE
from app.services.recommendations_service import get_recommendations  # ensure import path is correct

# ------------- bucketing helpers (same as earlier) -------------
def _floor_hour(dt: datetime) -> datetime:
    return dt.replace(minute=0, second=0, microsecond=0)

def _floor_day(dt: datetime) -> datetime:
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)

def _floor_week(dt: datetime) -> datetime:
    d0 = _floor_day(dt)
    return d0 - timedelta(days=d0.weekday())  # Monday

def _floor_month(dt: datetime) -> datetime:
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

def _iso_week_label(dt: datetime) -> str:
    iso = dt.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"

_RESOLUTION: Dict[str, Tuple[int, Callable[[datetime], datetime], Callable[[datetime], str]]] = {
    "hourly":  (3600, _floor_hour,  lambda d: d.strftime("%Y-%m-%dT%H:00")),
    "daily":   (86400, _floor_day,  lambda d: d.strftime("%Y-%m-%d")),
    "weekly":  (7*86400, _floor_week, _iso_week_label),
    "monthly": (0, _floor_month, lambda d: d.strftime("%Y-%m")),  # step handled below
}

def _next_bucket_start(dt: datetime, resolution: str) -> datetime:
    if resolution == "monthly":
        y = dt.year + (1 if dt.month == 12 else 0)
        m = 1 if dt.month == 12 else dt.month + 1
        return dt.replace(year=y, month=m, day=1, hour=0, minute=0, second=0, microsecond=0)
    step, _, _ = _RESOLUTION[resolution]
    return dt + timedelta(seconds=step)

_DEFAULT_REC_FREQ_STR = "6h"

def get_cost(resolution: str = "daily"):
    if resolution not in _RESOLUTION:
        raise HTTPException(status_code=400, detail="resolution must be one of: hourly, daily, weekly, monthly")

    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(DATASET_LIST)
        datasets = cur.fetchall()
        if not datasets:
            raise HTTPException(status_code=404, detail="No datasets found.")

        # --- bucket-first aggregation ---
        # bucket_costs[bucket_label][namespace] -> total_cost
        bucket_costs = defaultdict(lambda: defaultdict(float))

        step_seconds, floor_fn, label_fn = _RESOLUTION[resolution]

        for ds in datasets:
            ds_id = ds["id"]
            namespace = ds["namespace"]

            cur.execute(COST_COUNTS_RANGE, (ds_id,))
            rows = cur.fetchall()
            if not rows:
                continue

            min_ts = min(r["min_ts"] for r in rows if r["min_ts"] is not None)
            max_ts = max(r["max_ts"] for r in rows if r["max_ts"] is not None)
            if min_ts is None or max_ts is None or max_ts <= min_ts:
                continue

            # Convert dataset min/max to ISO-ish strings for recommendations call
            from_str = datetime.fromtimestamp(min_ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
            to_str = datetime.fromtimestamp(max_ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

            # Attempt to fetch recommendations for this dataset/time-range.
            try:
                recs_resp = get_recommendations(
                    namespace=ds["namespace"],
                    workload_type=ds["workload_type"],
                    workload_name=ds["workload_name"],
                    container_name=ds["container_name"],
                    rec_freq=_DEFAULT_REC_FREQ_STR,
                    from_str=from_str,
                    to_str=to_str,
                )
                rec_map = recs_resp.get("recommendations", {}) or {}
            except Exception as e:
                # Basic info
                print("== get_recommendations failed ==")
                print("Exception type:", type(e).__name__)
                print("Exception repr:", repr(e))

                # If it's an HTTPException from FastAPI, show status_code and detail
                if isinstance(e, HTTPException):
                    try:
                        print("HTTPException.status_code:", e.status_code)
                        print("HTTPException.detail:", e.detail)
                    except Exception:
                        pass

                # Full traceback
                tb = traceback.format_exc()
                print("Traceback:")
                print(tb)

                rec_map = {}

            # If recommendations empty, fallback: charge using DEFAULT_REQUESTS_LIMITS across dataset duration
            if not rec_map:
                start = datetime.fromtimestamp(min_ts, tz=timezone.utc)
                end_inclusive = datetime.fromtimestamp(max_ts, tz=timezone.utc)
                # cost per hour from default limits
                default_cores = float(DEFAULT_REQUESTS_LIMITS["limits"]["cpu"]["amount"])
                default_cost_per_hr = default_cores * COST_PER_HR_PER_VCPU

                # iterate buckets like before and add proportional cost
                cur_start = floor_fn(start)
                # ensure cur_start is <= end: if cur_start > start, step backwards one step to catch earlier overlap
                if cur_start > start:
                    # move one step earlier for non-monthly to ensure we don't skip; for monthly handle separately
                    if resolution == "monthly":
                        # if start is on same month, floor_fn already gave month start; otherwise reduce month by 1
                        cur_start = _floor_month(start)
                    else:
                        cur_start = cur_start - timedelta(seconds=step_seconds)

                while cur_start <= end_inclusive:
                    next_start = _next_bucket_start(cur_start, resolution)
                    bucket_start = cur_start
                    bucket_end = next_start - timedelta(seconds=1)

                    ov_start = max(start, bucket_start)
                    ov_end = min(end_inclusive, bucket_end)
                    if ov_end >= ov_start:
                        overlap_hours = (ov_end - ov_start).total_seconds() / 3600.0
                        label = label_fn(cur_start)
                        bucket_costs[label][namespace] += round(overlap_hours * default_cost_per_hr, 2)

                    cur_start = next_start

                continue  # done with this dataset

            # Process recommendations map: each recommendation entry contains interval_start_utc, interval_end_utc
            # For each rec interval, compute its cost and split across buckets (same overlap math)
            print(len(rec_map.items()))
            for _end_key, rec_entry in rec_map.items():
                try:
                    rec_start_ts = int(rec_entry.get("interval_start_utc"))
                    rec_end_ts = int(rec_entry.get("interval_end_utc"))
                except Exception:
                    continue

                if rec_end_ts < rec_start_ts:
                    continue

                # duration of this rec interval in seconds
                rec_start_dt = datetime.fromtimestamp(rec_start_ts, tz=timezone.utc)
                rec_end_dt = datetime.fromtimestamp(rec_end_ts, tz=timezone.utc)

                # get cores from short_term limits if available, otherwise fallback to default
                try:
                    short_cfg = rec_entry["recommendation_terms"]["short_term"]["recommendation_engines"]["cost"]["config"]
                    cores = float(short_cfg["limits"]["cpu"]["amount"])
                except Exception as e:
                    print("exception in cores")
                    print(e)
                    cores = float(DEFAULT_REQUESTS_LIMITS["limits"]["cpu"]["amount"])

                cost_per_hr = cores * COST_PER_HR_PER_VCPU

                # iterate buckets that intersect this rec interval
                cur_start = floor_fn(rec_start_dt)
                # ensure we start from a bucket that may precede rec_start_dt to capture overlap
                if cur_start > rec_start_dt:
                    if resolution == "monthly":
                        cur_start = _floor_month(rec_start_dt)
                    else:
                        cur_start = cur_start - timedelta(seconds=step_seconds)

                while cur_start <= rec_end_dt:
                    next_start = _next_bucket_start(cur_start, resolution)
                    bucket_start = cur_start
                    bucket_end = next_start - timedelta(seconds=1)

                    ov_start = max(rec_start_dt, bucket_start)
                    ov_end = min(rec_end_dt, bucket_end)
                    if ov_end >= ov_start:
                        overlap_hours = (ov_end - ov_start).total_seconds() / 3600.0
                        label = label_fn(cur_start)
                        bucket_costs[label][namespace] += round(overlap_hours * cost_per_hr, 2)

                    cur_start = next_start

        if not bucket_costs:
            raise HTTPException(status_code=404, detail="No cost data available.")

        # --- render in desired shape: one item per DATE, with all namespaces under 'projects' ---
        def mk_value(label: str, ns: str, total_cost: float):
            return {
                "date": label,
                "source_uuid": [],
                "project": ns,
                "infrastructure": {
                    "raw":   {"value": total_cost, "units": "USD"},
                    "markup":{"value": 0, "units": "USD"},
                    "usage": {"value": 0, "units": "USD"},
                    "total": {"value": total_cost, "units": "USD"},
                },
                "supplementary": {
                    "raw":   {"value": 0, "units": "USD"},
                    "markup":{"value": 0, "units": "USD"},
                    "usage": {"value": 0, "units": "USD"},
                    "total": {"value": 0, "units": "USD"},
                },
                "cost": {
                    "raw":   {"value": total_cost, "units": "USD"},
                    "markup":{"value": 0, "units": "USD"},
                    "usage": {"value": 0, "units": "USD"},
                    "total": {"value": total_cost, "units": "USD"},
                }
            }

        data = []
        # iterate dates in order
        for label in sorted(bucket_costs.keys()):
            ns_map = bucket_costs[label]
            # for this date, build one 'projects' item per namespace
            projects = []
            for ns in sorted(ns_map.keys()):
                total_cost = round(ns_map[ns], 2)
                projects.append({
                    "project": ns,
                    "values": [mk_value(label, ns, total_cost)]
                })

            # single date entry holding all namespaces
            data.append([{
                "date": label,
                "projects": projects
            }])

        return {
            "meta": {},
            "links": {},
            "data": data
        }

    finally:
        conn.close()
