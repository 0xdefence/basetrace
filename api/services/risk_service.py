from api.services.db import get_conn
from api.services.label_service import get_labels


def entity_risk(address: str):
    addr = address.lower()
    labels_bundle = get_labels(addr)

    with get_conn() as conn:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT
              COUNT(*) FILTER (WHERE status='new') AS new_alerts,
              COUNT(*) FILTER (WHERE severity='high') AS high_alerts,
              COALESCE(AVG(confidence),0)
            FROM alerts
            WHERE address = %s
              AND created_at >= now() - interval '7 days'
            """,
            (addr,),
        )
        new_alerts, high_alerts, avg_conf = cur.fetchone()

        cur.execute(
            """
            WITH recent AS (
              SELECT from_address AS a, COUNT(*) AS out_c, 0::bigint AS in_c
              FROM transactions
              WHERE timestamp >= now() - interval '24 hours' AND from_address IS NOT NULL
              GROUP BY from_address
              UNION ALL
              SELECT to_address AS a, 0::bigint AS out_c, COUNT(*) AS in_c
              FROM transactions
              WHERE timestamp >= now() - interval '24 hours' AND to_address IS NOT NULL
              GROUP BY to_address
            ), agg AS (
              SELECT a, SUM(out_c) AS out_c, SUM(in_c) AS in_c
              FROM recent GROUP BY a
            )
            SELECT COALESCE(out_c,0), COALESCE(in_c,0)
            FROM agg
            WHERE a = %s
            """,
            (addr,),
        )
        row = cur.fetchone() or (0, 0)
        out_24h, in_24h = int(row[0] or 0), int(row[1] or 0)

        cur.execute(
            """
            SELECT
              COALESCE(SUM(CASE WHEN from_address = %s THEN value_wei ELSE 0 END),0),
              COALESCE(SUM(CASE WHEN to_address = %s THEN value_wei ELSE 0 END),0)
            FROM transactions
            WHERE timestamp >= now() - interval '7 days'
              AND (from_address = %s OR to_address = %s)
            """,
            (addr, addr, addr, addr),
        )
        out_wei_7d, in_wei_7d = cur.fetchone()

    label_risk = 0.0
    for lb in labels_bundle.get("labels", []):
        l = lb.get("label")
        c = float(lb.get("confidence", 0))
        if l in {"bridge", "exchange-facing", "high-activity", "router"}:
            label_risk += c * 20
        elif l in {"deployer", "treasury"}:
            label_risk += c * 10

    alert_risk = min(45.0, (int(new_alerts or 0) * 4.0) + (int(high_alerts or 0) * 8.0) + float(avg_conf or 0) * 10)
    centrality_risk = min(25.0, ((out_24h + in_24h) / 50.0))

    flow_mag = float(out_wei_7d or 0) + float(in_wei_7d or 0)
    flow_risk = min(20.0, flow_mag / 1e21)

    score = max(0.0, min(100.0, label_risk + alert_risk + centrality_risk + flow_risk))

    return {
        "address": addr,
        "risk_score": round(score, 2),
        "band": "high" if score >= 70 else "medium" if score >= 40 else "low",
        "factors": {
            "label_risk": round(label_risk, 2),
            "alert_risk": round(alert_risk, 2),
            "centrality_risk": round(centrality_risk, 2),
            "flow_risk": round(flow_risk, 2),
        },
        "stats": {
            "new_alerts_7d": int(new_alerts or 0),
            "high_alerts_7d": int(high_alerts or 0),
            "avg_alert_conf_7d": float(avg_conf or 0),
            "outbound_txs_24h": out_24h,
            "inbound_txs_24h": in_24h,
            "outbound_wei_7d": str(out_wei_7d or 0),
            "inbound_wei_7d": str(in_wei_7d or 0),
        },
        "labels": labels_bundle.get("labels", []),
    }
