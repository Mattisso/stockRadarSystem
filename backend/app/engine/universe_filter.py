"""Universe Filter Engine — scans NASDAQ for sub-$10 stocks matching criteria."""

from app.broker.interface import Quote
from sqlalchemy.orm import Session

from app.broker.interface import BrokerInterface
from app.core.config import settings
from app.core.logging import get_logger
from app.engine.secret_ingredients import SecretIngredientsService
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
        tickers = await self._load_filtered_universe(
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
        SecretIngredientsService(self.db).record_daily_universe(tickers)
        self.db.commit()
        log.info("universe_filter.db_synced", active_count=len(tickers))
        return tickers

    async def refresh_secret_ingredients_universe(
        self,
        *,
        universe_quotes: list[Quote] | None = None,
    ) -> list[str]:
        """Build the dedicated Secret Ingredients daily universe snapshot.

        This persists the day-level universe and ensures Symbol metadata exists,
        but it does not own the active watchlist used by the fast scan loop.
        """
        excluded = self._secret_universe_excluded_tickers()
        if universe_quotes is None:
            tickers = await self._load_filtered_universe(
                max_price=settings.secret_universe_max_price,
                min_price=settings.secret_universe_min_price,
                min_volume=settings.secret_universe_min_volume,
                excluded_tickers=excluded,
            )
            quotes_by_ticker = {ticker: await self.broker.get_quote(ticker) for ticker in tickers}
        else:
            filtered_quotes = [quote for quote in universe_quotes if quote.ticker not in excluded]
            tickers = [quote.ticker for quote in filtered_quotes]
            quotes_by_ticker = {quote.ticker: quote for quote in filtered_quotes}
        log.info("secret_universe.scan_complete", candidate_count=len(tickers))

        for ticker in tickers:
            existing = self.db.query(Symbol).filter_by(ticker=ticker).first()
            quote = quotes_by_ticker[ticker]
            if existing:
                existing.exchange = existing.exchange or "NASDAQ"
                existing.last_price = quote.last
                existing.avg_volume = quote.volume
            else:
                self.db.add(
                    Symbol(
                        ticker=ticker,
                        exchange="NASDAQ",
                        last_price=quote.last,
                        avg_volume=quote.volume,
                        is_active=False,
                    )
                )

        self.db.flush()
        SecretIngredientsService(self.db).record_daily_universe(tickers)
        self.db.commit()
        log.info("secret_universe.persisted", count=len(tickers))
        return tickers

    def get_active_tickers(self) -> list[str]:
        """Return currently active tickers from the database."""
        symbols = self.db.query(Symbol).filter_by(is_active=True).all()
        return [s.ticker for s in symbols]

    def get_secret_ingredients_tickers(self) -> list[str]:
        """Return the most recent persisted Secret Ingredients universe snapshot."""
        return SecretIngredientsService(self.db).latest_daily_universe_tickers()

    async def _load_filtered_universe(
        self,
        *,
        max_price: float,
        min_price: float,
        min_volume: int,
        excluded_tickers: set[str] | None = None,
    ) -> list[str]:
        tickers = await self.broker.get_universe(
            max_price=max_price,
            min_price=min_price,
            min_volume=min_volume,
        )
        excluded = excluded_tickers or set()
        return [ticker for ticker in tickers if ticker not in excluded]

    @staticmethod
    def _secret_universe_excluded_tickers() -> set[str]:
        raw = settings.secret_universe_excluded_tickers.strip()
        if not raw:
            return set()
        return {ticker.strip().upper() for ticker in raw.split(",") if ticker.strip()}
