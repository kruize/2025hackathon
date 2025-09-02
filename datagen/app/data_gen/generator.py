import math, random
from datetime import datetime, timezone, timedelta
from typing import Tuple
from ..models import CreateDataRequest, Scenario
from ..constants import (
    METRIC_MEM_USAGE, METRIC_MEM_RSS, METRIC_CPU_SECS, METRIC_THR_SECS,
    CPU_USAGE_HIGH, CPU_USAGE_MEDIUM, CPU_USAGE_LOW
)
from ..utils.time_utils import round_down

def generate_series(req: CreateDataRequest, dataset_id: int, conn) -> int:
    """
    Generate per-interval samples (no aggregate table).
    """
    now_utc = int((datetime.now(timezone.utc) + timedelta(days=req.days)).timestamp())
    end_ts = round_down(now_utc, req.interval_in_secs)
    start_ts = end_ts - (2 * req.days) * 24 * 3600

    seed_key = f"{req.namespace}|{req.workload_type}|{req.workload_name}|{req.container_name}"
    random.seed(hash(seed_key) & 0xFFFFFFFF)

    cpu_seconds = 0.0
    throttle_seconds = 0.0

    if req.scenario == Scenario.idle:
        base_usage = 200 * 1024 * 1024
        base_rss   = 150 * 1024 * 1024
        MAX_IDLE_CPU_CORES_PER_SEC = 0.0007
        cpu_rate_per_sec = 0.0005
        throttle_rate_per_sec = 0.0
        usage_pattern = None
    else:
        base_usage = 600 * 1024 * 1024
        base_rss   = 450 * 1024 * 1024
        throttle_rate_per_sec = 0.003

        # Pick a usage pattern randomly
        usage_pattern = random.choice(["high", "medium", "low"])
        if usage_pattern == "high":
            cpu_min, cpu_max = CPU_USAGE_HIGH
        elif usage_pattern == "medium":
            cpu_min, cpu_max = CPU_USAGE_MEDIUM
        else:
            cpu_min, cpu_max = CPU_USAGE_LOW

    cur = conn.cursor()
    conn.execute("BEGIN")
    num_samples = 0
    step = req.interval_in_secs

    for ts in range(start_ts, end_ts + 1, step):
        phase = math.sin(ts / 600.0)
        noise = random.uniform(-0.03, 0.03)

        usage = int(round(max(0.0, base_usage * (1.0 + 0.10 * phase + noise))))
        rss   = int(round(max(0.0, base_rss   * (1.0 + 0.10 * phase + noise * 0.5))))

        if req.scenario == Scenario.idle:
            eff_rate = cpu_rate_per_sec * max(0.2, 1.0 + noise)
            eff_rate = min(eff_rate, MAX_IDLE_CPU_CORES_PER_SEC)
        else:
            # Pick CPU rate per sec randomly within the chosen pattern
            eff_rate = random.uniform(cpu_min, cpu_max)

        cpu_seconds      += eff_rate * step
        throttle_seconds += throttle_rate_per_sec * step * max(0.2, 1.0 + noise)

        rows = [
            (dataset_id, ts, METRIC_MEM_USAGE, usage),
            (dataset_id, ts, METRIC_MEM_RSS,   rss),
            (dataset_id, ts, METRIC_CPU_SECS,  cpu_seconds),
            (dataset_id, ts, METRIC_THR_SECS,  throttle_seconds),
        ]
        cur.executemany(
            "INSERT OR REPLACE INTO samples (dataset_id, ts_utc, metric, value) VALUES (?, ?, ?, ?)",
            rows
        )
        num_samples += len(rows)

    conn.commit()
    return num_samples
