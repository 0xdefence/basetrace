from fastapi import APIRouter

from api.services.alert_service import recent_alerts

router = APIRouter()


@router.get("/recent")
def recent(limit: int = 20):
    return {"limit": limit, "alerts": recent_alerts(limit=limit)}
