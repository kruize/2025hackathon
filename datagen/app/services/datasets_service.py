import sqlite3
from datetime import datetime, timezone
from ..db import get_db
from ..models import CreateDataRequest, DatasetOut, CreateResponse
from ..queries import INSERT_DATASET, SELECT_DATASET
from fastapi import HTTPException
from ..data_gen.generator import generate_series

def create_dataset(req: CreateDataRequest) -> CreateResponse:
    conn = get_db()
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                INSERT_DATASET,
                (
                    int(datetime.now(timezone.utc).timestamp()),
                    req.namespace, req.workload_type.value, req.workload_name, req.container_name,
                    req.scenario.value, req.days, req.interval_in_secs, req.measurement_duration_secs
                )
            )
            conn.commit()
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Data already exists for (namespace, workload_type, workload_name, container_name).")

        dataset_id = cur.lastrowid
        num_samples = generate_series(req, dataset_id, conn)

        cur.execute("SELECT * FROM datasets WHERE id = ?", (dataset_id,))
        row = cur.fetchone()
        dataset = DatasetOut(
            id=row["id"],
            created_at_utc=row["created_at_utc"],
            namespace=row["namespace"],
            workload_type=row["workload_type"],
            workload_name=row["workload_name"],
            container_name=row["container_name"],
            scenario=row["scenario"],
            days=row["days"],
            interval_in_secs=row["interval_in_secs"],
            measurement_duration_secs=row["measurement_duration_secs"],
        )
        return CreateResponse(dataset=dataset, num_samples=num_samples)
    finally:
        conn.close()
