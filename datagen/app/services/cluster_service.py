from typing import Dict, Any
from ..db import get_db
from ..queries import DATASET_LIST, METRIC_COUNTS_RANGE
from ..utils.time_utils import fmt_utc

def get_cluster_inventory() -> Dict[str, Any]:
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(DATASET_LIST)
        ds_rows = cur.fetchall()
        if not ds_rows:
            return {"cluster": {"namespaces": {}}}

        metrics_info = {}
        for r in ds_rows:
            ds_id = int(r["id"])
            cur.execute(METRIC_COUNTS_RANGE, (ds_id,))
            rows = cur.fetchall()
            counts = {}
            min_ts = None; max_ts = None
            for mrow in rows:
                counts[mrow["metric"]] = int(mrow["cnt"])
                mmin = int(mrow["min_ts"]); mmax = int(mrow["max_ts"])
                min_ts = mmin if min_ts is None or mmin < min_ts else min_ts
                max_ts = mmax if max_ts is None or mmax > max_ts else max_ts
            metrics_info[ds_id] = {
                "counts": counts,
                "unique": len(counts),
                "start_ts": min_ts,
                "end_ts": max_ts
            }

        out = {"cluster": {"namespaces": {}}}
        ns_map = out["cluster"]["namespaces"]

        for r in ds_rows:
            ds_id = int(r["id"])
            namespace = r["namespace"]; wtype = r["workload_type"]
            wname = r["workload_name"];  cname = r["container_name"]

            ns_entry = ns_map.setdefault(namespace, {"workload_types": {}})
            wt_entry = ns_entry["workload_types"].setdefault(wtype, {})
            wl_entry = wt_entry.setdefault(wname, {"containers": {}})
            containers = wl_entry["containers"]

            info = metrics_info[ds_id]
            start_hr = fmt_utc(info["start_ts"]) if info["start_ts"] is not None else None
            end_hr   = fmt_utc(info["end_ts"])   if info["end_ts"]   is not None else None
            containers[cname] = {
                "unique_metrics": info["unique"],
                "start_time": start_hr,
                "end_time": end_hr,
                "metrics": {m: {"count": c} for m, c in info["counts"].items()}
            }
        return out
    finally:
        conn.close()
