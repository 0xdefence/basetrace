from api.services.db import get_conn
from api.services.label_service import get_labels


def get_entity_profile(address: str):
    addr = address.lower()
    label_bundle = get_labels(addr)

    with get_conn() as conn:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT
              COALESCE(SUM(CASE WHEN from_address = %s THEN value_wei ELSE 0 END),0) AS out_wei,
              COALESCE(SUM(CASE WHEN to_address = %s THEN value_wei ELSE 0 END),0) AS in_wei,
              COALESCE(COUNT(*) FILTER (WHERE from_address = %s),0) AS out_txs,
              COALESCE(COUNT(*) FILTER (WHERE to_address = %s),0) AS in_txs
            FROM transactions
            WHERE timestamp >= now() - interval '7 days'
              AND (from_address = %s OR to_address = %s)
            """,
            (addr, addr, addr, addr, addr, addr),
        )
        out_wei7, in_wei7, out_txs7, in_txs7 = cur.fetchone()

        cur.execute(
            """
            SELECT
              COALESCE(SUM(CASE WHEN from_address = %s THEN value_wei ELSE 0 END),0) AS out_wei,
              COALESCE(SUM(CASE WHEN to_address = %s THEN value_wei ELSE 0 END),0) AS in_wei,
              COALESCE(COUNT(*) FILTER (WHERE from_address = %s),0) AS out_txs,
              COALESCE(COUNT(*) FILTER (WHERE to_address = %s),0) AS in_txs
            FROM transactions
            WHERE timestamp >= now() - interval '30 days'
              AND (from_address = %s OR to_address = %s)
            """,
            (addr, addr, addr, addr, addr, addr),
        )
        out_wei30, in_wei30, out_txs30, in_txs30 = cur.fetchone()

        cur.execute(
            """
            SELECT
              CASE WHEN src_address = %s THEN dst_address ELSE src_address END AS cp,
              SUM(tx_count) AS txs,
              SUM(total_value_wei) AS value_wei
            FROM edges
            WHERE src_address = %s OR dst_address = %s
            GROUP BY cp
            ORDER BY txs DESC
            LIMIT 10
            """,
            (addr, addr, addr),
        )
        top = [
            {"address": cp, "tx_count": int(txs or 0), "total_value_wei": str(v or 0)}
            for cp, txs, v in cur.fetchall()
        ]

    return {
        "address": addr,
        "labels": label_bundle["labels"],
        "features": label_bundle["features"],
        "flow_7d": {
            "outbound_wei": str(out_wei7 or 0),
            "inbound_wei": str(in_wei7 or 0),
            "outbound_txs": int(out_txs7 or 0),
            "inbound_txs": int(in_txs7 or 0),
        },
        "flow_30d": {
            "outbound_wei": str(out_wei30 or 0),
            "inbound_wei": str(in_wei30 or 0),
            "outbound_txs": int(out_txs30 or 0),
            "inbound_txs": int(in_txs30 or 0),
        },
        "top_counterparties": top,
    }
