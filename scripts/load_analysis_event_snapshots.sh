#!/usr/bin/env bash
set -euo pipefail

ANALYSIS_DB_URL="${ANALYSIS_DB_URL:-postgresql://postgres:postgres@localhost:5434/stock_radar_analysis}"
SOURCE_DB_URL="${SOURCE_DB_URL:-postgresql://postgres:postgres@localhost:5434/stock_radar}"

START_DATE="${START_DATE:-}"
END_DATE="${END_DATE:-}"

if [[ -z "$START_DATE" || -z "$END_DATE" ]]; then
  echo "Usage:"
  echo "  START_DATE=YYYY-MM-DD END_DATE=YYYY-MM-DD $0"
  exit 1
fi

TMP_CANDIDATES="$(mktemp /tmp/candidate_events_snapshot.XXXXXX.csv)"
TMP_DECISIONS="$(mktemp /tmp/decision_events_snapshot.XXXXXX.csv)"
cleanup() {
  rm -f "$TMP_CANDIDATES" "$TMP_DECISIONS"
}
trap cleanup EXIT

psql "$SOURCE_DB_URL" -v ON_ERROR_STOP=1 -c "\copy (
  SELECT
    id,
    ticker,
    event_ts,
    trigger_name,
    trigger_score,
    trigger_payload,
    last_second_ts,
    last_minute_ts,
    seconds_since_last_trade_bar,
    minutes_since_last_trade_bar,
    is_second_stream_stale,
    is_minute_stream_stale,
    processed_at,
    created_at
  FROM stock_radar.candidate_events
  WHERE event_ts::date BETWEEN DATE '$START_DATE' AND DATE '$END_DATE'
) TO '$TMP_CANDIDATES' WITH (FORMAT csv, HEADER true)"

psql "$SOURCE_DB_URL" -v ON_ERROR_STOP=1 -c "\copy (
  SELECT
    id,
    ticker,
    decision_ts,
    decision_type,
    reason_code,
    decision_payload,
    candidate_score,
    validation_pass_count,
    seconds_since_last_trade_bar,
    minutes_since_last_trade_bar,
    is_second_stream_stale,
    is_minute_stream_stale,
    created_at
  FROM stock_radar.decision_events
  WHERE decision_ts::date BETWEEN DATE '$START_DATE' AND DATE '$END_DATE'
) TO '$TMP_DECISIONS' WITH (FORMAT csv, HEADER true)"

psql "$ANALYSIS_DB_URL" -v ON_ERROR_STOP=1 <<SQL
DELETE FROM public.candidate_events_snapshot
WHERE event_ts::date BETWEEN DATE '$START_DATE' AND DATE '$END_DATE';

\copy public.candidate_events_snapshot (id, ticker, event_ts, trigger_name, trigger_score, trigger_payload, last_second_ts, last_minute_ts, seconds_since_last_trade_bar, minutes_since_last_trade_bar, is_second_stream_stale, is_minute_stream_stale, processed_at, created_at) FROM '$TMP_CANDIDATES' WITH (FORMAT csv, HEADER true)

DELETE FROM public.decision_events_snapshot
WHERE decision_ts::date BETWEEN DATE '$START_DATE' AND DATE '$END_DATE';

\copy public.decision_events_snapshot (id, ticker, decision_ts, decision_type, reason_code, decision_payload, candidate_score, validation_pass_count, seconds_since_last_trade_bar, minutes_since_last_trade_bar, is_second_stream_stale, is_minute_stream_stale, created_at) FROM '$TMP_DECISIONS' WITH (FORMAT csv, HEADER true)
SQL

echo "Loaded event snapshots for $START_DATE through $END_DATE into analysis DB"
