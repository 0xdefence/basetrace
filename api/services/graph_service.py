from api.services.db import get_conn


def get_global_graph(limit: int = 80):
    """Return the top N most-active addresses and all edges between them."""
    with get_conn() as conn:
        cur = conn.cursor()
        # Find the most active addresses by total weighted degree
        cur.execute(
            """
            SELECT address
            FROM (
                SELECT src_address AS address, SUM(tx_count) AS w FROM edges GROUP BY src_address
                UNION ALL
                SELECT dst_address, SUM(tx_count) FROM edges GROUP BY dst_address
            ) t
            GROUP BY address
            ORDER BY SUM(w) DESC
            LIMIT %s
            """,
            (limit,),
        )
        top_addrs = [r[0] for r in cur.fetchall()]
        if not top_addrs:
            return {"nodes": [], "edges": []}

        placeholders = ",".join(["%s"] * len(top_addrs))
        cur.execute(
            f"""
            SELECT src_address, dst_address,
                   SUM(tx_count) AS tx_count,
                   SUM(total_value_wei) AS total_value_wei
            FROM edges
            WHERE src_address IN ({placeholders}) AND dst_address IN ({placeholders})
            GROUP BY src_address, dst_address
            ORDER BY tx_count DESC
            LIMIT 400
            """,
            top_addrs + top_addrs,
        )
        rows = cur.fetchall()

    nodes_seen: set = set()
    edges = []
    for s, d, c, v in rows:
        nodes_seen.add(s)
        nodes_seen.add(d)
        edges.append({"src": s, "dst": d, "tx_count": int(c or 0), "total_value_wei": str(v or 0)})

    return {"nodes": [{"id": n} for n in sorted(nodes_seen)], "edges": edges}


def get_neighbors(address: str, limit: int = 25):
    addr = address.lower()
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT src_address, dst_address,
                   SUM(tx_count) AS tx_count,
                   SUM(total_value_wei) AS total_value_wei
            FROM edges
            WHERE src_address = %s OR dst_address = %s
            GROUP BY src_address, dst_address
            ORDER BY SUM(tx_count) DESC
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
