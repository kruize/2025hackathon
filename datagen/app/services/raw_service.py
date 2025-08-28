from fastapi import HTTPException
from typing import Dict, Any, List, Tuple, Optional
from ..db import get_db
from ..queries import SELECT_DATASET, SELECT_SAMPLES_RANGE
from ..utils.time_utils import parse_human_dt_utc, fmt_utc

def get_raw(namespace: str, workload_type: str, workload_name: str, container_name: str,
            from_str: Optional[str], to_str: Optional[str]) -> Dict[str, Any]:
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(SELECT_DATASET, (namespace, workload_type, workload_name, container_name))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Dataset not found.")
        dataset_id = row["id"]

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
            time_where += " AND ts_utc >= ?"
            params.append(start_ts)
        if end_ts is not None:
            time_where += " AND ts_utc <= ?"
            params.append(end_ts)

        sql = SELECT_SAMPLES_RANGE.format(time_where=time_where)
        cur.execute(sql, params)
        rows = cur.fetchall()
        if not rows:
            raise HTTPException(status_code=404, detail="No samples found for the requested time range.")

        metrics: Dict[str, Dict[str, Any]] = {}
        first_ts = None; last_ts = None
        for r in rows:
            ts = int(r["ts_utc"]); m = r["metric"]; v = float(r["value"])
            if first_ts is None or ts < first_ts: first_ts = ts
            if last_ts  is None or ts > last_ts:  last_ts  = ts
            metrics.setdefault(m, {"metric": m, "values": []})["values"].append([ts, v])

        time_window = {
            "start": fmt_utc(first_ts),
            "end":   fmt_utc(last_ts),
            "start_utc_secs": first_ts,
            "end_utc_secs":   last_ts,
        }

        return {
            "namespace": namespace,
            "workload_type": workload_type,
            "workload_name": workload_name,
            "container_name": container_name,
            "time_window": time_window,
            "metrics": metrics,
        }
    finally:
        conn.close()
