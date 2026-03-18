"""Backfill script: link trades to originating signals, then populate outcome_pnl."""

import psycopg2

CONN_PARAMS = {
    "host": "localhost",
    "port": 5434,
    "user": "postgres",
    "password": "postgres",
    "dbname": "stock_radar",
}
SCHEMA = "stock_radar"
MATCH_WINDOW_SECONDS = 30


def main():
    conn = psycopg2.connect(**CONN_PARAMS)
    conn.autocommit = False
    cur = conn.cursor()

    # Step 1: Link trades to signals
    print("=== Step 1: Link trades to matching signals ===\n")

    cur.execute(f"""
        SELECT id, ticker, signal_score, entry_time, created_at
        FROM {SCHEMA}.trades
        WHERE signal_id IS NULL
        ORDER BY id
    """)
    unlinked_trades = cur.fetchall()
    print(f"Found {len(unlinked_trades)} trade(s) with signal_id IS NULL.\n")

    linked = 0
    skipped = 0

    for trade_id, ticker, signal_score, entry_time, created_at in unlinked_trades:
        ref_time = entry_time or created_at
        if ref_time is None:
            skipped += 1
            continue

        cur.execute(f"""
            SELECT id, created_at
            FROM {SCHEMA}.signals
            WHERE ticker = %s
              AND score = %s
              AND signal_type = 'BREAKOUT'
              AND created_at <= %s
              AND created_at >= %s - INTERVAL '{MATCH_WINDOW_SECONDS} seconds'
            ORDER BY created_at DESC
            LIMIT 1
        """, (ticker, signal_score, ref_time, ref_time))

        row = cur.fetchone()
        if row:
            signal_id, signal_created = row
            print(f"  Trade {trade_id} ({ticker}, score={signal_score}) -> Signal {signal_id}")
            cur.execute(f"UPDATE {SCHEMA}.trades SET signal_id = %s WHERE id = %s",
                        (signal_id, trade_id))
            linked += 1
        else:
            skipped += 1

    print(f"\nLinked: {linked}  |  Skipped: {skipped}\n")

    # Step 2: Backfill outcome_pnl
    print("=== Step 2: Backfill outcome_pnl on linked signals ===\n")

    cur.execute(f"""
        UPDATE {SCHEMA}.signals s
        SET outcome_pnl = t.pnl
        FROM {SCHEMA}.trades t
        WHERE t.signal_id = s.id
          AND t.pnl IS NOT NULL
          AND (s.outcome_pnl IS NULL OR s.outcome_pnl != t.pnl)
    """)
    print(f"Updated outcome_pnl on {cur.rowcount} signal(s).\n")

    # Step 3: Mark acted_on
    print("=== Step 3: Mark acted_on = true for linked signals ===\n")

    cur.execute(f"""
        UPDATE {SCHEMA}.signals s
        SET acted_on = true
        FROM {SCHEMA}.trades t
        WHERE t.signal_id = s.id
          AND s.acted_on = false
    """)
    print(f"Set acted_on = true on {cur.rowcount} signal(s).\n")

    conn.commit()
    cur.close()
    conn.close()
    print("=== Done. All changes committed. ===")


if __name__ == "__main__":
    main()
