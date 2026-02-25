from api.services.db import get_conn


def search_entities(query: str, limit: int = 20):
    q = (query or "").strip().lower()
    if not q:
        return []

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT DISTINCT a.address,
                   a.tx_count,
                   a.contracts_deployed,
                   COALESCE(l.label, '') as top_label,
                   COALESCE(l.confidence, 0) as top_confidence
            FROM addresses a
            LEFT JOIN LATERAL (
              SELECT label, confidence
              FROM labels
              WHERE address = a.address
              ORDER BY confidence DESC
              LIMIT 1
            ) l ON true
            WHERE a.address LIKE %s
               OR EXISTS (
                 SELECT 1 FROM labels x
                 WHERE x.address = a.address AND x.label LIKE %s
               )
            ORDER BY a.tx_count DESC
            LIMIT %s
            """,
            (f"%{q}%", f"%{q}%", limit),
        )
        rows = cur.fetchall()

    return [
        {
            "address": addr,
            "tx_count": int(tx or 0),
            "contracts_deployed": int(cd or 0),
            "top_label": lbl,
            "top_confidence": float(conf or 0),
        }
        for addr, tx, cd, lbl, conf in rows
    ]
