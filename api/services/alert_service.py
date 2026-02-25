import hashlib
import json
from typing import Any, Dict, List, Optional

from api.services.db import get_conn

BRIDGES = {
    "0x4200000000000000000000000000000000000010",  # L2StandardBridge
    "0x4200000000000000000000000000000000000007",  # L2CrossDomainMessenger
}

DEFAULT_THRESHOLDS = {
    "fan_out_spike": {"min_ratio": 3.0, "min_delta": 20, "min_count": 25, "cooldown_hours": 6, "enabled": True},
    "fan_in_spike": {"min_ratio": 3.0, "min_delta": 20, "min_count": 25, "cooldown_hours": 6, "enabled": True},
    "new_high_centrality_node": {"min_ratio": 1.0, "min_delta": 0, "min_count": 300, "cooldown_hours": 6, "enabled": True},
    "anomalous_bridge_path": {"min_ratio": 4.0, "min_delta": 15, "min_count": 1, "cooldown_hours": 6, "enabled": True},
}


def _ensure_schema() -> None:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("ALTER TABLE alerts ADD COLUMN IF NOT EXISTS assignee TEXT")
        cur.execute("ALTER TABLE alerts ADD COLUMN IF NOT EXISTS ack_at TIMESTAMPTZ")
        cur.execute("ALTER TABLE alerts ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS alert_thresholds (
              rule_type TEXT PRIMARY KEY,
              min_ratio NUMERIC,
              min_delta INT,
              min_count INT,
              cooldown_hours INT DEFAULT 6,
              enabled BOOLEAN DEFAULT TRUE,
              updated_at TIMESTAMPTZ DEFAULT now()
            )
            """
        )
        for rt, cfg in DEFAULT_THRESHOLDS.items():
            cur.execute(
                """
                INSERT INTO alert_thresholds(rule_type, min_ratio, min_delta, min_count, cooldown_hours, enabled, updated_at)
                VALUES(%s,%s,%s,%s,%s,%s,now())
                ON CONFLICT (rule_type) DO NOTHING
                """,
                (rt, cfg["min_ratio"], cfg["min_delta"], cfg["min_count"], cfg["cooldown_hours"], cfg["enabled"]),
            )


def _load_thresholds() -> Dict[str, Dict[str, Any]]:
    _ensure_schema()
    out = {k: dict(v) for k, v in DEFAULT_THRESHOLDS.items()}
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT rule_type, min_ratio, min_delta, min_count, cooldown_hours, enabled FROM alert_thresholds")
        for rt, r, d, c, cd, en in cur.fetchall():
            out[str(rt)] = {
                "min_ratio": float(r) if r is not None else out.get(rt, {}).get("min_ratio", 1.0),
                "min_delta": int(d) if d is not None else out.get(rt, {}).get("min_delta", 0),
                "min_count": int(c) if c is not None else out.get(rt, {}).get("min_count", 0),
                "cooldown_hours": int(cd) if cd is not None else out.get(rt, {}).get("cooldown_hours", 6),
                "enabled": bool(en),
            }
    return out


def _fingerprint(alert: Dict[str, Any]) -> str:
    base = {
        "type": alert.get("type"),
        "address": (alert.get("address") or "").lower(),
        "window": (alert.get("evidence") or {}).get("window"),
    }
    return hashlib.sha256(json.dumps(base, sort_keys=True).encode()).hexdigest()[:16]


def _persist_alerts(candidates: List[Dict[str, Any]], thresholds: Dict[str, Dict[str, Any]]) -> None:
    if not candidates:
        return
    with get_conn() as conn:
        cur = conn.cursor()
        for a in candidates:
            rt = a.get("type")
            cooldown = int(thresholds.get(rt, {}).get("cooldown_hours", 6))
            fp = _fingerprint(a)
            cur.execute(
                """
                SELECT 1 FROM alerts
                WHERE fingerprint = %s
                  AND created_at >= now() - (%s || ' hours')::interval
                LIMIT 1
                """,
                (fp, cooldown),
            )
            if cur.fetchone():
                continue
            cur.execute(
                """
                INSERT INTO alerts(type, address, severity, confidence, evidence, fingerprint)
                VALUES(%s, %s, %s, %s, %s::jsonb, %s)
                """,
                (
                    rt,
                    (a.get("address") or "").lower(),
                    a.get("severity", "medium"),
                    float(a.get("confidence", 0.5)),
                    json.dumps(a.get("evidence", {})),
                    fp,
                ),
            )


def _generate_alert_candidates(limit: int = 20, thresholds: Optional[Dict[str, Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    cfg = thresholds or _load_thresholds()
    alerts: List[Dict[str, Any]] = []
    with get_conn() as conn:
        cur = conn.cursor()

        # fan_out_spike
        if cfg["fan_out_spike"]["enabled"]:
            cur.execute(
                """
                WITH now_w AS (
                  SELECT from_address AS a, COUNT(*) AS c
                  FROM transactions
                  WHERE timestamp >= now() - interval '24 hours' AND from_address IS NOT NULL
                  GROUP BY from_address
                ), prev_w AS (
                  SELECT from_address AS a, COUNT(*) AS c
                  FROM transactions
                  WHERE timestamp >= now() - interval '48 hours' AND timestamp < now() - interval '24 hours' AND from_address IS NOT NULL
                  GROUP BY from_address
                )
                SELECT n.a, n.c, COALESCE(p.c,0)
                FROM now_w n LEFT JOIN prev_w p ON p.a=n.a
                WHERE n.c >= %s
                ORDER BY (n.c-COALESCE(p.c,0)) DESC
                LIMIT %s
                """,
                (cfg["fan_out_spike"]["min_count"], max(limit, 50)),
            )
            for addr, now_c, prev_c in cur.fetchall():
                baseline = max(1, int(prev_c or 0))
                ratio = float(now_c) / baseline
                delta = int(now_c) - int(prev_c or 0)
                if ratio >= cfg["fan_out_spike"]["min_ratio"] and delta >= cfg["fan_out_spike"]["min_delta"]:
                    alerts.append({
                        "type": "fan_out_spike",
                        "address": addr,
                        "severity": "high" if ratio >= 8 else "medium",
                        "confidence": min(0.99, 0.5 + min(ratio, 10) / 12),
                        "evidence": {"window": "24h_vs_prev24h", "now_outbound": int(now_c), "prev_outbound": int(prev_c or 0), "ratio": round(ratio, 2), "delta": delta},
                    })

        # fan_in_spike
        if cfg["fan_in_spike"]["enabled"]:
            cur.execute(
                """
                WITH now_w AS (
                  SELECT to_address AS a, COUNT(*) AS c
                  FROM transactions
                  WHERE timestamp >= now() - interval '24 hours' AND to_address IS NOT NULL
                  GROUP BY to_address
                ), prev_w AS (
                  SELECT to_address AS a, COUNT(*) AS c
                  FROM transactions
                  WHERE timestamp >= now() - interval '48 hours' AND timestamp < now() - interval '24 hours' AND to_address IS NOT NULL
                  GROUP BY to_address
                )
                SELECT n.a, n.c, COALESCE(p.c,0)
                FROM now_w n LEFT JOIN prev_w p ON p.a=n.a
                WHERE n.c >= %s
                ORDER BY (n.c-COALESCE(p.c,0)) DESC
                LIMIT %s
                """,
                (cfg["fan_in_spike"]["min_count"], max(limit, 50)),
            )
            for addr, now_c, prev_c in cur.fetchall():
                baseline = max(1, int(prev_c or 0))
                ratio = float(now_c) / baseline
                delta = int(now_c) - int(prev_c or 0)
                if ratio >= cfg["fan_in_spike"]["min_ratio"] and delta >= cfg["fan_in_spike"]["min_delta"]:
                    alerts.append({
                        "type": "fan_in_spike",
                        "address": addr,
                        "severity": "high" if ratio >= 8 else "medium",
                        "confidence": min(0.99, 0.5 + min(ratio, 10) / 12),
                        "evidence": {"window": "24h_vs_prev24h", "now_inbound": int(now_c), "prev_inbound": int(prev_c or 0), "ratio": round(ratio, 2), "delta": delta},
                    })

        # new_high_centrality_node
        if cfg["new_high_centrality_node"]["enabled"]:
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
                  SELECT a, SUM(out_c) AS out_c, SUM(in_c) AS in_c FROM recent GROUP BY a
                )
                SELECT a, out_c, in_c
                FROM agg
                WHERE (out_c + in_c) >= %s
                ORDER BY (out_c + in_c) DESC
                LIMIT %s
                """,
                (cfg["new_high_centrality_node"]["min_count"], max(limit, 30)),
            )
            for addr, out_c, in_c in cur.fetchall():
                alerts.append({
                    "type": "new_high_centrality_node",
                    "address": addr,
                    "severity": "medium",
                    "confidence": 0.7,
                    "evidence": {"window": "last_24h", "outbound": int(out_c or 0), "inbound": int(in_c or 0), "degree_proxy": int((out_c or 0) + (in_c or 0))},
                })

        # anomalous_bridge_path
        if cfg["anomalous_bridge_path"]["enabled"]:
            cur.execute(
                """
                WITH now_w AS (
                  SELECT CASE WHEN from_address = ANY(%s) THEN to_address ELSE from_address END AS cp, COUNT(*) AS c
                  FROM transactions
                  WHERE timestamp >= now() - interval '24 hours' AND (from_address = ANY(%s) OR to_address = ANY(%s))
                  GROUP BY cp
                ), prev_w AS (
                  SELECT CASE WHEN from_address = ANY(%s) THEN to_address ELSE from_address END AS cp, COUNT(*) AS c
                  FROM transactions
                  WHERE timestamp >= now() - interval '48 hours' AND timestamp < now() - interval '24 hours' AND (from_address = ANY(%s) OR to_address = ANY(%s))
                  GROUP BY cp
                )
                SELECT n.cp, n.c, COALESCE(p.c,0)
                FROM now_w n LEFT JOIN prev_w p ON p.cp=n.cp
                WHERE n.cp IS NOT NULL
                ORDER BY (n.c-COALESCE(p.c,0)) DESC
                LIMIT %s
                """,
                (list(BRIDGES), list(BRIDGES), list(BRIDGES), list(BRIDGES), list(BRIDGES), list(BRIDGES), max(limit, 30)),
            )
            for cp, now_c, prev_c in cur.fetchall():
                baseline = max(1, int(prev_c or 0))
                ratio = float(now_c) / baseline
                delta = int(now_c) - int(prev_c or 0)
                if ratio >= cfg["anomalous_bridge_path"]["min_ratio"] and delta >= cfg["anomalous_bridge_path"]["min_delta"]:
                    alerts.append({
                        "type": "anomalous_bridge_path",
                        "address": cp,
                        "severity": "high" if ratio >= 8 else "medium",
                        "confidence": min(0.99, 0.55 + min(ratio, 10) / 12),
                        "evidence": {"window": "24h_vs_prev24h", "bridge_counterparty_now": int(now_c), "bridge_counterparty_prev": int(prev_c or 0), "ratio": round(ratio, 2), "delta": delta},
                    })

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
    cfg = _load_thresholds()
    candidates = _generate_alert_candidates(limit=max(limit, 50), thresholds=cfg)
    _persist_alerts(candidates, cfg)
    with get_conn() as conn:
        cur = conn.cursor()
        if status:
            cur.execute("SELECT id, type, address, severity, confidence, evidence, status, assignee, ack_at, resolved_at, created_at FROM alerts WHERE status=%s ORDER BY created_at DESC LIMIT %s", (status, limit))
        else:
            cur.execute("SELECT id, type, address, severity, confidence, evidence, status, assignee, ack_at, resolved_at, created_at FROM alerts ORDER BY created_at DESC LIMIT %s", (limit,))
        rows = cur.fetchall()
    return _format_rows(rows)


def alert_queue(limit: int = 20, status: str = "new"):
    _ensure_schema()
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, type, address, severity, confidence, evidence, status, assignee, ack_at, resolved_at, created_at
            FROM alerts
            WHERE status = %s
            ORDER BY CASE severity WHEN 'high' THEN 3 WHEN 'medium' THEN 2 ELSE 1 END DESC,
                     confidence DESC,
                     created_at DESC
            LIMIT %s
            """,
            (status, limit),
        )
        rows = cur.fetchall()
    return _format_rows(rows)


def alerts_for_address(address: str, limit: int = 20, status: Optional[str] = None):
    with get_conn() as conn:
        cur = conn.cursor()
        if status:
            cur.execute("SELECT id, type, address, severity, confidence, evidence, status, assignee, ack_at, resolved_at, created_at FROM alerts WHERE address=%s AND status=%s ORDER BY created_at DESC LIMIT %s", (address.lower(), status, limit))
        else:
            cur.execute("SELECT id, type, address, severity, confidence, evidence, status, assignee, ack_at, resolved_at, created_at FROM alerts WHERE address=%s ORDER BY created_at DESC LIMIT %s", (address.lower(), limit))
        rows = cur.fetchall()
    return _format_rows(rows)


def update_alert_status(alert_id: int, status: str, assignee: Optional[str] = None):
    if status not in {"new", "ack", "resolved"}:
        raise ValueError("invalid status")
    _ensure_schema()
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
    return _format_rows([row])[0] if row else None


def get_thresholds() -> Dict[str, Dict[str, Any]]:
    return _load_thresholds()


def update_threshold(rule_type: str, min_ratio: Optional[float], min_delta: Optional[int], min_count: Optional[int], cooldown_hours: Optional[int], enabled: Optional[bool]):
    _ensure_schema()
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO alert_thresholds(rule_type, min_ratio, min_delta, min_count, cooldown_hours, enabled, updated_at)
            VALUES(%s,%s,%s,%s,%s,%s,now())
            ON CONFLICT (rule_type) DO UPDATE SET
              min_ratio = COALESCE(EXCLUDED.min_ratio, alert_thresholds.min_ratio),
              min_delta = COALESCE(EXCLUDED.min_delta, alert_thresholds.min_delta),
              min_count = COALESCE(EXCLUDED.min_count, alert_thresholds.min_count),
              cooldown_hours = COALESCE(EXCLUDED.cooldown_hours, alert_thresholds.cooldown_hours),
              enabled = COALESCE(EXCLUDED.enabled, alert_thresholds.enabled),
              updated_at = now()
            """,
            (rule_type, min_ratio, min_delta, min_count, cooldown_hours, enabled),
        )
    return get_thresholds().get(rule_type)
