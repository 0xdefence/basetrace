from fastapi import APIRouter

from api.services.runbook_service import alerts_runbook, failures_runbook, ingest_runbook

router = APIRouter()


@router.get("/ingest")
def runbook_ingest():
    return ingest_runbook()


@router.get("/alerts")
def runbook_alerts():
    return alerts_runbook()


@router.get("/failures")
def runbook_failures(limit: int = 100):
    return failures_runbook(limit=limit)
