from api.services.db import get_conn


def ingest_runbook():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT key, value, updated_at FROM ingest_state")
        state_rows = cur.fetchall()
        state = {k: {"value": v, "updated_at": ts.isoformat() if ts else None} for k, v, ts in state_rows}

        cur.execute("SELECT COUNT(*) FROM alerts WHERE status='new'")
        new_alerts = int(cur.fetchone()[0] or 0)

        cur.execute("SELECT COUNT(*) FROM transactions")
        tx_total = int(cur.fetchone()[0] or 0)

    return {
        "ingest_state": state,
        "new_alerts": new_alerts,
        "transactions_total": tx_total,
        "notes": [
            "If last_error is non-empty, inspect ingestor logs and RPC provider health.",
            "If ingest lag grows, add RPC fallback providers and reduce log query pressure.",
            "If alert volume spikes, review /alerts/queue and tune threshold ratios.",
        ],
    }


def alerts_runbook():
    with get_conn() as conn:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT status, COUNT(*)
            FROM alerts
            GROUP BY status
            """
        )
        rows = cur.fetchall()
        counts = {"new": 0, "ack": 0, "resolved": 0}
        for status, c in rows:
            counts[str(status)] = int(c or 0)

        cur.execute(
            """
            SELECT
              percentile_cont(0.5) WITHIN GROUP (ORDER BY confidence)
            FROM alerts
            WHERE status = 'new'
            """
        )
        median_new_conf = cur.fetchone()[0]

        cur.execute(
            """
            SELECT
              percentile_cont(0.5) WITHIN GROUP (ORDER BY confidence)
            FROM alerts
            WHERE status = 'ack'
            """
        )
        median_ack_conf = cur.fetchone()[0]

        cur.execute(
            """
            SELECT
              percentile_cont(0.5) WITHIN GROUP (ORDER BY confidence)
            FROM alerts
            WHERE status = 'resolved'
            """
        )
        median_resolved_conf = cur.fetchone()[0]

        cur.execute(
            """
            SELECT COALESCE(
              AVG(EXTRACT(EPOCH FROM (resolved_at - ack_at)))
              FILTER (WHERE resolved_at IS NOT NULL AND ack_at IS NOT NULL),
              0
            )
            FROM alerts
            """
        )
        avg_ack_to_resolve_secs = float(cur.fetchone()[0] or 0.0)

    backlog_pressure = "low"
    if counts.get("new", 0) > max(25, counts.get("ack", 0) * 2):
        backlog_pressure = "high"
    elif counts.get("new", 0) > 10:
        backlog_pressure = "medium"

    return {
        "queue_counts": counts,
        "median_confidence": {
            "new": float(median_new_conf) if median_new_conf is not None else None,
            "ack": float(median_ack_conf) if median_ack_conf is not None else None,
            "resolved": float(median_resolved_conf) if median_resolved_conf is not None else None,
        },
        "avg_ack_to_resolve_seconds": round(avg_ack_to_resolve_secs, 2),
        "backlog_pressure": backlog_pressure,
    }
