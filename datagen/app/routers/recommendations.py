from fastapi import APIRouter, Query
from ..models import WorkloadType
from ..services.recommendations_service import get_recommendations as svc

router = APIRouter(prefix="/data/get", tags=["recommendations"])

@router.get("/recommendations")
def get_recommendations(namespace: str,
                        workload_type: WorkloadType,
                        workload_name: str,
                        container_name: str,
                        rec_freq: str | None = None,
                        from_: str | None = Query(None, alias="from"),
                        to: str | None = Query(None, alias="to")):
    return svc(namespace, workload_type.value, workload_name, container_name, rec_freq, from_, to)
