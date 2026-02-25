from fastapi import APIRouter

from api.services.runbook_service import ingest_runbook

router = APIRouter()


@router.get("/ingest")
def runbook_ingest():
    return ingest_runbook()
