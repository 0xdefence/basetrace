from fastapi import APIRouter

from api.services.risk_service import entity_risk

router = APIRouter()


@router.get("/{address}/risk")
def risk(address: str):
    return entity_risk(address)
