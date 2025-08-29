from fastapi import APIRouter, Query
from ..services.raw_service import get_raw as svc_get_raw
from ..services.agg_service import get_agg as svc_get_agg
from ..models import WorkloadType

router = APIRouter(prefix="/data/get", tags=["metrics"])

@router.get("/raw")
def get_raw(namespace: str,
            workload_type: WorkloadType,
            workload_name: str,
            container_name: str,
            from_: str | None = Query(None, alias="from"),
            to: str | None = Query(None, alias="to"),
            last: str | None = Query(None, alias="last"),
            agg_func: str | None = Query(None, alias="agg_func"),
            foreach: str | None = Query(None, alias="foreach")):
    return svc_get_raw(namespace=namespace,
                       workload_type=workload_type.value,
                       workload_name=workload_name,
                       container_name=container_name,
                       from_str=from_,
                       to_str=to,
                       last=last,
                       agg_func=agg_func,
                       foreach=foreach)

@router.get("/agg")
def get_agg(namespace: str,
            workload_type: WorkloadType,
            workload_name: str,
            container_name: str,
            agg_time: str | None = None,
            from_: str | None = Query(None, alias="from"),
            to: str | None = Query(None, alias="to")):
    return svc_get_agg(namespace, workload_type.value, workload_name, container_name, agg_time, from_, to)
