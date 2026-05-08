-- Diagnose AM/A persistence on 2026-05-08
--
-- Symptom: /api/polygon/minute-aggregates returns items=[] / trade_date=null,
-- but /api/polygon/second-aggregates returns populated rows for trade_date=2026-05-08.
-- Worker logs show polygon.aggregate_events_published with minute_count=0 second_count=N
-- consistently — Polygon WS is delivering A bars but no AM bars are ever published.
--
-- Run each query in DBeaver and capture results. The combination tells us where
-- the AM events are getting lost.
--
-- Companion shell command (run separately, not in DBeaver):
--   kubectl -n stock-radar-public logs deploy/stock-radar-polygon-ingest-worker --since=30m \
--     | grep -iE "polygon\.ws_subscribed|polygon\.ws_status|max_subscriptions|auth_failed" | head -20


-- ────────────────────────────────────────────────────────────────────────────
-- 1. Are SECONDS landing in the live table for the last 30 min?
--    (The API said yes; this confirms persistence is healthy for the A channel.)
-- ────────────────────────────────────────────────────────────────────────────
SELECT
  count(*)              AS rows,
  min(created_at)       AS first_today,
  max(created_at)       AS last_today,
  count(DISTINCT ticker) AS tickers
FROM stock_radar.second_aggregates_live
WHERE created_at > now() - interval '30 minutes';


-- ────────────────────────────────────────────────────────────────────────────
-- 2. Are MINUTES landing in the live table for the last 30 min?
--    (The API said no; expect 0. Confirms AM events are not being persisted.)
-- ────────────────────────────────────────────────────────────────────────────
SELECT
  count(*)              AS rows,
  min(created_at)       AS first_today,
  max(created_at)       AS last_today,
  count(DISTINCT ticker) AS tickers
FROM stock_radar.minute_aggregates_live
WHERE created_at > now() - interval '30 minutes';


-- ────────────────────────────────────────────────────────────────────────────
-- 3. Compare live vs history tables side-by-side for the last 30 min.
--    Tells us whether the flatfile path also has gaps.
-- ────────────────────────────────────────────────────────────────────────────
SELECT 'minute_live'    AS tbl, count(*) AS rows, max(created_at) AS last
  FROM stock_radar.minute_aggregates_live
 WHERE created_at > now() - interval '30 minutes'
UNION ALL
SELECT 'minute_history',     count(*), max(created_at)
  FROM stock_radar.polygon_minute_aggregates
 WHERE created_at > now() - interval '30 minutes'
UNION ALL
SELECT 'second_live',        count(*), max(created_at)
  FROM stock_radar.second_aggregates_live
 WHERE created_at > now() - interval '30 minutes'
UNION ALL
SELECT 'second_history',     count(*), max(created_at)
  FROM stock_radar.polygon_second_aggregates
 WHERE created_at > now() - interval '30 minutes';


-- ────────────────────────────────────────────────────────────────────────────
-- 4. What's the most recent minute_ts ever recorded in the live table?
--    If it's stuck at a date before today, AM has been broken for days.
-- ────────────────────────────────────────────────────────────────────────────
SELECT
  max(minute_ts)  AS latest_minute_ts,
  max(created_at) AS latest_created_at
FROM stock_radar.minute_aggregates_live;


-- ────────────────────────────────────────────────────────────────────────────
-- 5. Distribution of live minute rows across the last 3 days.
--    Shows whether AM ever worked recently or has been broken since 2026-05-01.
-- ────────────────────────────────────────────────────────────────────────────
SELECT
  date_trunc('day', minute_ts)::date AS day,
  count(*)                           AS rows,
  count(DISTINCT ticker)             AS tickers
FROM stock_radar.minute_aggregates_live
WHERE minute_ts > now() - interval '3 days'
GROUP BY 1
ORDER BY 1;


-- ────────────────────────────────────────────────────────────────────────────
-- 6. (Optional) Sample the actual rows landing in second_aggregates_live now
--    so we can confirm WS feed is providing real ticker data.
-- ────────────────────────────────────────────────────────────────────────────
SELECT ticker, second_ts, close, created_at
  FROM stock_radar.second_aggregates_live
 WHERE created_at > now() - interval '5 minutes'
 ORDER BY created_at DESC
 LIMIT 10;
