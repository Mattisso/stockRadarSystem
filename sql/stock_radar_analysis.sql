CREATE TABLE IF NOT EXISTS public.polygon_day_flatfile_stage (
    trade_date date NOT NULL,
    ticker text NOT NULL,
    open numeric(18, 6),
    high numeric(18, 6),
    low numeric(18, 6),
    close numeric(18, 6),
    volume bigint,
    vwap numeric(18, 6),
    transactions bigint,
    dollar_volume numeric(24, 6) GENERATED ALWAYS AS (
        CASE
            WHEN close IS NULL OR volume IS NULL THEN NULL
            ELSE close * volume
        END
    ) STORED,
    close_to_high_ratio numeric(18, 6) GENERATED ALWAYS AS (
        CASE
            WHEN high IS NULL OR high = 0 OR close IS NULL THEN NULL
            ELSE close / high
        END
    ) STORED,
    intraday_range_pct numeric(18, 6) GENERATED ALWAYS AS (
        CASE
            WHEN open IS NULL OR open = 0 OR high IS NULL OR low IS NULL THEN NULL
            ELSE (high - low) / open
        END
    ) STORED,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (trade_date, ticker)
);

CREATE INDEX IF NOT EXISTS ix_polygon_day_flatfile_stage_universe_filter
    ON public.polygon_day_flatfile_stage (trade_date, close, volume DESC, ticker);

CREATE INDEX IF NOT EXISTS ix_polygon_day_flatfile_stage_rank_metrics
    ON public.polygon_day_flatfile_stage (trade_date, dollar_volume DESC, close_to_high_ratio DESC, ticker);

CREATE TABLE IF NOT EXISTS public.analysis_cap_sizes (
    cap_size integer PRIMARY KEY
);

INSERT INTO public.analysis_cap_sizes (cap_size)
VALUES
    (50),
    (100),
    (150),
    (250),
    (500),
    (750),
    (1000)
ON CONFLICT (cap_size) DO NOTHING;

CREATE TABLE IF NOT EXISTS public.subscription_cap_analysis_result (
    prior_trade_date date NOT NULL,
    next_trade_date date NOT NULL,
    universe_filter text NOT NULL,
    ranking_rule text NOT NULL,
    cap_size integer NOT NULL,
    candidate_count integer NOT NULL,
    decision_count integer NOT NULL,
    captured_candidate_count integer NOT NULL,
    captured_decision_count integer NOT NULL,
    candidate_recall numeric(10, 6),
    decision_recall numeric(10, 6),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (prior_trade_date, next_trade_date, universe_filter, ranking_rule, cap_size)
);

CREATE TABLE IF NOT EXISTS public.candidate_events_snapshot (
    id integer PRIMARY KEY,
    ticker text NOT NULL,
    event_ts timestamptz NOT NULL,
    trigger_name text NOT NULL,
    trigger_score double precision,
    trigger_payload text,
    last_second_ts timestamptz,
    last_minute_ts timestamptz,
    seconds_since_last_trade_bar integer,
    minutes_since_last_trade_bar integer,
    is_second_stream_stale boolean NOT NULL DEFAULT false,
    is_minute_stream_stale boolean NOT NULL DEFAULT false,
    processed_at timestamptz,
    created_at timestamptz
);

CREATE INDEX IF NOT EXISTS ix_candidate_events_snapshot_event_ts
    ON public.candidate_events_snapshot (event_ts);

CREATE INDEX IF NOT EXISTS ix_candidate_events_snapshot_ticker
    ON public.candidate_events_snapshot (ticker);

CREATE TABLE IF NOT EXISTS public.decision_events_snapshot (
    id integer PRIMARY KEY,
    ticker text NOT NULL,
    decision_ts timestamptz NOT NULL,
    decision_type text NOT NULL,
    reason_code text NOT NULL,
    decision_payload text,
    candidate_score double precision,
    validation_pass_count integer,
    seconds_since_last_trade_bar integer,
    minutes_since_last_trade_bar integer,
    is_second_stream_stale boolean NOT NULL DEFAULT false,
    is_minute_stream_stale boolean NOT NULL DEFAULT false,
    created_at timestamptz
);

CREATE INDEX IF NOT EXISTS ix_decision_events_snapshot_decision_ts
    ON public.decision_events_snapshot (decision_ts);

CREATE INDEX IF NOT EXISTS ix_decision_events_snapshot_ticker
    ON public.decision_events_snapshot (ticker);

CREATE TABLE IF NOT EXISTS public.polygon_am_flatfile_stage (
    trade_date date NOT NULL,
    bucket_ts timestamptz NOT NULL,
    ticker text NOT NULL,
    open numeric(18, 6),
    high numeric(18, 6),
    low numeric(18, 6),
    close numeric(18, 6),
    volume bigint,
    vwap numeric(18, 6),
    transactions bigint,
    dollar_volume numeric(24, 6) GENERATED ALWAYS AS (
        CASE
            WHEN close IS NULL OR volume IS NULL THEN NULL
            ELSE close * volume
        END
    ) STORED,
    close_to_high_ratio numeric(18, 6) GENERATED ALWAYS AS (
        CASE
            WHEN high IS NULL OR high = 0 OR close IS NULL THEN NULL
            ELSE close / high
        END
    ) STORED,
    intraday_range_pct numeric(18, 6) GENERATED ALWAYS AS (
        CASE
            WHEN open IS NULL OR open = 0 OR high IS NULL OR low IS NULL THEN NULL
            ELSE (high - low) / open
        END
    ) STORED,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (trade_date, ticker, bucket_ts)
);

CREATE INDEX IF NOT EXISTS ix_polygon_am_flatfile_stage_time_window
    ON public.polygon_am_flatfile_stage (trade_date, bucket_ts, ticker);

CREATE INDEX IF NOT EXISTS ix_polygon_am_flatfile_stage_rank_metrics
    ON public.polygon_am_flatfile_stage (trade_date, bucket_ts, volume DESC, dollar_volume DESC, ticker);
