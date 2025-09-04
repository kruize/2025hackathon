from fastapi import FastAPI
from .db import init_db, get_db
from .routers.datasets import router as datasets_router
from .routers.metrics import router as metrics_router
from .routers.cluster import router as cluster_router
from .routers.recommendations import router as recs_router
from .routers.cost import router as cost_router
from .constants import DB_PATH
from .queries import COUNT_TABLE

app = FastAPI(title="FastAPI Sample (SQLite, modular)")

@app.on_event("startup")
def startup():
    init_db()

@app.get("/")
def root():
    return {
        "message": "OK. See /docs",
        "endpoints": [
            "/data/create (POST)",
            "/data/get/raw (GET)",
            "/data/get/agg (GET)",
            "/data/get/recommendations (GET)",
            "/data/cluster (GET)",
            "/healthz (GET)"
        ],
        "db_path": DB_PATH
    }

@app.get("/healthz")
def healthz():
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(COUNT_TABLE.format(table="datasets")); datasets = cur.fetchone()["c"]
        cur.execute(COUNT_TABLE.format(table="samples"));  samples  = cur.fetchone()["c"]
        return {"status":"ok","datasets":datasets,"samples":samples}
    finally:
        conn.close()

# Wire routers
app.include_router(datasets_router)
app.include_router(metrics_router)
app.include_router(cluster_router)
app.include_router(recs_router)
app.include_router(cost_router)

