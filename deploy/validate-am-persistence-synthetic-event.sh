#!/bin/bash
# End-to-end synthetic AM event test for the AM/A persistence fix.
#
# Steps 1-5 of validate-am-persistence-fix.sh are already passing for the
# 5cdf7975cc-* pod (scheduler alive, blocking job disabled). This script runs
# only the remaining end-to-end check: inject a synthetic AM event into the
# prod Redis Stream and verify it lands in stock_radar.minute_aggregates_live.
#
# Uses a hardcoded market-hours event_ts (2026-04-10T14:30:00+00:00 = 10:30 ET
# Friday) so the persistence worker's line-127 filter accepts the event even
# though the market is closed when this runs.

set -uo pipefail
NS=stock-radar-public
PG_HOST=192.168.1.77
PG_PORT=5434
PG_USER=postgres
PG_PASS=postgres
PG_DB=stock_radar
TICKER=TEST_VALIDATION

echo "=== Step 1: XADD synthetic AM event into Redis Stream ==="
# Use TODAY's date with a market-hours time-of-day. is_regular_us_market_time only
# checks the time-of-day in NY tz, so 14:30 UTC = 10:30 ET passes even outside hours.
# Today's date avoids the retention purge that deletes rows older than retention_hours.
TODAY=$(date -u +"%Y-%m-%d")
EVENT_TS="${TODAY}T14:30:00+00:00"
TS_NOW=$(date -u +"%Y-%m-%dT%H:%M:%S+00:00")
MSG_ID=$(kubectl -n $NS exec deploy/stock-radar-redis -- redis-cli XADD stockradar:polygon:aggregate '*' \
  ticker $TICKER \
  event_type AM \
  event_ts "$EVENT_TS" \
  received_at "$TS_NOW" \
  subscription_generation_id 1 \
  open 1.00 high 1.10 low 0.99 close 1.05 \
  volume 100 vwap 1.05 transactions 1)
echo "XADD message id: $MSG_ID (event_ts=$EVENT_TS)"

echo
echo "=== Step 2: Wait 3s for persistence worker to consume ==="
sleep 3

echo
echo "=== Step 3: Query minute_aggregates_live for the synthetic row ==="
RESULT=$(PGPASSWORD=$PG_PASS psql -h $PG_HOST -p $PG_PORT -U $PG_USER -d $PG_DB -tAc "
  SELECT ticker || '|' || minute_ts || '|' || close
    FROM stock_radar.minute_aggregates_live
   WHERE ticker = '$TICKER';")
echo "Result: ${RESULT:-<empty>}"

if [[ -n "$RESULT" ]]; then
  echo "PASS: end-to-end pipeline is healthy (Redis -> worker -> minute_aggregates_live)"
else
  echo "FAIL: synthetic event did not land in minute_aggregates_live"
  echo "  - Check: kubectl -n $NS logs deploy/stock-radar-polygon-ingest-worker --since=2m | grep -E 'aggregate_persistence_batch_committed|aggregate_persistence_batch_failed'"
  exit 1
fi

echo
echo "=== Step 4: Cleanup ==="
PGPASSWORD=$PG_PASS psql -h $PG_HOST -p $PG_PORT -U $PG_USER -d $PG_DB -c "
  DELETE FROM stock_radar.minute_aggregates_live WHERE ticker = '$TICKER';
  DELETE FROM stock_radar.polygon_minute_aggregates WHERE ticker = '$TICKER';"

echo
echo "=== DONE ==="
echo "Tomorrow at 13:30 UTC (09:30 ET), the same path should fire with real Polygon AM/A data."
echo "Spot-check with:"
echo "  kubectl -n $NS logs deploy/stock-radar-polygon-ingest-worker --since=5m | grep -E 'polygon\\.subscriptions_resumed|polygon\\.aggregate_events_published'"
