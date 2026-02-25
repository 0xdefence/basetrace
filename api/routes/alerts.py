from fastapi import APIRouter

from api.services.alert_service import alerts_for_address, recent_alerts

router = APIRouter()


@router.get("/recent")
def recent(limit: int = 20):
    return {"limit": limit, "alerts": recent_alerts(limit=limit)}


@router.get("/{address}")
def by_address(address: str, limit: int = 20):
    return {"address": address.lower(), "limit": limit, "alerts": alerts_for_address(address, limit=limit)}
