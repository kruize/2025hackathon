import os

DB_PATH = os.environ.get("DB_PATH", "app.db")

# Metrics
METRIC_MEM_USAGE = "container_memory_usage_bytes"
METRIC_MEM_RSS   = "container_memory_rss"
METRIC_CPU_SECS  = "container_cpu_usage_seconds_total"
METRIC_THR_SECS  = "container_cpu_cfs_throttled_seconds_total"

ALL_METRICS = [METRIC_MEM_USAGE, METRIC_MEM_RSS, METRIC_CPU_SECS, METRIC_THR_SECS]

# Defaults
DEFAULT_DAYS = 1
DEFAULT_INTERVAL = 15
DEFAULT_MEAS_WINDOW = 900
DEFAULT_AGG = "15m"
DEFAULT_REC_FREQ_SECS = 6 * 3600
MAX_REC_FREQ_SECS = 86400  # 1d
