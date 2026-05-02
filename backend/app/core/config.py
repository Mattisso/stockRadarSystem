from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables / .env file."""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # --- Database ---
    database_url: str = "postgresql://postgres:postgres@localhost:5434/stock_radar"

    # --- API ---
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_secret_key: str = "change-me-in-production"
    api_runtime_role: str = "all"  # "all" | "web" | "worker"
    api_enable_legacy_scan_job: bool = True
    api_enable_position_monitor_job: bool = True
    api_enable_aggregate_rolling_refresh: bool = True
    api_enable_day_refresh: bool = True
    api_enable_minute_refresh: bool = True
    cors_allowed_origins: str = (
        "https://stockradarx.com,"
        "https://www.stockradarx.com,"
        "http://127.0.0.1:14200,"
        "http://localhost:14200,"
        "http://127.0.0.1:14201,"
        "http://localhost:14201,"
        "http://127.0.0.1:4200,"
        "http://localhost:4200,"
        "http://127.0.0.1:4201,"
        "http://localhost:4201"
    )
    cors_allowed_origin_regex: str = r"https://.*\.trycloudflare\.com"

    # --- Trading ---
    trading_mode: str = "paper"  # "paper" | "live"
    min_position_size: float = 4000.0
    max_position_size: float = 10000.0
    max_concurrent_positions: int = 5
    stop_loss_pct: float = 0.05
    daily_loss_limit: float = 500.0
    target_profit_per_share_min: float = 0.10
    target_profit_per_share_max: float = 0.25
    execution_chase_multiplier: float = 1.001
    execution_max_dollar_risk: float = 150.0
    execution_percent_stop_pct: float = 0.02
    execution_support_buffer_pct: float = 0.001
    execution_max_stop_pct: float = 0.03
    execution_strongest_bid_levels: int = 3
    execution_stop_revision_min_interval_seconds: int = 3
    buy_retry_attempts: int = 3
    buy_retry_backoff_seconds: float = 0.2
    max_entry_slippage_pct: float = 0.003
    buy_order_style: str = "adaptive"  # "adaptive" | "market" | "limit"
    buy_use_brackets: bool = False
    trailing_stop_pct: float = 0.03
    emergency_stop_loss_pct: float = 0.08
    l2_exit_imbalance_threshold: float = 0.35
    execution_weak_trade_window_seconds: int = 5
    execution_weak_trade_max_progress_pct: float = 0.0015
    execution_gate_max_spread_pct: float = 0.01
    execution_gate_min_bid_stacking: float = 0.55
    execution_gate_max_seller_pressure: float = 1.2
    execution_gate_min_buying_aggression: float = 0.55
    execution_gate_min_support_stability: float = 0.55
    execution_time_stop_seconds: int = 20
    execution_min_progress_pct: float = 0.003
    runner_trigger_profit_pct: float = 0.03
    strategy_entry_formula_enabled: bool = True
    strategy_entry_formula_preset: str = "balanced"
    strategy_entry_breakout_score_weight: float = 0.35
    strategy_entry_liquidity_imbalance_weight: float = 0.25
    strategy_entry_bid_stacking_weight: float = 0.15
    strategy_entry_volume_acceleration_weight: float = 0.10
    strategy_entry_order_aggression_weight: float = 0.10
    strategy_entry_ml_confidence_weight: float = 0.05
    strategy_entry_threshold: float = 0.72
    strategy_entry_min_spread_compression: float = 0.55
    strategy_entry_max_spoofing_risk: float = 0.35
    strategy_entry_min_ml_confidence: float = 0.0
    strategy_exit_formula_enabled: bool = True
    strategy_exit_formula_preset: str = "balanced"
    strategy_exit_l2_weakness_weight: float = 0.40
    strategy_exit_momentum_decay_weight: float = 0.25
    strategy_exit_spread_worsening_weight: float = 0.20
    strategy_exit_pnl_drawdown_from_peak_weight: float = 0.15
    strategy_exit_threshold: float = 0.70

    # --- Universe Filter ---
    universe_min_price: float = 1.0
    universe_max_price: float = 10.0
    universe_min_volume: int = 100_000
    secret_universe_enabled: bool = True
    secret_universe_source: str = "broker"  # "broker" | "polygon"
    secret_universe_min_price: float = 0.0
    secret_universe_max_price: float = 10.0
    secret_universe_min_volume: int = 100_000
    secret_universe_excluded_tickers: str = ""
    secret_universe_rebuild_hour: int = 8
    secret_universe_rebuild_minute: int = 0
    secret_polygon_live_max_symbols: int = 500
    secret_polygon_live_min_avg_volume: int = 500_000
    aggregate_live_max_symbols: int = 0
    aggregate_live_min_avg_volume: int = 0
    polygon_operational_subscription_max_symbols: int = 100
    polygon_operational_recent_sold_minutes: int = 30

    # --- Broker ---
    broker_type: str = "mock"  # "mock" | "ibkr"

    # --- IBKR ---
    ibkr_host: str = "127.0.0.1"
    ibkr_port: int = 7497  # TWS: 7497=paper, 7496=live | Gateway: 4002=paper, 4001=live
    ibkr_client_id: int = 1
    ibkr_timeout: int = 30
    ibkr_max_reconnect_attempts: int = 10

    # --- State Machine ---
    state_watching_threshold: float = 0.30
    state_candidate_threshold: float = 0.55
    state_l2_confirm_threshold: float = 0.65
    state_ready_to_buy_threshold: float = 0.75
    state_decay_ticks: int = 3
    state_l2_bid_stacking_min: float = 0.6
    state_l2_liquidity_imbalance_min: float = 0.6
    state_l2_order_aggression_min: float = 0.5
    state_l2_spread_compression_min: float = 0.5
    signal_dedupe_window_seconds: int = 60
    signal_dedupe_score_delta: float = 0.02

    # --- Polygon ---
    polygon_api_key: str = ""  # Empty = disabled
    polygon_mode: str = "rest"  # "rest" | "websocket" | "dev" | "sandbox"
    polygon_rest_poll_interval: float = 1.0
    polygon_ws_url: str = "wss://socket.massive.com/stocks"
    polygon_rest_url: str = "https://api.polygon.io"
    polygon_flatfiles_endpoint_url: str = "https://files.massive.com"
    polygon_enable_quote_client: bool = True
    polygon_enable_aggregate_client: bool = True
    polygon_flatfiles_bucket: str = "flatfiles"
    polygon_day_aggregate_prefix: str = "us_stocks_sip/day_aggs_v1"
    polygon_reconnect_max_delay: float = 30.0
    polygon_subscription_batch_size: int = 500
    polygon_queue_maxsize: int = 10_000
    polygon_persist_ticks: bool = False
    polygon_persist_batch_size: int = 100
    polygon_day_aggregate_ingestion_enabled: bool = False
    polygon_day_aggregate_refresh_minutes: int = 15
    polygon_minute_aggregate_ingestion_enabled: bool = True
    polygon_minute_aggregate_refresh_minutes: int = 1
    polygon_second_aggregate_recent_window_minutes: int = 15
    polygon_symbol_state_rolling_window_seconds: int = 60
    polygon_second_stream_stale_after_seconds: int = 3
    polygon_minute_stream_stale_after_minutes: int = 2
    polygon_live_cleanup_interval_minutes: int = 5
    polygon_live_ticks_retention_hours: int = 8
    polygon_live_minute_aggregates_retention_hours: int = 8
    polygon_live_second_aggregates_retention_hours: int = 8
    polygon_scope_cleanup_enabled: bool = True
    polygon_scope_cleanup_session_start_et: str = "09:30:00"
    polygon_scope_cleanup_session_end_et: str = "16:00:00"
    aggregate_rolling_refresh_seconds: int = 1
    aggregate_candidate_event_max_age_seconds: int = 15
    aggregate_history_export_enabled: bool = False
    aggregate_history_export_interval_minutes: int = 60
    aggregate_history_export_min_age_minutes: int = 30
    aggregate_history_export_dir: str = "exports/aggregate_history"
    aggregate_trigger_breakout_buffer_pct: float = 0.0005
    aggregate_trigger_velocity_bars: int = 3
    aggregate_trigger_velocity_spike_pct: float = 0.01
    aggregate_trigger_second_volume_spike_multiplier: float = 3.0
    aggregate_trigger_second_volume_spike_min_volume: int = 300
    aggregate_trigger_range_expansion_window: int = 10
    aggregate_trigger_range_expansion_multiplier: float = 1.8
    aggregate_trigger_range_expansion_close_in_range_pct: float = 0.7
    aggregate_trigger_consecutive_green_seconds: int = 3
    aggregate_trigger_minute_high_buffer_pct: float = 0.0005
    aggregate_trigger_recovery_window_seconds: int = 5
    aggregate_trigger_recovery_pullback_pct: float = 0.005
    aggregate_trigger_recovery_rebound_pct: float = 0.008
    aggregate_trigger_recovery_close_in_range_pct: float = 0.7
    aggregate_trigger_quiet_window: int = 10
    aggregate_trigger_quiet_max_avg_range_pct: float = 0.0025
    aggregate_trigger_quiet_max_avg_volume: int = 200
    aggregate_trigger_quiet_breakout_pct: float = 0.005
    aggregate_trigger_new_high_day_buffer_pct: float = 0.0005
    aggregate_trigger_new_high_day_early_minutes: int = 90
    aggregate_validation_min_average_second_volume: int = 200
    aggregate_validation_near_high_buffer_pct: float = 0.01
    aggregate_validation_sharp_drop_pct: float = 0.03
    aggregate_validation_pullback_buffer_pct: float = 0.015
    aggregate_validation_minute_strength_buffer_pct: float = 0.01
    aggregate_validation_range_expansion_multiplier: float = 0.9
    aggregate_validation_range_close_position_pct: float = 0.6
    aggregate_validation_max_extension_pct: float = 0.08
    aggregate_decision_min_validation_score: float = 0.6
    aggregate_decision_min_validation_pass_count: int = 6
    aggregate_decision_max_minute_gap_minutes: int = 5
    aggregate_buy_min_validation_score: float = 0.8
    aggregate_buy_min_validation_pass_count: int = 8
    aggregate_buy_min_candidate_score: float = 0.66
    aggregate_buy_near_high_buffer_pct: float = 0.005
    aggregate_sell_stop_loss_pct: float = 0.03
    aggregate_sell_momentum_lookback_bars: int = 5
    aggregate_sell_sharp_reversal_pct: float = 0.03
    aggregate_sell_no_continuation_seconds: int = 10
    aggregate_sell_quick_profit_pct: float = 0.05
    aggregate_sell_quick_profit_retrace_pct: float = 0.02
    polygon_dev_max_symbols: int = 3
    secret_polygon_include_trade_wildcard: bool = True
    secret_candidate_min_score: float = 0.55
    secret_candidate_max_spread_pct: float = 0.02
    secret_candidate_min_quote_rate: float = 0.10
    secret_candidate_min_buy_pressure: float = 0.45
    secret_candidate_min_volume_expansion: float = 1.10
    secret_l2_max_active: int = 8
    secret_l2_queue_maxsize: int = 100

    # --- Redis ---
    redis_url: str = ""  # Empty = use in-memory cache
    redis_l1_ttl: int = 10
    redis_l2_ttl: int = 10

    # --- ML ---
    ml_enabled: bool = True
    ml_min_training_samples: int = 50
    ml_retrain_interval_hours: int = 24
    ml_model_dir: str = "models"
    ml_confidence_weight: float = 0.3


settings = Settings()
