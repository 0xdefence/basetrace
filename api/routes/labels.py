from fastapi import APIRouter

from api.services.label_service import get_labels

router = APIRouter()


@router.get("/{address}")
def labels(address: str):
    return get_labels(address)
