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

    # --- Trading ---
    trading_mode: str = "paper"  # "paper" | "live"
    min_position_size: float = 4000.0
    max_position_size: float = 10000.0
    max_concurrent_positions: int = 5
    stop_loss_pct: float = 0.05
    daily_loss_limit: float = 500.0
    target_profit_per_share_min: float = 0.10
    target_profit_per_share_max: float = 0.25
    buy_retry_attempts: int = 3
    buy_retry_backoff_seconds: float = 0.2
    max_entry_slippage_pct: float = 0.003
    buy_order_style: str = "adaptive"  # "adaptive" | "market" | "limit"
    trailing_stop_pct: float = 0.03
    emergency_stop_loss_pct: float = 0.08
    l2_exit_imbalance_threshold: float = 0.35

    # --- Universe Filter ---
    universe_min_price: float = 1.0
    universe_max_price: float = 10.0
    universe_min_volume: int = 100_000

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

    # --- Polygon ---
    polygon_api_key: str = ""  # Empty = disabled
    polygon_mode: str = "rest"  # "rest" | "websocket" | "dev" | "sandbox"
    polygon_rest_poll_interval: float = 1.0
    polygon_ws_url: str = "wss://socket.polygon.io/stocks"
    polygon_rest_url: str = "https://api.polygon.io"
    polygon_reconnect_max_delay: float = 30.0
    polygon_subscription_batch_size: int = 500
    polygon_queue_maxsize: int = 10_000
    polygon_dev_max_symbols: int = 3

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
