"""Runtime status snapshot for Secret Ingredients."""

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class SecretIngredientsRuntimeStatus:
    configured_secret_universe_source: str = "broker"
    last_secret_universe_source: str | None = None
    last_secret_universe_refresh_at: datetime | None = None
    last_scan_at: datetime | None = None
    last_candidate_count: int = 0
    last_handoff_count: int = 0
    last_promotion_count: int = 0
    secret_universe_size: int = 0
    last_error: str | None = None
    recent_promoted_tickers: list[str] = field(default_factory=list)

    def mark_secret_universe_refresh(self, count: int, *, source: str) -> None:
        self.last_secret_universe_refresh_at = datetime.now(tz=timezone.utc)
        self.last_secret_universe_source = source
        self.secret_universe_size = count
        self.last_error = None

    def mark_scan(self, *, candidates: int, handoffs: int, promotions: int, promoted_tickers: list[str]) -> None:
        self.last_scan_at = datetime.now(tz=timezone.utc)
        self.last_candidate_count = candidates
        self.last_handoff_count = handoffs
        self.last_promotion_count = promotions
        self.recent_promoted_tickers = list(promoted_tickers)
        self.last_error = None

    def mark_error(self, message: str) -> None:
        self.last_error = message

    def to_dict(self) -> dict:
        return {
            "last_secret_universe_refresh_at": (
                self.last_secret_universe_refresh_at.isoformat()
                if self.last_secret_universe_refresh_at
                else None
            ),
            "configured_secret_universe_source": self.configured_secret_universe_source,
            "last_secret_universe_source": self.last_secret_universe_source,
            "last_scan_at": self.last_scan_at.isoformat() if self.last_scan_at else None,
            "last_candidate_count": self.last_candidate_count,
            "last_handoff_count": self.last_handoff_count,
            "last_promotion_count": self.last_promotion_count,
            "secret_universe_size": self.secret_universe_size,
            "last_error": self.last_error,
            "recent_promoted_tickers": self.recent_promoted_tickers,
        }
