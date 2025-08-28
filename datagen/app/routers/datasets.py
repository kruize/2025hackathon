from fastapi import APIRouter
from ..models import CreateDataRequest, CreateResponse
from ..services.datasets_service import create_dataset

router = APIRouter(prefix="/data", tags=["data"])

@router.post("/create", response_model=CreateResponse, status_code=201)
def create(req: CreateDataRequest):
    return create_dataset(req)
