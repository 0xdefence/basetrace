"""Base chain ingestion worker v1.

- Pulls blocks/txs from Base RPC
- Persists txs, address stats, and edge aggregates
- Extracts ERC20 Transfer logs per block (chunk-ready)
- Supports RPC fallback + retry/backoff
"""

import os
import time
from datetime import datetime, timezone

import httpx
import psycopg2
from dotenv import load_dotenv

TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55aebf8a5b84"  # ERC20 Transfer


def h2i(x: str) -> int:
    if x is None:
        return 0
    if isinstance(x, int):
        return x
    return int(x, 16)


def rpc_call(client: httpx.Client, rpc_urls: list[str], method: str, params: list, retries: int = 3):
    last_err = None
    for rpc_url in rpc_urls:
        for attempt in range(retries):
            try:
                payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
                r = client.post(rpc_url, json=payload, timeout=30)
                r.raise_for_status()
                data = r.json()
                if "error" in data:
                    raise RuntimeError(f"RPC {method} error: {data['error']}")
                return data.get("result"), rpc_url, attempt
            except Exception as e:
                last_err = e
                time.sleep(min(5, 0.6 * (2**attempt)))
    raise RuntimeError(f"RPC {method} failed across providers: {last_err}")


def ensure_state(conn):
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS ingest_state (
          key TEXT PRIMARY KEY,
          value TEXT,
          updated_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )
    conn.commit()


def get_last_block(conn) -> int:
    cur = conn.cursor()
    cur.execute("SELECT value FROM ingest_state WHERE key='last_block'")
    row = cur.fetchone()
    return int(row[0]) if row and row[0] else -1


def set_state(conn, key: str, value: str):
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO ingest_state(key, value, updated_at)
        VALUES(%s, %s, now())
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()
        """,
        (key, value),
    )


def set_last_block(conn, block_number: int):
    set_state(conn, "last_block", str(block_number))


def upsert_address(cur, address: str, block_number: int, tx_inc: int = 0, deploy_inc: int = 0):
    if not address:
        return
    a = address.lower()
    cur.execute(
        """
        INSERT INTO addresses(address, first_seen_block, last_seen_block, tx_count, contracts_deployed)
        VALUES(%s, %s, %s, %s, %s)
        ON CONFLICT (address) DO UPDATE SET
          last_seen_block = GREATEST(addresses.last_seen_block, EXCLUDED.last_seen_block),
          tx_count = addresses.tx_count + EXCLUDED.tx_count,
          contracts_deployed = addresses.contracts_deployed + EXCLUDED.contracts_deployed,
          updated_at = now()
        """,
        (a, block_number, block_number, tx_inc, deploy_inc),
    )


def ingest_block(conn, client, rpc_urls: list[str], block_number: int):
    block_hex = hex(block_number)
    block, rpc_used, rpc_attempt = rpc_call(client, rpc_urls, "eth_getBlockByNumber", [block_hex, True])
    if not block:
        return 0, 0

    ts = datetime.fromtimestamp(h2i(block.get("timestamp", "0x0")), tz=timezone.utc)
    txs = block.get("transactions", [])

    cur = conn.cursor()
    tx_count = 0

    for tx in txs:
        tx_hash = tx.get("hash")
        from_a = (tx.get("from") or "").lower() or None
        to_a = (tx.get("to") or "").lower() or None
        value = h2i(tx.get("value", "0x0"))
        deploy_inc = 1 if to_a is None else 0

        cur.execute(
            """
            INSERT INTO transactions(tx_hash, block_number, from_address, to_address, value_wei, success, timestamp)
            VALUES(%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (tx_hash) DO NOTHING
            """,
            (tx_hash, block_number, from_a, to_a, value, True, ts),
        )

        upsert_address(cur, from_a, block_number, tx_inc=1, deploy_inc=0)
        if to_a:
            upsert_address(cur, to_a, block_number, tx_inc=0, deploy_inc=0)
        if from_a and deploy_inc:
            upsert_address(cur, from_a, block_number, tx_inc=0, deploy_inc=1)

        if from_a and to_a:
            cur.execute(
                """
                INSERT INTO edges(src_address, dst_address, tx_count, total_value_wei, window_start, window_end)
                VALUES(%s, %s, 1, %s, %s, %s)
                """,
                (from_a, to_a, value, ts, ts),
            )

        tx_count += 1

    # Pull Transfer logs for this block (chunk-ready shape)
    logs, rpc_used_logs, rpc_attempt_logs = rpc_call(
        client,
        rpc_urls,
        "eth_getLogs",
        [{"fromBlock": block_hex, "toBlock": block_hex, "topics": [TRANSFER_TOPIC]}],
    ) or ([], rpc_used, rpc_attempt)

    transfer_count = 0
    for lg in logs:
        topics = lg.get("topics") or []
        if len(topics) < 3:
            continue
        token = (lg.get("address") or "").lower()
        from_addr = "0x" + topics[1][-40:]
        to_addr = "0x" + topics[2][-40:]
        amount = h2i(lg.get("data", "0x0"))
        tx_hash = lg.get("transactionHash")

        cur.execute(
            """
            INSERT INTO token_transfers(tx_hash, token_address, from_address, to_address, amount, block_number, timestamp)
            VALUES(%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (tx_hash, token, from_addr.lower(), to_addr.lower(), amount, block_number, ts),
        )
        transfer_count += 1

    set_last_block(conn, block_number)
    set_state(conn, "current_rpc", rpc_used)
    set_state(conn, "last_rpc_attempt", str(rpc_attempt))
    set_state(conn, "last_logs_rpc", rpc_used_logs)
    set_state(conn, "last_logs_rpc_attempt", str(rpc_attempt_logs))
    set_state(conn, "last_error", "")
    conn.commit()
    return tx_count, transfer_count


def run_ingest_loop():
    load_dotenv()

    primary = os.getenv("BASE_RPC_URL", "https://mainnet.base.org")
    fallback = os.getenv("BASE_RPC_FALLBACKS", "")
    rpc_urls = [primary] + [u.strip() for u in fallback.split(",") if u.strip()]

    dsn = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/basetrace")
    confirmations = int(os.getenv("INGEST_CONFIRMATIONS", "3"))
    start_block_env = int(os.getenv("INGEST_START_BLOCK", "0"))

    conn = psycopg2.connect(dsn)
    ensure_state(conn)

    with httpx.Client() as client:
        while True:
            try:
                head_hex, head_rpc, head_attempt = rpc_call(client, rpc_urls, "eth_blockNumber", [])
                head = h2i(head_hex)
                safe_head = max(0, head - confirmations)
                last = get_last_block(conn)
                nxt = max(start_block_env, last + 1)

                set_state(conn, "head_rpc", head_rpc)
                set_state(conn, "head_rpc_attempt", str(head_attempt))

                if nxt > safe_head:
                    print(f"[ingest] up-to-date last={last} safe_head={safe_head}")
                    conn.commit()
                    time.sleep(5)
                    continue

                txc, trc = ingest_block(conn, client, rpc_urls, nxt)
                print(f"[ingest] block={nxt} tx={txc} transfers={trc}")
            except Exception as e:
                set_state(conn, "last_error", str(e)[:800])
                conn.commit()
                print(f"[ingest] error: {e}")
                time.sleep(3)


if __name__ == "__main__":
    run_ingest_loop()
