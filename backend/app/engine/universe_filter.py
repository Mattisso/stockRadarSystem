"""Universe Filter Engine — scans NASDAQ for sub-$10 stocks matching criteria."""

from sqlalchemy.orm import Session

from app.broker.interface import BrokerInterface
from app.core.config import settings
from app.core.logging import get_logger
from app.models.symbol import Symbol

log = get_logger(__name__)


class UniverseFilterEngine:
    """Scans the broker's universe and maintains the active watchlist in the database."""

    def __init__(self, broker: BrokerInterface, db: Session) -> None:
        self.broker = broker
        self.db = db

    async def refresh_universe(self) -> list[str]:
        """Scan for all NASDAQ stocks matching filter criteria and sync to DB.

        Returns the list of active tickers.
        """
        tickers = await self.broker.get_universe(
            max_price=settings.universe_max_price,
            min_price=settings.universe_min_price,
            min_volume=settings.universe_min_volume,
        )
        log.info("universe_filter.scan_complete", candidate_count=len(tickers))

        # Deactivate symbols no longer in the universe
        self.db.query(Symbol).filter(Symbol.ticker.notin_(tickers)).update(
            {"is_active": False}, synchronize_session="fetch"
        )

        # Upsert active symbols
        for ticker in tickers:
            existing = self.db.query(Symbol).filter_by(ticker=ticker).first()
            if existing:
                existing.is_active = True
            else:
                quote = await self.broker.get_quote(ticker)
                self.db.add(
                    Symbol(
                        ticker=ticker,
                        exchange="NASDAQ",
                        last_price=quote.last,
                        avg_volume=quote.volume,
                        is_active=True,
                    )
                )

        self.db.commit()
        log.info("universe_filter.db_synced", active_count=len(tickers))
        return tickers

    def get_active_tickers(self) -> list[str]:
        """Return currently active tickers from the database."""
        symbols = self.db.query(Symbol).filter_by(is_active=True).all()
        return [s.ticker for s in symbols]
