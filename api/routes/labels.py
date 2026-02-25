from fastapi import APIRouter

from api.services.label_service import get_labels
from labels.taxonomy import LABEL_TAXONOMY

router = APIRouter()


@router.get("/taxonomy")
def taxonomy():
    return {"labels": LABEL_TAXONOMY}


@router.get("/{address}")
def labels(address: str):
    return get_labels(address)
