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
