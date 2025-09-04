from datetime import datetime
from collections import defaultdict

from fastapi import HTTPException

from app.constants import DEFAULT_REQUESTS_LIMITS, COST_PER_HR_PER_VCPU
from app.db import get_db
from app.queries import DATASET_LIST, COST_COUNTS_RANGE


def get_cost():
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(DATASET_LIST)
        datasets = cur.fetchall()
        if not datasets:
            raise HTTPException(status_code=404, detail="No datasets found.")

        # namespace -> {month -> {"total_cost": float}}
        namespace_map = defaultdict(lambda: defaultdict(float))

        for ds in datasets:
            ds_id = ds["id"]
            namespace = ds["namespace"]

            # Get min/max ts for this dataset (container)
            cur.execute(COST_COUNTS_RANGE, (ds_id,))
            rows = cur.fetchall()
            if not rows:
                continue
            min_ts = min(r["min_ts"] for r in rows if r["min_ts"])
            max_ts = max(r["max_ts"] for r in rows if r["max_ts"])
            if not min_ts or not max_ts:
                continue

            duration_hours = (max_ts - min_ts) / 3600.0

            # Cost per container per hour
            cost_per_hr = DEFAULT_REQUESTS_LIMITS["limits"]["cpu"]["amount"] * COST_PER_HR_PER_VCPU
            total_cost = round(duration_hours * cost_per_hr, 2)

            # Bucket by month
            month_str = datetime.utcfromtimestamp(min_ts).strftime("%Y-%m")
            namespace_map[namespace][month_str] += total_cost

        # Build response
        data = []
        for namespace, month_map in namespace_map.items():
            for month_str, total_cost in month_map.items():
                values = [{
                    "date": month_str,
                    "source_uuid": [],  # no per-container, just aggregated
                    "project": namespace,
                    "infrastructure": {
                        "raw": {"value": total_cost, "units": "USD"},
                        "markup": {"value": 0, "units": "USD"},
                        "usage": {"value": 0, "units": "USD"},
                        "total": {"value": total_cost, "units": "USD"},
                    },
                    "supplementary": {
                        "raw": {"value": 0, "units": "USD"},
                        "markup": {"value": 0, "units": "USD"},
                        "usage": {"value": 0, "units": "USD"},
                        "total": {"value": 0, "units": "USD"},
                    },
                    "cost": {
                        "raw": {"value": total_cost, "units": "USD"},
                        "markup": {"value": 0, "units": "USD"},
                        "usage": {"value": 0, "units": "USD"},
                        "total": {"value": total_cost, "units": "USD"},
                    }
                }]

                data.append([{
                    "date": month_str,
                    "projects": [{
                        "project": namespace,
                        "values": values
                    }]
                }])

        return {
            "meta": {},
            "links": {},
            "data": data
        }

    finally:
        conn.close()