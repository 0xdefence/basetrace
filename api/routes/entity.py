from fastapi import APIRouter

from api.services.entity_service import get_entity_profile

router = APIRouter()


@router.get("/{address}")
def entity_profile(address: str):
    return get_entity_profile(address)
