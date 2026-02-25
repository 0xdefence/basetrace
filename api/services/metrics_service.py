import os

import httpx

from api.services.db import get_conn


def _rpc_head_block() -> int | None:
    rpc_url = os.getenv("BASE_RPC_URL", "https://mainnet.base.org")
    payload = {"jsonrpc": "2.0", "id": 1, "method": "eth_blockNumber", "params": []}
    try:
        with httpx.Client(timeout=10) as client:
            r = client.post(rpc_url, json=payload)
            r.raise_for_status()
            data = r.json()
            return int(data.get("result", "0x0"), 16)
    except Exception:
        return None


def get_metrics():
    chain_head = _rpc_head_block()

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT value FROM ingest_state WHERE key='last_block'")
        row = cur.fetchone()
        ingested = int(row[0]) if row and row[0] else None

        cur.execute(
            """
            SELECT COUNT(*)
            FROM transactions
            WHERE timestamp >= now() - interval '24 hours'
            """
        )
        tx_24h = int(cur.fetchone()[0] or 0)

        cur.execute(
            """
            SELECT COUNT(*)
            FROM token_transfers
            WHERE timestamp >= now() - interval '24 hours'
            """
        )
        transfers_24h = int(cur.fetchone()[0] or 0)

        cur.execute(
            """
            SELECT COUNT(*)
            FROM alerts
            WHERE created_at >= now() - interval '24 hours'
            """
        )
        alerts_24h = int(cur.fetchone()[0] or 0)

    lag = None
    if chain_head is not None and ingested is not None:
        lag = max(0, chain_head - ingested)

    return {
        "chain_head_block": chain_head,
        "ingested_block": ingested,
        "ingest_lag_blocks": lag,
        "tx_24h": tx_24h,
        "transfers_24h": transfers_24h,
        "alerts_24h": alerts_24h,
    }
