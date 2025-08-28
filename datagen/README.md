# Metrics Demo API (FastAPI + SQLite)

A modular FastAPI service that generates dummy container metrics, stores them in SQLite, and serves:
- Raw time series
- Aggregations (fixed windows; counters are rate()-ed)
- Cluster inventory
- Recommendations (cost & performance) over short/medium/long terms

## Project Layout

```
app/
  main.py                   # App factory & router wiring
  db.py                     # DB connection & init
  models.py                 # Pydantic models & enums
  constants.py              # Metric names, defaults, env
  queries.py                # SQL strings

  utils/
    time_utils.py           # parse/format times, durations, rounding
    stats.py                # percentile()

  data_gen/
    generator.py            # sample data generator

  services/
    datasets_service.py         # /data/create logic
    raw_service.py              # /data/get/raw logic
    agg_service.py              # /data/get/agg logic (pure Python windowing)
    cluster_service.py          # /data/cluster logic
    recommendations_service.py  # /data/get/recommendations logic

  routers/
    datasets.py             # /data/create
    metrics.py              # /data/get/raw, /data/get/agg
    cluster.py              # /data/cluster
    recommendations.py      # /data/get/recommendations
```

## Endpoints

- `POST /data/create` — create dataset & generate samples (dummy)
- `GET  /data/get/raw` — raw samples (with `time_window`)
- `GET  /data/get/agg` — aggregated buckets (keyed by bucket **end** timestamp)
- `GET  /data/cluster` — namespace → workload_type → workload → containers inventory
- `GET  /data/get/recommendations` — cost & performance recommendations
- `GET  /healthz` — basic health

Common query params:
- `from`, `to`: human-readable UTC (`dd-mm-yyyyTHH:MM:SS` or `yyyy-mm-ddTHH:MM:SS`)
- `/data/get/agg`: `agg_time` (e.g., `15m`, `30m`, `1h`, `1d`)
- `/data/get/recommendations`: `rec_freq` (default `6h`, must be `<= 1d`)

## Local Run (no Docker)

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
# Open http://127.0.0.1:8000/docs
```

Environment variables:
- `DB_PATH` (default: `app.db` locally; image default: `/data/app.db`)

## Docker

### Build

```bash
docker build -t metrics-demo-api:latest .
```

### Run

```bash
mkdir -p ./data

docker run --rm -it   -p 8000:8000   -e DB_PATH=/data/app.db   -v "$(pwd)/data":/data   --name metrics-demo   metrics-demo-api:latest
```

OpenAPI docs: http://localhost:8000/docs

## Implementation Notes

- Aggregation is done in **pure Python**:
  - Counters (`container_cpu_usage_seconds_total`, `container_cpu_cfs_throttled_seconds_total`) → **rate()** via deltas anchored at the later sample.
  - Gauges (memory) → raw values.
- Idle scenario caps CPU to **< 1 millicore** and sets throttling to **0**.
- Recommendations:
  - **CPU (cores)**:
    - **cost** = P60(cpu_rate) + max(throttle_rate)
    - **performance** = P98(cpu_rate) + max(throttle_rate)
  - **Memory (MiB)**: P100 of `container_memory_usage_bytes` for both cost & performance
  - Terms:
    - **short**: 24h
    - **medium**: 7d
    - **long**: 15d
  - Output is keyed by the **end timestamp** of each recommendation window.

## Health

```bash
curl -s localhost:8000/healthz | jq
```

## License

MIT (or your choice)
