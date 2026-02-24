from api.services.db import get_conn
from labels.rules import label_address


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
    features = get_features(address)
    labels = label_address(address, features)
    return {"address": address.lower(), "features": features, "labels": labels}
