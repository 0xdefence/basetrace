from fastapi import APIRouter

router = APIRouter()


@router.get("/neighbors/{address}")
def neighbors(address: str, depth: int = 1, limit: int = 25):
    return {
        "address": address,
        "depth": depth,
        "limit": limit,
        "nodes": [],
        "edges": [],
        "note": "scaffold response; wire DB query in api/services/graph_service.py",
    }
