from fastapi import APIRouter

from api.services.runbook_service import alerts_runbook, ingest_runbook

router = APIRouter()


@router.get("/ingest")
def runbook_ingest():
    return ingest_runbook()


@router.get("/alerts")
def runbook_alerts():
    return alerts_runbook()
