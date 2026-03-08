from api.services.db import get_conn
from api.services.metrics_service import get_metrics
from api.services.runbook_service import alerts_runbook, failures_runbook


def dashboard_summary(hot_limit: int = 5):
    metrics = get_metrics()
    queue = alerts_runbook()
    failures = failures_runbook(limit=200)

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, type, address, severity, confidence, status, created_at
            FROM alerts
            WHERE status IN ('new', 'ack')
            ORDER BY CASE severity WHEN 'high' THEN 3 WHEN 'medium' THEN 2 ELSE 1 END DESC,
                     confidence DESC,
                     created_at DESC
            LIMIT %s
            """,
            (hot_limit,),
        )
        hot_rows = cur.fetchall()

        cur.execute(
            """
            SELECT type, COUNT(*)
            FROM alerts
            WHERE created_at >= now() - interval '24 hours'
            GROUP BY type
            ORDER BY COUNT(*) DESC
            LIMIT 5
            """
        )
        top_types_rows = cur.fetchall()

        cur.execute(
            """
            SELECT address, COUNT(*) AS c
            FROM alerts
            WHERE created_at >= now() - interval '24 hours'
            GROUP BY address
            ORDER BY c DESC
            LIMIT 5
            """
        )
        top_addr_rows = cur.fetchall()

        cur.execute(
            """
            SELECT address, tx_count
            FROM addresses
            ORDER BY tx_count DESC
            LIMIT %s
            """,
            (hot_limit,),
        )
        hot_addr_rows = cur.fetchall()

        waitlist_signups = 0
        try:
            cur.execute("SELECT COUNT(*) FROM waitlist_signups")
            waitlist_signups = int(cur.fetchone()[0] or 0)
        except Exception:
            waitlist_signups = 0

    hot_alerts = [
        {
            "id": int(i),
            "type": t,
            "address": a,
            "severity": s,
            "confidence": float(c or 0),
            "status": st,
            "created_at": created.isoformat() if created else None,
        }
        for i, t, a, s, c, st, created in hot_rows
    ]

    top_types = [{"type": t, "count": int(c)} for t, c in top_types_rows]
    top_addresses = [{"address": a, "count": int(c)} for a, c in top_addr_rows]
    hot_addresses = [{"address": a, "tx_count": int(c)} for a, c in hot_addr_rows]

    queue_counts = queue.get("queue_counts") or {}
    total_queue = queue_counts.get("new", 0) + queue_counts.get("ack", 0) + queue_counts.get("resolved", 0)
    ack_rate = (queue_counts.get("ack", 0) + queue_counts.get("resolved", 0)) / total_queue if total_queue else 0.0

    return {
        "compact": {
            "ingest_lag_blocks": metrics.get("ingest_lag_blocks"),
            "tx_24h": metrics.get("tx_24h"),
            "transfers_24h": metrics.get("transfers_24h"),
            "alerts_24h": metrics.get("alerts_24h"),
            "queue_new": queue_counts.get("new", 0),
            "queue_ack": queue_counts.get("ack", 0),
            "queue_resolved": queue_counts.get("resolved", 0),
            "backlog_pressure": queue.get("backlog_pressure"),
            "dead_letter_open": (failures.get("summary") or {}).get("open", 0),
        },
        "summary": {
            "metrics": metrics,
            "queue": queue,
            "dead_letter": failures.get("summary", {}),
            "top_alert_types_24h": top_types,
            "top_alert_addresses_24h": top_addresses,
            "hot_alerts": hot_alerts,
            "hot_addresses": hot_addresses,
            "kpis": {
                "product": {
                    "median_query_latency_ms": metrics.get("median_query_latency_ms"),
                    "alerts_24h": metrics.get("alerts_24h"),
                    "alert_acknowledged_rate": round(ack_rate, 4),
                },
                "gtm": {
                    "waitlist_signups": waitlist_signups,
                    "demos_booked": None,
                    "weekly_returning_users": None,
                },
            },
        },
    }
