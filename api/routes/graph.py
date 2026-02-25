from fastapi import APIRouter

from api.services.graph_service import get_global_graph, get_neighbors

router = APIRouter()


@router.get("/global")
def global_graph(limit: int = 80):
    return get_global_graph(limit=min(limit, 200))


@router.get("/neighbors/{address}")
def neighbors(address: str, depth: int = 1, limit: int = 25):
    data = get_neighbors(address, limit=limit)
    return {
        "address": address.lower(),
        "depth": depth,
        "limit": limit,
        **data,
    }
