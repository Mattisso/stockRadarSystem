WITH params AS (
    SELECT
        DATE '__TRADE_DATE__' AS trade_date,
        TIME '__CUTOFF_TIME__' AS cutoff_time,
        __MIN_PRICE__::numeric AS min_price,
        __MAX_PRICE__::numeric AS max_price,
        __MIN_VOLUME__::bigint AS min_volume
),
cutoff_rows AS (
    SELECT
        s.trade_date,
        s.ticker,
        s.bucket_ts,
        s.open,
        s.high,
        s.low,
        s.close,
        s.volume,
        s.vwap,
        s.transactions,
        s.dollar_volume,
        s.close_to_high_ratio,
        ROW_NUMBER() OVER (
            PARTITION BY s.trade_date, s.ticker
            ORDER BY s.bucket_ts DESC
        ) AS latest_row_rank
    FROM public.polygon_am_flatfile_stage AS s
    CROSS JOIN params p
    WHERE s.trade_date = p.trade_date
      AND (s.bucket_ts AT TIME ZONE 'America/New_York')::time <= p.cutoff_time
),
per_ticker_cutoff AS (
    SELECT
        c.trade_date,
        c.ticker,
        MAX(c.close) FILTER (WHERE c.latest_row_rank = 1) AS cutoff_close,
        MAX(c.high) AS session_high_through_cutoff,
        SUM(c.volume) AS cum_volume_through_cutoff,
        SUM(c.dollar_volume) AS cum_dollar_volume_through_cutoff,
        MAX(c.close_to_high_ratio) FILTER (WHERE c.latest_row_rank = 1) AS cutoff_close_to_high_ratio
    FROM cutoff_rows AS c
    GROUP BY c.trade_date, c.ticker
),
ranked_universe AS (
    SELECT
        pcut.*,
        ROW_NUMBER() OVER (
            ORDER BY
                pcut.cum_volume_through_cutoff DESC NULLS LAST,
                pcut.cum_dollar_volume_through_cutoff DESC NULLS LAST,
                pcut.cutoff_close_to_high_ratio DESC NULLS LAST,
                pcut.ticker ASC
        ) AS liquidity_rank
    FROM per_ticker_cutoff AS pcut
    CROSS JOIN params p
    WHERE COALESCE(pcut.cutoff_close, 0) >= p.min_price
      AND COALESCE(pcut.cutoff_close, 0) <= p.max_price
      AND COALESCE(pcut.cum_volume_through_cutoff, 0) >= p.min_volume
),
candidate_names AS (
    SELECT DISTINCT ce.ticker
    FROM public.candidate_events_snapshot AS ce
    CROSS JOIN params p
    WHERE ce.event_ts::date = p.trade_date
      AND (ce.event_ts AT TIME ZONE 'America/New_York')::time > p.cutoff_time
),
decision_names AS (
    SELECT DISTINCT de.ticker
    FROM public.decision_events_snapshot AS de
    CROSS JOIN params p
    WHERE de.decision_ts::date = p.trade_date
      AND (de.decision_ts AT TIME ZONE 'America/New_York')::time > p.cutoff_time
),
base_counts AS (
    SELECT
        (SELECT COUNT(*) FROM candidate_names) AS candidate_count,
        (SELECT COUNT(*) FROM decision_names) AS decision_count
),
cap_results AS (
    SELECT
        caps.cap_size,
        COUNT(*) FILTER (
            WHERE ru.liquidity_rank <= caps.cap_size
              AND EXISTS (SELECT 1 FROM candidate_names cn WHERE cn.ticker = ru.ticker)
        ) AS captured_candidate_count,
        COUNT(*) FILTER (
            WHERE ru.liquidity_rank <= caps.cap_size
              AND EXISTS (SELECT 1 FROM decision_names dn WHERE dn.ticker = ru.ticker)
        ) AS captured_decision_count
    FROM public.analysis_cap_sizes AS caps
    CROSS JOIN ranked_universe AS ru
    GROUP BY caps.cap_size
)
SELECT
    p.trade_date,
    p.cutoff_time,
    format(
        'close between %s and %s, cumulative volume >= %s',
        p.min_price,
        p.max_price,
        p.min_volume
    ) AS universe_filter,
    'rank by cumulative volume desc, cumulative dollar_volume desc, cutoff close_to_high_ratio desc' AS ranking_rule,
    cr.cap_size,
    bc.candidate_count,
    bc.decision_count,
    cr.captured_candidate_count,
    cr.captured_decision_count,
    CASE
        WHEN bc.candidate_count = 0 THEN NULL
        ELSE ROUND(cr.captured_candidate_count::numeric / bc.candidate_count, 6)
    END AS candidate_recall,
    CASE
        WHEN bc.decision_count = 0 THEN NULL
        ELSE ROUND(cr.captured_decision_count::numeric / bc.decision_count, 6)
    END AS decision_recall
FROM cap_results AS cr
CROSS JOIN base_counts AS bc
CROSS JOIN params p
ORDER BY cr.cap_size;
