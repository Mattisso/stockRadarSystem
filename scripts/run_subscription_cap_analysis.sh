#!/usr/bin/env bash
set -euo pipefail

export ANALYSIS_DB_URL="${ANALYSIS_DB_URL:-postgresql://postgres:postgres@localhost:5434/stock_radar_analysis}"
export SOURCE_DB_URL="${SOURCE_DB_URL:-postgresql://postgres:postgres@localhost:5434/stock_radar}"

TRADE_DATE="${TRADE_DATE:-}"
NEXT_TRADE_DATE="${NEXT_TRADE_DATE:-}"
CSV_GZ_PATH="${CSV_GZ_PATH:-}"
MIN_PRICE="${MIN_PRICE:-0.50}"
MAX_PRICE="${MAX_PRICE:-10.00}"
MIN_AVG_VOLUME="${MIN_AVG_VOLUME:-500000}"

if [[ -z "$TRADE_DATE" || -z "$NEXT_TRADE_DATE" || -z "$CSV_GZ_PATH" ]]; then
  echo "Usage:"
  echo "  TRADE_DATE=YYYY-MM-DD NEXT_TRADE_DATE=YYYY-MM-DD CSV_GZ_PATH=/path/file.csv.gz $0"
  exit 1
fi

TMP_SQL="$(mktemp /tmp/subscription_cap_analysis.XXXXXX.sql)"
cleanup_sql() {
  rm -f "$TMP_SQL"
}
trap cleanup_sql EXIT

scripts/load_polygon_day_flatfile_to_analysis.sh
START_DATE="$NEXT_TRADE_DATE" END_DATE="$NEXT_TRADE_DATE" scripts/load_analysis_event_snapshots.sh

sed \
  -e "s/__PRIOR_TRADE_DATE__/$TRADE_DATE/g" \
  -e "s/__NEXT_TRADE_DATE__/$NEXT_TRADE_DATE/g" \
  -e "s/__MIN_PRICE__/$MIN_PRICE/g" \
  -e "s/__MAX_PRICE__/$MAX_PRICE/g" \
  -e "s/__MIN_AVG_VOLUME__/$MIN_AVG_VOLUME/g" \
  sql/subscription_cap_analysis_queries.sql > "$TMP_SQL"

psql "$ANALYSIS_DB_URL" -f "$TMP_SQL"
