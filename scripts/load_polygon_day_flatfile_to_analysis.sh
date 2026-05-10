#!/usr/bin/env bash
set -euo pipefail

DB_NAME="${DB_NAME:-stock_radar_analysis}"
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5434}"
PGUSER="${PGUSER:-postgres}"
PGPASSWORD="${PGPASSWORD:-postgres}"

TRADE_DATE="${TRADE_DATE:-}"
CSV_GZ_PATH="${CSV_GZ_PATH:-}"

if [[ -z "$TRADE_DATE" || -z "$CSV_GZ_PATH" ]]; then
  echo "Usage:"
  echo "  TRADE_DATE=YYYY-MM-DD CSV_GZ_PATH=/path/file.csv.gz $0"
  exit 1
fi

if [[ ! -f "$CSV_GZ_PATH" ]]; then
  echo "File not found: $CSV_GZ_PATH"
  exit 1
fi

TMP_CSV="$(mktemp /tmp/polygon_day_flatfile.XXXXXX.csv)"
cleanup() {
  rm -f "$TMP_CSV"
}
trap cleanup EXIT

gzip -dc "$CSV_GZ_PATH" > "$TMP_CSV"

export PGPASSWORD
psql -v ON_ERROR_STOP=1 \
  -h "$PGHOST" \
  -p "$PGPORT" \
  -U "$PGUSER" \
  -d "$DB_NAME" <<SQL
CREATE TEMP TABLE tmp_polygon_day_flatfile_import (
    ticker text,
    volume numeric(24, 6),
    open numeric(18, 6),
    close numeric(18, 6),
    high numeric(18, 6),
    low numeric(18, 6),
    window_start bigint,
    transactions bigint
);
\copy tmp_polygon_day_flatfile_import (ticker, volume, open, close, high, low, window_start, transactions) FROM '$TMP_CSV' WITH (FORMAT csv, HEADER true)
INSERT INTO public.polygon_day_flatfile_stage (
    trade_date,
    ticker,
    open,
    high,
    low,
    close,
    volume,
    transactions
)
SELECT
    DATE '$TRADE_DATE',
    ticker,
    open,
    high,
    low,
    close,
    ROUND(volume)::bigint,
    transactions
FROM tmp_polygon_day_flatfile_import
ON CONFLICT (trade_date, ticker) DO UPDATE
SET
    open = EXCLUDED.open,
    high = EXCLUDED.high,
    low = EXCLUDED.low,
    close = EXCLUDED.close,
    volume = EXCLUDED.volume,
    transactions = EXCLUDED.transactions;
SQL

echo "Loaded $TRADE_DATE into public.polygon_day_flatfile_stage in $DB_NAME"
