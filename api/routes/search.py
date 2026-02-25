from fastapi import APIRouter

from api.services.search_service import search_entities

router = APIRouter()


@router.get("")
def search(q: str, limit: int = 20):
    return {"query": q, "limit": limit, "results": search_entities(q, limit=limit)}
