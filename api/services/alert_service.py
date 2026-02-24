from api.services.db import get_conn


def recent_alerts(limit: int = 20):
    # v1: derive lightweight alerts from edge concentration snapshots
    alerts = []
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT src_address, COUNT(*) AS edge_count, SUM(tx_count) AS txs
            FROM edges
            GROUP BY src_address
            ORDER BY txs DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall()

    for src, edge_count, txs in rows:
        if (txs or 0) > 1000 and (edge_count or 0) > 100:
            alerts.append(
                {
                    "type": "fan_out_spike",
                    "address": src,
                    "severity": "medium",
                    "evidence": {"edge_count": int(edge_count or 0), "txs": int(txs or 0)},
                }
            )

    return alerts[:limit]
