from api.services.db import get_conn


def get_cluster(address: str, limit: int = 200):
    addr = address.lower()

    with get_conn() as conn:
        cur = conn.cursor()

        # 1-hop
        cur.execute(
            """
            SELECT DISTINCT CASE WHEN src_address = %s THEN dst_address ELSE src_address END AS n
            FROM edges
            WHERE src_address = %s OR dst_address = %s
            LIMIT %s
            """,
            (addr, addr, addr, limit),
        )
        hop1 = [r[0] for r in cur.fetchall() if r[0]]

        # 2-hop from hop1 set
        hop2 = set()
        if hop1:
            cur.execute(
                """
                SELECT DISTINCT CASE WHEN src_address = ANY(%s) THEN dst_address ELSE src_address END AS n
                FROM edges
                WHERE src_address = ANY(%s) OR dst_address = ANY(%s)
                LIMIT %s
                """,
                (hop1, hop1, hop1, limit),
            )
            hop2 = {r[0] for r in cur.fetchall() if r[0]}

    nodes = {addr, *hop1, *hop2}
    return {
        "center": addr,
        "hop1_count": len(set(hop1)),
        "hop2_count": len(hop2),
        "nodes": [{"id": n} for n in sorted(nodes)],
    }
