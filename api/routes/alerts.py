from fastapi import APIRouter

router = APIRouter()


@router.get("/recent")
def recent(limit: int = 20):
    return {"limit": limit, "alerts": []}
