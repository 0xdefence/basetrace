import json
from typing import Any, Dict, List

from alerts.notifiers import send_discord, send_telegram
from api.services.db import get_conn


def _persist(alert_id: int | None, result: Dict[str, Any], payload: Dict[str, Any]) -> None:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO alert_deliveries(alert_id, channel, destination, status, attempts, error, payload)
            VALUES(%s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            (
                alert_id,
                result.get("channel"),
                result.get("destination"),
                "sent" if result.get("ok") else "failed",
                1,
                result.get("error"),
                json.dumps(payload),
            ),
        )


def send_test_alert(channel: str, payload: Dict[str, Any] | None = None):
    alert = payload or {
        "type": "test_alert",
        "address": "0x0000000000000000000000000000000000000000",
        "severity": "medium",
        "confidence": 0.66,
        "evidence": {"source": "runbook_test"},
    }

    c = channel.lower().strip()
    if c == "discord":
        result = send_discord(alert)
    elif c == "telegram":
        result = send_telegram(alert)
    else:
        raise ValueError("unsupported channel")

    _persist(None, result, alert)
    return {"channel": c, "result": result}


def recent_deliveries(limit: int = 50, status: str | None = None) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        cur = conn.cursor()
        if status:
            cur.execute(
                """
                SELECT id, alert_id, channel, destination, status, attempts, error, payload, created_at
                FROM alert_deliveries
                WHERE status=%s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (status, limit),
            )
        else:
            cur.execute(
                """
                SELECT id, alert_id, channel, destination, status, attempts, error, payload, created_at
                FROM alert_deliveries
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
        rows = cur.fetchall()

    out = []
    for i, alert_id, channel_name, dest, st, attempts, err, payload, created_at in rows:
        out.append(
            {
                "id": int(i),
                "alert_id": int(alert_id) if alert_id is not None else None,
                "channel": channel_name,
                "destination": dest,
                "status": st,
                "attempts": int(attempts or 1),
                "error": err,
                "payload": payload or {},
                "created_at": created_at.isoformat() if created_at else None,
            }
        )
    return out
