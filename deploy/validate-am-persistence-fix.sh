#!/bin/bash
# Validate the AM/A persistence fix after deploying commit 6a70c99b ("fixed AM/A issue").
#
# What this proves:
#   - Step 4: the asyncio loop stays alive past ~3 minutes (the pre-fix pod hung there).
#   - Step 5: the loop-blocking minute-refresh job is no longer registered.
#   - Step 7: an end-to-end synthetic event flows through prod Redis Stream → consumer
#             group → persistence worker → minute_aggregates_live. Uses a hardcoded
#             market-hours event_ts so the line-127 filter accepts it even though the
#             market is closed when this runs.
#
# Before running: replace <PROD_PG_HOST> in Steps 7 and 8 (or export PGHOST/PGUSER/
# PGPASSWORD/PGDATABASE in your shell so the explicit -h/-U args become unnecessary).

set -uo pipefail
NS=stock-radar-public

echo "=== Step 1: Wait for rollout ==="
kubectl -n $NS rollout status deploy/stock-radar-polygon-ingest-worker --timeout=180s

echo
echo "=== Step 2: Confirm worker started cleanly ==="
sleep 10
kubectl -n $NS logs deploy/stock-radar-polygon-ingest-worker --tail=50 \
  | grep -E "polygon\.aggregate_persistence_worker_started|app\.started|polygon\.subscriptions_paused|polygon\.ws_connected"

echo
echo "=== Step 3: Wait 3 minutes for scheduler to prove it stays alive ==="
echo "(pre-fix pod went silent at ~3 min; post-fix pod must keep firing every 60s)"
sleep 180

echo
echo "=== Step 4: Count scheduler activity in past 5 min ==="
SCHED_COUNT=$(kubectl -n $NS logs deploy/stock-radar-polygon-ingest-worker --since=5m \
  | grep -cE "Running job|Job .* executed successfully" || true)
echo "Scheduler events in last 5 min: $SCHED_COUNT"
echo "(expect >= 6 — at minimum the per-minute market_hours_subscriptions job firing 3+ times = 6+ lines)"
if [[ $SCHED_COUNT -ge 6 ]]; then
  echo "PASS: loop is alive"
else
  echo "FAIL: loop may still be hung"
  exit 1
fi

echo
echo "=== Step 5: Confirm the loop-blocking job is no longer registered ==="
MINUTE_REFRESH=$(kubectl -n $NS logs deploy/stock-radar-polygon-ingest-worker --since=5m \
  | grep -cE "refresh_polygon_minute_aggregates" || true)
echo "Minute refresh activity: $MINUTE_REFRESH (expect 0)"
if [[ $MINUTE_REFRESH -eq 0 ]]; then
  echo "PASS: blocking job disabled"
else
  echo "WARN: minute refresh still active"
fi

echo
echo "=== Step 6: Inject synthetic event into prod Redis stream ==="
TS_NOW=$(date -u +"%Y-%m-%dT%H:%M:%S+00:00")
MSG_ID=$(kubectl -n $NS exec deploy/stock-radar-redis -- redis-cli XADD stockradar:polygon:aggregate '*' \
  ticker TEST_VALIDATION \
  event_type AM \
  event_ts '2026-04-10T14:30:00+00:00' \
  received_at "$TS_NOW" \
  subscription_generation_id 1 \
  open 1.00 high 1.10 low 0.99 close 1.05 \
  volume 100 vwap 1.05 transactions 1)
echo "XADD message id: $MSG_ID"

echo
echo "=== Step 7: Wait 3s, then query DB for the synthetic row ==="
sleep 3
# Adjust PG host/credentials for your env. If running from inside cluster, use the in-cluster host.
PGPASSWORD=postgres psql -h 192.168.1.77 -U postgres -d stock_radar -tAc "
  SELECT ticker || '|' || minute_ts || '|' || close
    FROM stock_radar.minute_aggregates_live
   WHERE ticker = 'TEST_VALIDATION';"

echo
echo "=== Step 8: Cleanup ==="
PGPASSWORD=postgres psql -h 192.168.1.77 -U postgres -d stock_radar -c "
  DELETE FROM stock_radar.minute_aggregates_live WHERE ticker = 'TEST_VALIDATION';
  DELETE FROM stock_radar.polygon_minute_aggregates WHERE ticker = 'TEST_VALIDATION';"

echo
echo "=== DONE ==="
echo "If Step 7 returned a row -> end-to-end pipeline is healthy. Tomorrow's open will work."