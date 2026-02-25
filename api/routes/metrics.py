from fastapi import APIRouter

from api.services.metrics_service import get_metrics

router = APIRouter()


@router.get("")
def metrics():
    return get_metrics()
