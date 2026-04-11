"""Persistence helpers for Polygon day and minute aggregates."""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from collections import defaultdict

from sqlalchemy.orm import Session

from app.broker.interface import Quote
from app.engine.secret_ingredients import DailyUniverseSnapshot, SecretIngredientsService
from app.models.polygon_day_aggregate import PolygonDayAggregate
from app.models.polygon_minute_aggregate import PolygonMinuteAggregate
from app.models.polygon_second_aggregate import PolygonSecondAggregate
from app.models.symbol import Symbol


@dataclass(slots=True)
class PolygonDayAggregateRecord:
    ticker: str
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: float | None = None
    transactions: int | None = None
    source_ts: datetime | None = None


@dataclass(slots=True)
class PolygonMinuteAggregateRecord:
    ticker: str
    minute_ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: float | None = None
    transactions: int | None = None


@dataclass(slots=True)
class PolygonSecondAggregateRecord:
    ticker: str
    second_ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: float | None = None
    transactions: int | None = None


class PolygonAggregateService:
    """Store raw Polygon aggregates and derive the daily universe."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def upsert_day_aggregates(self, records: list[PolygonDayAggregateRecord]) -> int:
        rows_added = 0
        for record in records:
            existing = (
                self.db.query(PolygonDayAggregate)
                .filter_by(trade_date=record.trade_date, ticker=record.ticker)
                .first()
            )
            if existing is None:
                existing = PolygonDayAggregate(trade_date=record.trade_date, ticker=record.ticker)
                self.db.add(existing)
                rows_added += 1
            existing.open = record.open
            existing.high = record.high
            existing.low = record.low
            existing.close = record.close
            existing.volume = max(0, record.volume)
            existing.vwap = record.vwap
            existing.transactions = record.transactions
            existing.source_ts = record.source_ts
        self.db.flush()
        return rows_added

    def build_daily_universe(self, *, trade_date: date, max_open: float = 10.0) -> list[str]:
        rows = (
            self.db.query(PolygonDayAggregate)
            .filter(
                PolygonDayAggregate.trade_date == trade_date,
                PolygonDayAggregate.open < max_open,
            )
            .order_by(PolygonDayAggregate.ticker.asc())
            .all()
        )
        tickers = [row.ticker for row in rows]
        snapshots_by_ticker = {
            row.ticker: DailyUniverseSnapshot(
                ticker=row.ticker,
                exchange="NASDAQ",
                open_price=row.open,
                last_price=row.close,
                avg_volume=row.volume,
            )
            for row in rows
        }
        self._sync_symbols_from_day_rows(rows)
        SecretIngredientsService(self.db).record_daily_universe(
            tickers,
            trade_date=trade_date,
            snapshots_by_ticker=snapshots_by_ticker,
        )
        self.db.flush()
        return tickers

    def upsert_minute_aggregates(
        self,
        records: list[PolygonMinuteAggregateRecord],
        *,
        allowed_tickers: set[str] | None = None,
    ) -> int:
        rows_added = 0
        for record in records:
            if allowed_tickers is not None and record.ticker not in allowed_tickers:
                continue
            minute_ts = self._normalize_minute_ts(record.minute_ts)
            existing = (
                self.db.query(PolygonMinuteAggregate)
                .filter_by(ticker=record.ticker, minute_ts=minute_ts)
                .first()
            )
            if existing is None:
                existing = PolygonMinuteAggregate(ticker=record.ticker, minute_ts=minute_ts)
                self.db.add(existing)
                rows_added += 1
            existing.open = record.open
            existing.high = record.high
            existing.low = record.low
            existing.close = record.close
            existing.volume = max(0, record.volume)
            existing.vwap = record.vwap
            existing.transactions = record.transactions
        self.db.flush()
        return rows_added

    def upsert_second_aggregates(
        self,
        records: list[PolygonSecondAggregateRecord],
        *,
        allowed_tickers: set[str] | None = None,
    ) -> int:
        rows_added = 0
        for record in records:
            if allowed_tickers is not None and record.ticker not in allowed_tickers:
                continue
            second_ts = self._normalize_second_ts(record.second_ts)
            existing = (
                self.db.query(PolygonSecondAggregate)
                .filter_by(ticker=record.ticker, second_ts=second_ts)
                .first()
            )
            if existing is None:
                existing = PolygonSecondAggregate(ticker=record.ticker, second_ts=second_ts)
                self.db.add(existing)
                existing.open = record.open
                existing.high = record.high
                existing.low = record.low
                existing.close = record.close
                existing.volume = max(0, record.volume)
                existing.vwap = record.vwap
                existing.transactions = record.transactions
                rows_added += 1
                continue

            existing.high = max(existing.high, record.high)
            existing.low = min(existing.low, record.low)
            existing.close = record.close
            previous_volume = max(0, existing.volume)
            incoming_volume = max(0, record.volume)
            total_volume = previous_volume + incoming_volume
            existing.volume = total_volume
            existing.transactions = (existing.transactions or 0) + (record.transactions or 0)
            if total_volume > 0:
                previous_notional = (existing.vwap or existing.close) * previous_volume
                incoming_notional = (record.vwap or record.close) * incoming_volume
                existing.vwap = (previous_notional + incoming_notional) / total_volume
            elif record.vwap is not None:
                existing.vwap = record.vwap
        self.db.flush()
        return rows_added

    def latest_day_aggregate_date(self) -> date | None:
        row = self.db.query(PolygonDayAggregate.trade_date).order_by(PolygonDayAggregate.trade_date.desc()).first()
        return row[0] if row is not None else None

    @staticmethod
    def second_records_from_quotes(quotes: list[Quote]) -> list[PolygonSecondAggregateRecord]:
        grouped: dict[tuple[str, datetime], list[Quote]] = defaultdict(list)
        for quote in quotes:
            if quote.event_type != "trade":
                continue
            second_ts = PolygonAggregateService._normalize_second_ts(quote.timestamp)
            grouped[(quote.ticker, second_ts)].append(quote)

        records: list[PolygonSecondAggregateRecord] = []
        for (ticker, second_ts), second_quotes in grouped.items():
            ordered = sorted(second_quotes, key=lambda quote: quote.timestamp)
            prices = [quote.last for quote in ordered]
            total_volume = sum(max(0, quote.volume) for quote in ordered)
            total_notional = sum((quote.last or 0.0) * max(0, quote.volume) for quote in ordered)
            records.append(
                PolygonSecondAggregateRecord(
                    ticker=ticker,
                    second_ts=second_ts,
                    open=prices[0],
                    high=max(prices),
                    low=min(prices),
                    close=prices[-1],
                    volume=total_volume,
                    vwap=(total_notional / total_volume) if total_volume > 0 else ordered[-1].last,
                    transactions=len(ordered),
                )
            )
        records.sort(key=lambda record: (record.second_ts, record.ticker))
        return records

    def _sync_symbols_from_day_rows(self, rows: list[PolygonDayAggregate]) -> None:
        tickers = [row.ticker for row in rows]
        if not tickers:
            return

        self.db.query(Symbol).filter(Symbol.ticker.notin_(tickers)).update(
            {"is_active": False},
            synchronize_session="fetch",
        )

        existing_symbols = {
            symbol.ticker: symbol
            for symbol in self.db.query(Symbol).filter(Symbol.ticker.in_(tickers)).all()
        }

        for row in rows:
            symbol = existing_symbols.get(row.ticker)
            if symbol is None:
                symbol = Symbol(
                    ticker=row.ticker,
                    exchange="NASDAQ",
                    name="",
                    is_active=True,
                )
                self.db.add(symbol)
            symbol.exchange = symbol.exchange or "NASDAQ"
            symbol.last_price = row.close
            symbol.avg_volume = max(0, row.volume)
            symbol.is_active = True

        self.db.flush()

    @staticmethod
    def _normalize_minute_ts(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(second=0, microsecond=0)
        return value.astimezone(timezone.utc).replace(second=0, microsecond=0)

    @staticmethod
    def _normalize_second_ts(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(microsecond=0)
        return value.astimezone(timezone.utc).replace(microsecond=0)
