from fastapi import APIRouter
from ..services.cost_service import get_cost as svc

router = APIRouter(prefix="/data", tags=["cost"])

@router.get("/cost")
def get_cost():
    return svc()
