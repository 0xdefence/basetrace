"""Base chain ingestion worker.

Features:
- block/tx ingestion
- adaptive eth_getLogs chunking for ERC20 Transfer backfills
- dead-letter tracking in ingest_failures
- replay mode for failed ranges
"""

import os
import time
from datetime import datetime, timezone

import httpx
import psycopg2
from dotenv import load_dotenv

TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55aebf8a5b84"


def h2i(x):
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
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS ingest_failures (
          id BIGSERIAL PRIMARY KEY,
          stage TEXT NOT NULL,
          start_block BIGINT,
          end_block BIGINT,
          error TEXT,
          retry_count INT DEFAULT 0,
          status TEXT DEFAULT 'open',
          created_at TIMESTAMPTZ DEFAULT now(),
          updated_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )
    conn.commit()


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


def get_state_int(conn, key: str, default: int = -1) -> int:
    cur = conn.cursor()
    cur.execute("SELECT value FROM ingest_state WHERE key=%s", (key,))
    row = cur.fetchone()
    return int(row[0]) if row and row[0] else default


def add_failure(conn, stage: str, start_block: int, end_block: int, error: str):
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO ingest_failures(stage, start_block, end_block, error, status, updated_at)
        VALUES(%s,%s,%s,%s,'open',now())
        """,
        (stage, start_block, end_block, error[:1000]),
    )


def mark_failure_resolved(conn, failure_id: int):
    cur = conn.cursor()
    cur.execute(
        "UPDATE ingest_failures SET status='resolved', updated_at=now() WHERE id=%s",
        (failure_id,),
    )


def bump_failure_retry(conn, failure_id: int, error: str):
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE ingest_failures
        SET retry_count = retry_count + 1, error=%s, updated_at=now()
        WHERE id=%s
        """,
        (error[:1000], failure_id),
    )


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


def ingest_block_txs(conn, client, rpc_urls: list[str], block_number: int):
    block_hex = hex(block_number)
    block, rpc_used, rpc_attempt = rpc_call(client, rpc_urls, "eth_getBlockByNumber", [block_hex, True])
    if not block:
        return 0

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

    set_state(conn, "current_rpc", rpc_used)
    set_state(conn, "last_rpc_attempt", str(rpc_attempt))
    return tx_count


def _insert_logs(conn, logs: list):
    cur = conn.cursor()
    n = 0
    for lg in logs:
        topics = lg.get("topics") or []
        if len(topics) < 3:
            continue
        token = (lg.get("address") or "").lower()
        from_addr = "0x" + topics[1][-40:]
        to_addr = "0x" + topics[2][-40:]
        amount = h2i(lg.get("data", "0x0"))
        tx_hash = lg.get("transactionHash")
        block_number = h2i(lg.get("blockNumber", "0x0"))
        ts = datetime.now(timezone.utc)

        cur.execute(
            """
            INSERT INTO token_transfers(tx_hash, token_address, from_address, to_address, amount, block_number, timestamp)
            VALUES(%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (tx_hash, token, from_addr.lower(), to_addr.lower(), amount, block_number, ts),
        )
        n += 1
    return n


def fetch_logs_adaptive(conn, client, rpc_urls: list[str], start_block: int, end_block: int, min_chunk: int = 1):
    """Adaptive range chunking for eth_getLogs backfills."""
    total = 0
    stack = [(start_block, end_block)]

    while stack:
        s, e = stack.pop()
        if s > e:
            continue
        try:
            result, rpc_used, rpc_attempt = rpc_call(
                client,
                rpc_urls,
                "eth_getLogs",
                [{
                    "fromBlock": hex(s),
                    "toBlock": hex(e),
                    "topics": [TRANSFER_TOPIC],
                }],
            )
            logs = result or []
            total += _insert_logs(conn, logs)
            set_state(conn, "last_logs_rpc", rpc_used)
            set_state(conn, "last_logs_rpc_attempt", str(rpc_attempt))
            set_state(conn, "last_error", "")
        except Exception as ex:
            if s == e or (e - s + 1) <= min_chunk:
                add_failure(conn, "logs", s, e, str(ex))
            else:
                mid = (s + e) // 2
                stack.append((s, mid))
                stack.append((mid + 1, e))
    return total


def replay_failures(conn, client, rpc_urls: list[str], max_rows: int = 25):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, stage, start_block, end_block, retry_count
        FROM ingest_failures
        WHERE status='open'
        ORDER BY created_at ASC
        LIMIT %s
        """,
        (max_rows,),
    )
    rows = cur.fetchall()
    resolved = 0
    for fid, stage, s, e, _ in rows:
        try:
            if stage == "logs":
                fetch_logs_adaptive(conn, client, rpc_urls, int(s), int(e))
                mark_failure_resolved(conn, int(fid))
                resolved += 1
            else:
                mark_failure_resolved(conn, int(fid))
        except Exception as ex:
            bump_failure_retry(conn, int(fid), str(ex))
    return resolved, len(rows)


def run_ingest_loop():
    load_dotenv()

    primary = os.getenv("BASE_RPC_URL", "https://mainnet.base.org")
    fallback = os.getenv("BASE_RPC_FALLBACKS", "")
    rpc_urls = [primary] + [u.strip() for u in fallback.split(",") if u.strip()]

    dsn = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/basetrace")
    confirmations = int(os.getenv("INGEST_CONFIRMATIONS", "3"))
    start_block_env = int(os.getenv("INGEST_START_BLOCK", "0"))
    log_chunk = int(os.getenv("INGEST_LOG_CHUNK", "200"))
    replay_mode = os.getenv("INGEST_REPLAY_MODE", "0") == "1"

    conn = psycopg2.connect(dsn)
    ensure_state(conn)

    with httpx.Client() as client:
        while True:
            try:
                head_hex, head_rpc, head_attempt = rpc_call(client, rpc_urls, "eth_blockNumber", [])
                head = h2i(head_hex)
                safe_head = max(0, head - confirmations)

                # tx stream pointer
                last = get_state_int(conn, "last_block", -1)
                nxt = max(start_block_env, last + 1)

                # logs pointer (separate for chunked backfill)
                last_logs = get_state_int(conn, "last_logs_block", start_block_env - 1)
                logs_next = max(start_block_env, last_logs + 1)

                set_state(conn, "head_rpc", head_rpc)
                set_state(conn, "head_rpc_attempt", str(head_attempt))

                if replay_mode:
                    res, scanned = replay_failures(conn, client, rpc_urls)
                    conn.commit()
                    print(f"[replay] resolved={res}/{scanned}")
                    time.sleep(5)
                    continue

                if nxt <= safe_head:
                    txc = ingest_block_txs(conn, client, rpc_urls, nxt)
                    set_state(conn, "last_block", str(nxt))
                    conn.commit()
                    print(f"[ingest] tx block={nxt} tx={txc}")

                if logs_next <= safe_head:
                    end = min(safe_head, logs_next + log_chunk - 1)
                    trc = fetch_logs_adaptive(conn, client, rpc_urls, logs_next, end)
                    set_state(conn, "last_logs_block", str(end))
                    conn.commit()
                    print(f"[ingest] logs {logs_next}-{end} transfers={trc}")

                if nxt > safe_head and logs_next > safe_head:
                    print(f"[ingest] up-to-date last_tx={last} last_logs={last_logs} safe_head={safe_head}")
                    time.sleep(4)

            except Exception as e:
                set_state(conn, "last_error", str(e)[:800])
                conn.commit()
                print(f"[ingest] error: {e}")
                time.sleep(3)


if __name__ == "__main__":
    run_ingest_loop()
