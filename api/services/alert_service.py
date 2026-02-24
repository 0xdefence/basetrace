from api.services.db import get_conn


def recent_alerts(limit: int = 20):
    """24h vs prior-24h delta alerting.

    Uses transactions table as stable source for window comparisons.
    """
    alerts = []
    with get_conn() as conn:
        cur = conn.cursor()

        # Fan-out spikes: outbound tx count now vs previous window
        cur.execute(
            """
            WITH now_w AS (
              SELECT from_address AS a, COUNT(*) AS c
              FROM transactions
              WHERE timestamp >= now() - interval '24 hours'
                AND from_address IS NOT NULL
              GROUP BY from_address
            ), prev_w AS (
              SELECT from_address AS a, COUNT(*) AS c
              FROM transactions
              WHERE timestamp >= now() - interval '48 hours'
                AND timestamp < now() - interval '24 hours'
                AND from_address IS NOT NULL
              GROUP BY from_address
            )
            SELECT n.a, n.c AS now_count, COALESCE(p.c, 0) AS prev_count
            FROM now_w n
            LEFT JOIN prev_w p ON p.a = n.a
            WHERE n.c >= 25
            ORDER BY (n.c - COALESCE(p.c,0)) DESC
            LIMIT %s
            """,
            (max(limit, 50),),
        )
        for addr, now_c, prev_c in cur.fetchall():
            baseline = max(1, int(prev_c or 0))
            ratio = float(now_c) / baseline
            delta = int(now_c) - int(prev_c or 0)
            if ratio >= 3.0 and delta >= 20:
                alerts.append(
                    {
                        "type": "fan_out_spike",
                        "address": addr,
                        "severity": "high" if ratio >= 8 else "medium",
                        "confidence": min(0.99, 0.5 + min(ratio, 10) / 12),
                        "evidence": {
                            "window": "24h_vs_prev24h",
                            "now_outbound": int(now_c),
                            "prev_outbound": int(prev_c or 0),
                            "ratio": round(ratio, 2),
                            "delta": delta,
                        },
                    }
                )

        # Fan-in spikes: inbound tx count now vs previous window
        cur.execute(
            """
            WITH now_w AS (
              SELECT to_address AS a, COUNT(*) AS c
              FROM transactions
              WHERE timestamp >= now() - interval '24 hours'
                AND to_address IS NOT NULL
              GROUP BY to_address
            ), prev_w AS (
              SELECT to_address AS a, COUNT(*) AS c
              FROM transactions
              WHERE timestamp >= now() - interval '48 hours'
                AND timestamp < now() - interval '24 hours'
                AND to_address IS NOT NULL
              GROUP BY to_address
            )
            SELECT n.a, n.c AS now_count, COALESCE(p.c, 0) AS prev_count
            FROM now_w n
            LEFT JOIN prev_w p ON p.a = n.a
            WHERE n.c >= 25
            ORDER BY (n.c - COALESCE(p.c,0)) DESC
            LIMIT %s
            """,
            (max(limit, 50),),
        )
        for addr, now_c, prev_c in cur.fetchall():
            baseline = max(1, int(prev_c or 0))
            ratio = float(now_c) / baseline
            delta = int(now_c) - int(prev_c or 0)
            if ratio >= 3.0 and delta >= 20:
                alerts.append(
                    {
                        "type": "fan_in_spike",
                        "address": addr,
                        "severity": "high" if ratio >= 8 else "medium",
                        "confidence": min(0.99, 0.5 + min(ratio, 10) / 12),
                        "evidence": {
                            "window": "24h_vs_prev24h",
                            "now_inbound": int(now_c),
                            "prev_inbound": int(prev_c or 0),
                            "ratio": round(ratio, 2),
                            "delta": delta,
                        },
                    }
                )

        # New high-centrality nodes in last 24h
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
            SELECT a, out_c, in_c
            FROM agg
            WHERE (out_c + in_c) >= 300
            ORDER BY (out_c + in_c) DESC
            LIMIT %s
            """,
            (max(limit, 30),),
        )
        for addr, out_c, in_c in cur.fetchall():
            alerts.append(
                {
                    "type": "new_high_centrality_node",
                    "address": addr,
                    "severity": "medium",
                    "confidence": 0.7,
                    "evidence": {
                        "window": "last_24h",
                        "outbound": int(out_c or 0),
                        "inbound": int(in_c or 0),
                        "degree_proxy": int((out_c or 0) + (in_c or 0)),
                    },
                }
            )

    # sort by confidence desc then severity
    sev_rank = {"high": 3, "medium": 2, "low": 1}
    alerts.sort(key=lambda x: (x.get("confidence", 0), sev_rank.get(x.get("severity", "low"), 1)), reverse=True)
    return alerts[:limit]
