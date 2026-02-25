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


@router.post("/threshold-presets/{preset}")
def runbook_threshold_preset(preset: str):
    p = preset.lower()
    presets = {
        "conservative": {
            "fan_out_spike": {"min_ratio": 5.0, "min_delta": 35, "min_count": 40, "cooldown_hours": 8, "enabled": True},
            "fan_in_spike": {"min_ratio": 5.0, "min_delta": 35, "min_count": 40, "cooldown_hours": 8, "enabled": True},
            "new_high_centrality_node": {"min_count": 500, "cooldown_hours": 8, "enabled": True},
            "anomalous_bridge_path": {"min_ratio": 6.0, "min_delta": 25, "cooldown_hours": 8, "enabled": True},
        },
        "base": {
            "fan_out_spike": {"min_ratio": 3.0, "min_delta": 20, "min_count": 25, "cooldown_hours": 6, "enabled": True},
            "fan_in_spike": {"min_ratio": 3.0, "min_delta": 20, "min_count": 25, "cooldown_hours": 6, "enabled": True},
            "new_high_centrality_node": {"min_count": 300, "cooldown_hours": 6, "enabled": True},
            "anomalous_bridge_path": {"min_ratio": 4.0, "min_delta": 15, "cooldown_hours": 6, "enabled": True},
        },
        "aggressive": {
            "fan_out_spike": {"min_ratio": 2.0, "min_delta": 10, "min_count": 15, "cooldown_hours": 3, "enabled": True},
            "fan_in_spike": {"min_ratio": 2.0, "min_delta": 10, "min_count": 15, "cooldown_hours": 3, "enabled": True},
            "new_high_centrality_node": {"min_count": 180, "cooldown_hours": 3, "enabled": True},
            "anomalous_bridge_path": {"min_ratio": 2.5, "min_delta": 8, "cooldown_hours": 3, "enabled": True},
        },
    }
    cfg = presets.get(p)
    if not cfg:
        raise HTTPException(status_code=400, detail="unknown preset")

    applied = {}
    for rule_type, vals in cfg.items():
        applied[rule_type] = update_threshold(
            rule_type,
            vals.get("min_ratio"),
            vals.get("min_delta"),
            vals.get("min_count"),
            vals.get("cooldown_hours"),
            vals.get("enabled"),
        )

    return {"preset": p, "applied": applied}
