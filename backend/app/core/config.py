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
    max_position_size: float = 5000.0
    max_concurrent_positions: int = 5
    stop_loss_pct: float = 0.05
    daily_loss_limit: float = 500.0
    target_profit_per_share_min: float = 0.10
    target_profit_per_share_max: float = 0.25

    # --- Universe Filter ---
    universe_min_price: float = 1.0
    universe_max_price: float = 10.0
    universe_min_volume: int = 100_000

    # --- Broker ---
    broker_type: str = "mock"  # "mock" | "ibkr"

    # --- IBKR ---
    ibkr_host: str = "127.0.0.1"
    ibkr_port: int = 7497  # 7497=paper, 7496=live
    ibkr_client_id: int = 1
    ibkr_timeout: int = 30
    ibkr_max_reconnect_attempts: int = 10

    # --- ML ---
    ml_enabled: bool = True
    ml_min_training_samples: int = 50
    ml_retrain_interval_hours: int = 24
    ml_model_dir: str = "models"
    ml_confidence_weight: float = 0.3


settings = Settings()
