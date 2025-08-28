from fastapi import APIRouter
from ..services.cluster_service import get_cluster_inventory as svc

router = APIRouter(prefix="/data", tags=["cluster"])

@router.get("/cluster")
def get_cluster():
    return svc()
