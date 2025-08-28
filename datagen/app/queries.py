CREATE_TABLES = [
"""
CREATE TABLE IF NOT EXISTS datasets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at_utc INTEGER NOT NULL,
    namespace TEXT NOT NULL,
    workload_type TEXT NOT NULL,
    workload_name TEXT NOT NULL,
    container_name TEXT NOT NULL,
    scenario TEXT NOT NULL,
    days INTEGER NOT NULL,
    interval_in_secs INTEGER NOT NULL,
    measurement_duration_secs INTEGER NOT NULL,
    UNIQUE(namespace, workload_type, workload_name, container_name)
)
""",
"""
CREATE TABLE IF NOT EXISTS samples (
    dataset_id INTEGER NOT NULL,
    ts_utc INTEGER NOT NULL,
    metric TEXT NOT NULL,
    value REAL NOT NULL,
    PRIMARY KEY (dataset_id, ts_utc, metric),
    FOREIGN KEY(dataset_id) REFERENCES datasets(id) ON DELETE CASCADE
)
"""
]

INSERT_DATASET = """
INSERT INTO datasets
(created_at_utc, namespace, workload_type, workload_name, container_name,
 scenario, days, interval_in_secs, measurement_duration_secs)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

SELECT_DATASET = """
SELECT * FROM datasets
WHERE namespace = ? AND workload_type = ? AND workload_name = ? AND container_name = ?
"""

SELECT_DATASET_ID = """
SELECT id FROM datasets
WHERE namespace = ? AND workload_type = ? AND workload_name = ? AND container_name = ?
"""

SELECT_SAMPLES_RANGE = """
SELECT ts_utc, metric, value
FROM samples
WHERE dataset_id = ?
  {time_where}
ORDER BY ts_utc ASC, metric ASC
"""

COUNT_TABLE = "SELECT COUNT(*) AS c FROM {table}"

DATASET_LIST = """
SELECT id, namespace, workload_type, workload_name, container_name
FROM datasets
ORDER BY namespace, workload_type, workload_name, container_name
"""

METRIC_COUNTS_RANGE = """
SELECT metric, COUNT(*) AS cnt, MIN(ts_utc) AS min_ts, MAX(ts_utc) AS max_ts
FROM samples
WHERE dataset_id = ?
GROUP BY metric
"""
