from api.services.db import get_conn


def get_neighbors(address: str, limit: int = 25):
    addr = address.lower()
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT src_address, dst_address, tx_count, total_value_wei
            FROM edges
            WHERE src_address = %s OR dst_address = %s
            ORDER BY tx_count DESC
            LIMIT %s
            """,
            (addr, addr, limit),
        )
        rows = cur.fetchall()

    nodes = set([addr])
    edges = []
    for s, d, c, v in rows:
        nodes.add(s)
        nodes.add(d)
        edges.append({"src": s, "dst": d, "tx_count": int(c or 0), "total_value_wei": str(v or 0)})

    return {"nodes": [{"id": n} for n in sorted(nodes)], "edges": edges}
