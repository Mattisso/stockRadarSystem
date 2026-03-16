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

    # --- IBKR (Phase 1b) ---
    ibkr_host: str = ""
    ibkr_port: int = 0
    ibkr_client_id: int = 0


settings = Settings()
