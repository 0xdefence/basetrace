from fastapi import APIRouter, HTTPException

from api.services.alert_service import update_alert_status

router = APIRouter()


@router.post("/{alert_id}/ack")
def ack_alert(alert_id: int, assignee: str | None = None):
    item = update_alert_status(alert_id, "ack", assignee=assignee)
    if not item:
        raise HTTPException(status_code=404, detail="alert not found")
    return item


@router.post("/{alert_id}/resolve")
def resolve_alert(alert_id: int, assignee: str | None = None):
    item = update_alert_status(alert_id, "resolved", assignee=assignee)
    if not item:
        raise HTTPException(status_code=404, detail="alert not found")
    return item
