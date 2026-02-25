from fastapi import APIRouter

from api.services.alert_service import alerts_for_address, recent_alerts

router = APIRouter()


@router.get("/recent")
def recent(limit: int = 20, status: str | None = None):
    return {"limit": limit, "status": status, "alerts": recent_alerts(limit=limit, status=status)}


@router.get("/{address}")
def by_address(address: str, limit: int = 20, status: str | None = None):
    return {
        "address": address.lower(),
        "limit": limit,
        "status": status,
        "alerts": alerts_for_address(address, limit=limit, status=status),
    }
