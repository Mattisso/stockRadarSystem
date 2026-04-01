"""Prometheus business metrics for Stock Radar System."""

from prometheus_client import Counter, Gauge, Histogram

# -- Signals --
SIGNALS_DETECTED = Counter(
    "stockradar_signals_detected_total",
    "Total signals detected",
    ["signal_type"],
)

# -- Trades --
TRADES_EXECUTED = Counter(
    "stockradar_trades_executed_total",
    "Total trades executed",
    ["side"],
)

TRADE_PNL = Histogram(
    "stockradar_trade_pnl_dollars",
    "Realized P&L per closed trade in dollars",
    buckets=[-500, -200, -100, -50, -20, -10, 0, 10, 20, 50, 100, 200, 500, 1000],
)

# -- Positions --
OPEN_POSITIONS = Gauge(
    "stockradar_open_positions",
    "Current number of open positions",
)

# -- Risk --
RISK_REJECTIONS = Counter(
    "stockradar_risk_rejections_total",
    "Total trades rejected by risk manager",
    ["reason"],
)

# -- State Machine --
STATE_TRANSITIONS = Counter(
    "stockradar_state_transitions_total",
    "State machine transitions",
    ["from_state", "to_state"],
)

# -- ML --
ML_MODEL_TRAINED = Gauge(
    "stockradar_ml_model_trained",
    "Whether the ML model is trained (1) or not (0)",
)

ML_RETRAIN_TOTAL = Counter(
    "stockradar_ml_retrain_total",
    "Total ML model retraining runs",
    ["status"],
)

# -- Scheduler --
SCHEDULER_JOB_DURATION = Histogram(
    "stockradar_scheduler_job_duration_seconds",
    "Duration of scheduler jobs",
    ["job"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30],
)

SCHEDULER_JOB_ERRORS = Counter(
    "stockradar_scheduler_job_errors_total",
    "Total scheduler job errors",
    ["job"],
)

# -- Polygon / Secret Ingredients runtime --
POLYGON_SESSION_CONNECTED = Gauge(
    "stockradar_polygon_session_connected",
    "Whether the Polygon session is currently connected",
    ["mode"],
)

POLYGON_RECONNECT_TOTAL = Counter(
    "stockradar_polygon_reconnect_total",
    "Total Polygon reconnect attempts",
    ["mode"],
)

SECRET_L2_QUEUE_DEPTH = Gauge(
    "stockradar_secret_l2_queue_depth",
    "Current depth of the Secret Ingredients L2 promotion queue",
)

SECRET_L2_PROMOTIONS_TOTAL = Counter(
    "stockradar_secret_l2_promotions_total",
    "Total Secret Ingredients promotions into L2 subscriptions",
)

SECRET_CANDIDATES_TOTAL = Counter(
    "stockradar_secret_candidates_total",
    "Total Secret Ingredients candidates emitted by the dedicated scorer",
)

SECRET_HANDOFFS_TOTAL = Counter(
    "stockradar_secret_handoffs_total",
    "Total Secret Ingredients handoffs emitted toward Secret Sauce",
)

SECRET_ACTIVE_L2_SLOTS = Gauge(
    "stockradar_secret_active_l2_slots",
    "Current number of active Secret Ingredients L2 slots",
)

SECRET_UNIVERSE_SIZE = Gauge(
    "stockradar_secret_universe_size",
    "Current size of the dedicated Secret Ingredients daily universe",
)
