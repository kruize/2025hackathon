# app/routers/cost.py
from fastapi import APIRouter, Query
from ..services.cost_service import get_cost as svc

router = APIRouter(prefix="/data", tags=["cost"])

@router.get("/cost")
def get_cost(
    resolution: str = Query("daily", regex="^(hourly|daily|weekly|monthly)$")
):
    return svc(resolution=resolution)
