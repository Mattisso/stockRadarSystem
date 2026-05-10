WITH params AS (
    SELECT
        DATE '__PRIOR_TRADE_DATE__' AS prior_trade_date,
        DATE '__NEXT_TRADE_DATE__' AS next_trade_date,
        __MIN_PRICE__::numeric AS min_price,
        __MAX_PRICE__::numeric AS max_price,
        __MIN_AVG_VOLUME__::bigint AS min_avg_volume
),
ranked_universe AS (
    SELECT
        s.trade_date,
        s.ticker,
        s.close,
        s.volume,
        s.dollar_volume,
        s.close_to_high_ratio,
        ROW_NUMBER() OVER (
            ORDER BY
                s.volume DESC NULLS LAST,
                s.dollar_volume DESC NULLS LAST,
                s.close_to_high_ratio DESC NULLS LAST,
                s.ticker ASC
        ) AS liquidity_rank
    FROM public.polygon_day_flatfile_stage AS s
    CROSS JOIN params p
    WHERE s.trade_date = p.prior_trade_date
      AND COALESCE(s.close, 0) >= p.min_price
      AND COALESCE(s.close, 0) <= p.max_price
      AND COALESCE(s.volume, 0) >= p.min_avg_volume
),
candidate_names AS (
    SELECT DISTINCT ce.ticker
    FROM public.candidate_events_snapshot AS ce
    CROSS JOIN params p
    WHERE ce.event_ts::date = p.next_trade_date
),
decision_names AS (
    SELECT DISTINCT de.ticker
    FROM public.decision_events_snapshot AS de
    CROSS JOIN params p
    WHERE de.decision_ts::date = p.next_trade_date
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
    p.prior_trade_date,
    p.next_trade_date,
    format(
        'close between %s and %s, volume >= %s',
        p.min_price,
        p.max_price,
        p.min_avg_volume
    ) AS universe_filter,
    'rank by volume desc, dollar_volume desc, close_to_high_ratio desc' AS ranking_rule,
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
