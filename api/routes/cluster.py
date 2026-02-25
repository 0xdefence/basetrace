from fastapi import APIRouter

from api.services.cluster_service import get_cluster

router = APIRouter()


@router.get("/{address}")
def cluster(address: str, limit: int = 200):
    return get_cluster(address, limit=limit)
