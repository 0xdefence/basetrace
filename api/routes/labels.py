from fastapi import APIRouter

router = APIRouter()


@router.get("/{address}")
def labels(address: str):
    return {
        "address": address,
        "labels": [],
        "note": "scaffold response; wire label engine in labels/rules.py",
    }
