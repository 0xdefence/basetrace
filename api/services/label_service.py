from api.services.db import get_conn
from labels.rules import label_address


def persist_labels(address: str, labels: list[dict]):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM labels WHERE address = %s", (address.lower(),))
        for lb in labels:
            cur.execute(
                """
                INSERT INTO labels(address, label, confidence, evidence)
                VALUES(%s, %s, %s, %s::jsonb)
                """,
                (address.lower(), lb.get("label"), float(lb.get("confidence", 0)), json_dumps(lb.get("evidence", {}))),
            )


def json_dumps(obj: dict) -> str:
    import json

    return json.dumps(obj or {})


def get_features(address: str) -> dict:
    addr = address.lower()
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT tx_count, contracts_deployed FROM addresses WHERE address = %s",
            (addr,),
        )
        row = cur.fetchone() or (0, 0)

        cur.execute(
            "SELECT COUNT(DISTINCT dst_address) FROM edges WHERE src_address = %s",
            (addr,),
        )
        unique_counterparties = cur.fetchone()[0] or 0

        cur.execute("SELECT COUNT(*) FROM edges WHERE dst_address = %s", (addr,))
        inbound_edges = cur.fetchone()[0] or 0

        cur.execute("SELECT COUNT(*) FROM edges WHERE src_address = %s", (addr,))
        outbound_edges = cur.fetchone()[0] or 0

    return {
        "tx_count": row[0] or 0,
        "contracts_deployed": row[1] or 0,
        "unique_counterparties": unique_counterparties,
        "inbound_edges": inbound_edges,
        "outbound_edges": outbound_edges,
    }


def get_labels(address: str):
    addr = address.lower()
    features = get_features(addr)
    labels = label_address(addr, features)
    persist_labels(addr, labels)
    return {"address": addr, "features": features, "labels": labels}
