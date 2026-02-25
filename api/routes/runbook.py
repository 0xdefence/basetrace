from fastapi import APIRouter, HTTPException

from api.services.alert_service import get_thresholds, update_threshold
from api.services.runbook_service import (
    alerts_runbook,
    failures_runbook,
    ingest_runbook,
    resolve_failure,
    retry_failure,
)

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


@router.post("/failures/{failure_id}/retry")
def runbook_failure_retry(failure_id: int):
    item = retry_failure(failure_id)
    if not item:
        raise HTTPException(status_code=404, detail="failure not found")
    return item


@router.post("/failures/{failure_id}/resolve")
def runbook_failure_resolve(failure_id: int):
    item = resolve_failure(failure_id)
    if not item:
        raise HTTPException(status_code=404, detail="failure not found")
    return item


@router.get("/thresholds")
def runbook_thresholds():
    return get_thresholds()


@router.post("/thresholds/{rule_type}")
def runbook_threshold_update(
    rule_type: str,
    min_ratio: float | None = None,
    min_delta: int | None = None,
    min_count: int | None = None,
    cooldown_hours: int | None = None,
    enabled: bool | None = None,
):
    row = update_threshold(rule_type, min_ratio, min_delta, min_count, cooldown_hours, enabled)
    return {"rule_type": rule_type, "config": row}
