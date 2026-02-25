import hashlib
import json
from typing import Any, Dict, List, Optional

from api.services.db import get_conn

BRIDGES = {
    "0x4200000000000000000000000000000000000010",  # L2StandardBridge
    "0x4200000000000000000000000000000000000007",  # L2CrossDomainMessenger
}


def _ensure_alert_columns() -> None:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("ALTER TABLE alerts ADD COLUMN IF NOT EXISTS assignee TEXT")
        cur.execute("ALTER TABLE alerts ADD COLUMN IF NOT EXISTS ack_at TIMESTAMPTZ")
        cur.execute("ALTER TABLE alerts ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ")


def _fingerprint(alert: Dict[str, Any]) -> str:
    base = {
        "type": alert.get("type"),
        "address": (alert.get("address") or "").lower(),
        "window": (alert.get("evidence") or {}).get("window"),
    }
    return hashlib.sha256(json.dumps(base, sort_keys=True).encode()).hexdigest()[:16]


def _persist_alerts(candidates: List[Dict[str, Any]], dedupe_hours: int = 6) -> None:
    if not candidates:
        return

    _ensure_alert_columns()
    with get_conn() as conn:
        cur = conn.cursor()
        for a in candidates:
            fp = _fingerprint(a)
            cur.execute(
                """
                SELECT 1 FROM alerts
                WHERE fingerprint = %s
                  AND created_at >= now() - (%s || ' hours')::interval
                LIMIT 1
                """,
                (fp, dedupe_hours),
            )
            if cur.fetchone():
                continue

            cur.execute(
                """
                INSERT INTO alerts(type, address, severity, confidence, evidence, fingerprint)
                VALUES(%s, %s, %s, %s, %s::jsonb, %s)
                """,
                (
                    a.get("type"),
                    (a.get("address") or "").lower(),
                    a.get("severity", "medium"),
                    float(a.get("confidence", 0.5)),
                    json.dumps(a.get("evidence", {})),
                    fp,
                ),
            )


def _generate_alert_candidates(limit: int = 20) -> List[Dict[str, Any]]:
    alerts: List[Dict[str, Any]] = []

    with get_conn() as conn:
        cur = conn.cursor()

        # Fan-out spikes (24h vs previous 24h)
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

        # Fan-in spikes (24h vs previous 24h)
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

        # Bridge route anomalies (24h vs previous 24h)
        cur.execute(
            """
            WITH now_w AS (
              SELECT CASE WHEN from_address = ANY(%s) THEN to_address ELSE from_address END AS cp,
                     COUNT(*) AS c
              FROM transactions
              WHERE timestamp >= now() - interval '24 hours'
                AND (from_address = ANY(%s) OR to_address = ANY(%s))
              GROUP BY cp
            ), prev_w AS (
              SELECT CASE WHEN from_address = ANY(%s) THEN to_address ELSE from_address END AS cp,
                     COUNT(*) AS c
              FROM transactions
              WHERE timestamp >= now() - interval '48 hours'
                AND timestamp < now() - interval '24 hours'
                AND (from_address = ANY(%s) OR to_address = ANY(%s))
              GROUP BY cp
            )
            SELECT n.cp, n.c AS now_count, COALESCE(p.c,0) AS prev_count
            FROM now_w n
            LEFT JOIN prev_w p ON p.cp = n.cp
            WHERE n.cp IS NOT NULL
            ORDER BY (n.c - COALESCE(p.c,0)) DESC
            LIMIT %s
            """,
            (list(BRIDGES), list(BRIDGES), list(BRIDGES), list(BRIDGES), list(BRIDGES), list(BRIDGES), max(limit, 30)),
        )
        for cp, now_c, prev_c in cur.fetchall():
            baseline = max(1, int(prev_c or 0))
            ratio = float(now_c) / baseline
            delta = int(now_c) - int(prev_c or 0)
            if ratio >= 4.0 and delta >= 15:
                alerts.append(
                    {
                        "type": "anomalous_bridge_path",
                        "address": cp,
                        "severity": "high" if ratio >= 8 else "medium",
                        "confidence": min(0.99, 0.55 + min(ratio, 10) / 12),
                        "evidence": {
                            "window": "24h_vs_prev24h",
                            "bridge_counterparty_now": int(now_c),
                            "bridge_counterparty_prev": int(prev_c or 0),
                            "ratio": round(ratio, 2),
                            "delta": delta,
                        },
                    }
                )

    return alerts


def _format_rows(rows):
    return [
        {
            "id": int(i),
            "type": t,
            "address": a,
            "severity": s,
            "confidence": float(c or 0),
            "evidence": e or {},
            "status": st,
            "assignee": assignee,
            "ack_at": ack_at.isoformat() if ack_at else None,
            "resolved_at": resolved_at.isoformat() if resolved_at else None,
            "created_at": created.isoformat() if created else None,
        }
        for i, t, a, s, c, e, st, assignee, ack_at, resolved_at, created in rows
    ]


def recent_alerts(limit: int = 20, status: Optional[str] = None):
    candidates = _generate_alert_candidates(limit=max(limit, 50))
    _persist_alerts(candidates)

    with get_conn() as conn:
        cur = conn.cursor()
        if status:
            cur.execute(
                """
                SELECT id, type, address, severity, confidence, evidence, status, assignee, ack_at, resolved_at, created_at
                FROM alerts
                WHERE status = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (status, limit),
            )
        else:
            cur.execute(
                """
                SELECT id, type, address, severity, confidence, evidence, status, assignee, ack_at, resolved_at, created_at
                FROM alerts
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
        rows = cur.fetchall()

    return _format_rows(rows)


def alerts_for_address(address: str, limit: int = 20, status: Optional[str] = None):
    with get_conn() as conn:
        cur = conn.cursor()
        if status:
            cur.execute(
                """
                SELECT id, type, address, severity, confidence, evidence, status, assignee, ack_at, resolved_at, created_at
                FROM alerts
                WHERE address = %s AND status = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (address.lower(), status, limit),
            )
        else:
            cur.execute(
                """
                SELECT id, type, address, severity, confidence, evidence, status, assignee, ack_at, resolved_at, created_at
                FROM alerts
                WHERE address = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (address.lower(), limit),
            )
        rows = cur.fetchall()

    return _format_rows(rows)


def alert_queue(limit: int = 20, status: str = "new"):
    _ensure_alert_columns()
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, type, address, severity, confidence, evidence, status, assignee, ack_at, resolved_at, created_at
            FROM alerts
            WHERE status = %s
            ORDER BY
              CASE severity WHEN 'high' THEN 3 WHEN 'medium' THEN 2 ELSE 1 END DESC,
              confidence DESC,
              created_at DESC
            LIMIT %s
            """,
            (status, limit),
        )
        rows = cur.fetchall()
    return _format_rows(rows)


def update_alert_status(alert_id: int, status: str, assignee: Optional[str] = None):
    if status not in {"new", "ack", "resolved"}:
        raise ValueError("invalid status")

    _ensure_alert_columns()
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE alerts
            SET status = %s,
                assignee = COALESCE(%s, assignee),
                ack_at = CASE WHEN %s = 'ack' THEN now() ELSE ack_at END,
                resolved_at = CASE WHEN %s = 'resolved' THEN now() ELSE resolved_at END
            WHERE id = %s
            RETURNING id, type, address, severity, confidence, evidence, status, assignee, ack_at, resolved_at, created_at
            """,
            (status, assignee, status, status, alert_id),
        )
        row = cur.fetchone()

    if not row:
        return None

    return _format_rows([row])[0]
