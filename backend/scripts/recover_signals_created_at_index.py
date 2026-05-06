#!/usr/bin/env python3
"""Recover from a cancelled CREATE INDEX CONCURRENTLY on signals.created_at.

If the alembic migration `1a2b3c4d5e6f_signals_created_at_index` is interrupted
mid-build, Postgres leaves the index marked INVALID — it isn't used by the
planner but is still maintained on every write to `signals`. This script
detects that state and drops the invalid index so the migration can be
re-run cleanly.

Usage examples:

  # In-cluster (recommended — runs against the live DB via the app's connection):
  kubectl -n stock-radar-public exec deploy/stock-radar-api -- \
      python backend/scripts/recover_signals_created_at_index.py

  # Force-drop even if the index reports as VALID (rarely needed):
  kubectl -n stock-radar-public exec deploy/stock-radar-api -- \
      python backend/scripts/recover_signals_created_at_index.py --force

After this script reports the index gone and `alembic_version` is the prior
revision (`0f1e2d3c4b5a`), re-run:

  kubectl -n stock-radar-public exec deploy/stock-radar-api -- alembic upgrade head

If `alembic_version` shows `1a2b3c4d5e6f` already, the migration row was
written before cancellation. To re-run the migration, first roll the version
row back manually:

  UPDATE stock_radar.alembic_version SET version_num = '0f1e2d3c4b5a';
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import text

from app.core.database import engine

INDEX_NAME = "ix_stock_radar_signals_created_at"
SCHEMA = "stock_radar"
PREVIOUS_REVISION = "0f1e2d3c4b5a"
TARGET_REVISION = "1a2b3c4d5e6f"


def fetch_index_state() -> tuple[bool, bool] | None:
    """Return (indisvalid, indisready) or None if the index does not exist."""
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT ix.indisvalid, ix.indisready
                  FROM pg_class i
                  JOIN pg_index ix ON ix.indexrelid = i.oid
                  JOIN pg_namespace n ON n.oid = i.relnamespace
                 WHERE n.nspname = :schema AND i.relname = :name
                """
            ),
            {"schema": SCHEMA, "name": INDEX_NAME},
        ).fetchone()
    if row is None:
        return None
    return bool(row[0]), bool(row[1])


def fetch_alembic_version() -> str | None:
    with engine.connect() as conn:
        return conn.execute(
            text(f"SELECT version_num FROM {SCHEMA}.alembic_version")
        ).scalar()


def drop_concurrently() -> None:
    # CREATE/DROP INDEX CONCURRENTLY may not run inside a transaction, so we
    # use an autocommit connection.
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text(f"DROP INDEX CONCURRENTLY IF EXISTS {SCHEMA}.{INDEX_NAME}"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument(
        "--force",
        action="store_true",
        help="Drop the index even if it reports as VALID (use sparingly).",
    )
    args = parser.parse_args()

    state = fetch_index_state()
    if state is None:
        print(f"index {INDEX_NAME!r} does not exist — nothing to drop")
    else:
        is_valid, is_ready = state
        print(f"index {INDEX_NAME!r}: indisvalid={is_valid}, indisready={is_ready}")
        if is_valid and not args.force:
            print("index is VALID — leaving it alone (use --force to override)")
        else:
            label = "INVALID" if not is_valid else "VALID-but-forced"
            print(f"dropping {label} index concurrently…")
            drop_concurrently()
            after = fetch_index_state()
            if after is not None:
                print(f"WARNING: index still present after drop: {after}", file=sys.stderr)
                return 2
            print("dropped")

    version = fetch_alembic_version()
    print(f"alembic_version: {version}")
    if version == PREVIOUS_REVISION:
        print("→ safe to re-run: alembic upgrade head")
    elif version == TARGET_REVISION:
        print(
            "→ migration row already written. To rebuild the index either:\n"
            f"   (a) roll back: UPDATE {SCHEMA}.alembic_version "
            f"SET version_num='{PREVIOUS_REVISION}'; then re-run alembic, or\n"
            "   (b) create the index manually with the SQL from the migration."
        )
    else:
        print(f"→ unexpected alembic version {version!r}; investigate manually.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
