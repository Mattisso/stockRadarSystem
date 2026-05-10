from __future__ import annotations

import csv
import gzip
import io
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import BinaryIO

from sqlalchemy.orm import Session

from app.core.config import settings
from app.data.polygon_aggregate_service import PolygonAggregateService, PolygonDayAggregateRecord
from app.models.universe_daily import UNIVERSE_SOURCE_POLYGON_FLATFILE


@dataclass(slots=True)
class UniverseLoadStats:
    total_rows: int = 0
    valid_rows: int = 0
    filtered_rows: int = 0
    skipped_rows: int = 0


class PolygonFlatFileUniverseLoader:
    """Load the daily universe from Polygon day aggregate flat files."""

    def __init__(self, db: Session, *, s3_client=None) -> None:
        self.db = db
        self.s3_client = s3_client

    def load_universe_from_s3(
        self,
        trade_date: date,
        *,
        max_close: float | None = None,
        min_close: float | None = None,
        min_volume: int | None = None,
    ) -> list[str]:
        target_max_close = settings.universe_max_price if max_close is None else max_close
        target_min_close = settings.universe_min_price if min_close is None else min_close
        target_min_volume = settings.universe_min_volume if min_volume is None else min_volume
        records, _stats = self._fetch_day_records_from_s3(
            trade_date,
            max_close=target_max_close,
            min_close=target_min_close,
            min_volume=target_min_volume,
        )
        aggregate_service = PolygonAggregateService(self.db)
        aggregate_service.upsert_day_aggregates(records)
        return aggregate_service.build_daily_universe(
            trade_date=trade_date,
            max_close=target_max_close,
            min_close=target_min_close,
            min_volume=target_min_volume,
            source=UNIVERSE_SOURCE_POLYGON_FLATFILE,
        )

    def load_latest_universe_from_s3(
        self,
        *,
        max_lookback_days: int = 7,
        max_close: float | None = None,
        min_close: float | None = None,
        min_volume: int | None = None,
        as_of: date | None = None,
    ) -> tuple[date, list[str], UniverseLoadStats]:
        target_max_close = settings.universe_max_price if max_close is None else max_close
        target_min_close = settings.universe_min_price if min_close is None else min_close
        target_min_volume = settings.universe_min_volume if min_volume is None else min_volume
        anchor = as_of or datetime.now(timezone.utc).date()

        last_error: Exception | None = None
        for offset in range(max_lookback_days + 1):
            trade_date = anchor - timedelta(days=offset)
            if trade_date.weekday() >= 5:
                continue
            try:
                records, stats = self._fetch_day_records_from_s3(
                    trade_date,
                    max_close=target_max_close,
                    min_close=target_min_close,
                    min_volume=target_min_volume,
                )
            except Exception as exc:
                if self._should_continue_latest_lookup(exc, trade_date=trade_date, anchor=anchor):
                    last_error = exc
                    continue
                raise

            aggregate_service = PolygonAggregateService(self.db)
            aggregate_service.upsert_day_aggregates(records)
            tickers = aggregate_service.build_daily_universe(
                trade_date=trade_date,
                max_close=target_max_close,
                min_close=target_min_close,
                min_volume=target_min_volume,
                source=UNIVERSE_SOURCE_POLYGON_FLATFILE,
            )
            return trade_date, tickers, stats

        if last_error is not None:
            raise last_error
        raise FileNotFoundError("No Polygon day aggregate flat file found in lookback window")

    def parse_day_aggregate_stream(
        self,
        stream: BinaryIO,
        trade_date: date,
        *,
        max_close: float,
        min_close: float | None = None,
        min_volume: int | None = None,
    ) -> tuple[list[PolygonDayAggregateRecord], UniverseLoadStats]:
        stats = UniverseLoadStats()
        records: list[PolygonDayAggregateRecord] = []
        with gzip.GzipFile(fileobj=stream, mode="rb") as gz_stream:
            text_stream = io.TextIOWrapper(gz_stream, encoding="utf-8")
            reader = csv.DictReader(text_stream)
            for row in reader:
                stats.total_rows += 1
                record = self._parse_row(row, trade_date)
                if record is None:
                    stats.skipped_rows += 1
                    continue
                stats.valid_rows += 1
                if record.close >= max_close:
                    continue
                if min_close is not None and record.close <= min_close:
                    continue
                if min_volume is not None and max(0, record.volume) <= min_volume:
                    continue
                records.append(record)
                stats.filtered_rows += 1
        return records, stats

    @classmethod
    def build_day_aggregate_filename(cls, trade_date: date) -> str:
        return cls._build_day_aggregate_key(trade_date).rsplit("/", 1)[-1]

    @staticmethod
    def _build_day_aggregate_key(trade_date: date) -> str:
        return (
            f"{settings.polygon_day_aggregate_prefix}/"
            f"{trade_date.year:04d}/{trade_date.month:02d}/{trade_date.isoformat()}.csv.gz"
        )

    def fetch_day_aggregate_object(self, trade_date: date) -> dict:
        key = self._build_day_aggregate_key(trade_date)
        return self._get_s3_client().get_object(Bucket=settings.polygon_flatfiles_bucket, Key=key)

    def _fetch_day_records_from_s3(
        self,
        trade_date: date,
        *,
        max_close: float,
        min_close: float | None = None,
        min_volume: int | None = None,
    ) -> tuple[list[PolygonDayAggregateRecord], UniverseLoadStats]:
        response = self.fetch_day_aggregate_object(trade_date)
        body = response["Body"]
        return self.parse_day_aggregate_stream(
            body,
            trade_date,
            max_close=max_close,
            min_close=min_close,
            min_volume=min_volume,
        )

    def _get_s3_client(self):
        if self.s3_client is not None:
            return self.s3_client
        import boto3

        self.s3_client = boto3.client(
            "s3",
            endpoint_url=settings.polygon_flatfiles_endpoint_url,
        )
        return self.s3_client

    def _parse_row(self, row: dict[str, str], trade_date: date) -> PolygonDayAggregateRecord | None:
        ticker = self._get_first(row, "ticker", "T")
        open_value = self._parse_float(self._get_first(row, "open", "o"))
        high_value = self._parse_float(self._get_first(row, "high", "h"))
        low_value = self._parse_float(self._get_first(row, "low", "l"))
        close_value = self._parse_float(self._get_first(row, "close", "c"))
        volume_value = self._parse_int(self._get_first(row, "volume", "v"))
        if not ticker or open_value is None or high_value is None or low_value is None or close_value is None or volume_value is None:
            return None
        return PolygonDayAggregateRecord(
            ticker=ticker.upper(),
            trade_date=trade_date,
            open=open_value,
            high=high_value,
            low=low_value,
            close=close_value,
            volume=volume_value,
            vwap=self._parse_float(self._get_first(row, "vwap", "vw")),
            transactions=self._parse_int(self._get_first(row, "transactions", "n")),
            source_ts=self._parse_timestamp(self._get_first(row, "timestamp", "window_start", "t")),
        )

    @staticmethod
    def _get_first(row: dict[str, str], *keys: str) -> str | None:
        for key in keys:
            if key in row and row[key] not in ("", None):
                return row[key]
        return None

    @staticmethod
    def _parse_float(value: str | None) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_int(value: str | None) -> int | None:
        if value is None:
            return None
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_timestamp(value: str | None) -> datetime | None:
        if value is None:
            return None
        try:
            raw = int(float(value))
        except (TypeError, ValueError):
            return None
        # Flat-file timestamps may be emitted in seconds, milliseconds,
        # microseconds, or nanoseconds depending on source/version.
        if raw >= 1_000_000_000_000_000_000:
            raw = raw / 1_000_000_000
        elif raw >= 1_000_000_000_000_000:
            raw = raw / 1_000_000
        elif raw >= 1_000_000_000_000:
            raw = raw / 1000
        return datetime.fromtimestamp(raw, tz=timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _is_missing_object_error(exc: Exception) -> bool:
        if isinstance(exc, (FileNotFoundError, KeyError)):
            return True
        response = getattr(exc, "response", None)
        if not isinstance(response, dict):
            return False
        code = str(response.get("Error", {}).get("Code", ""))
        return code in {"404", "NoSuchKey", "NotFound"}

    @classmethod
    def _should_continue_latest_lookup(cls, exc: Exception, *, trade_date: date, anchor: date) -> bool:
        if cls._is_missing_object_error(exc):
            return True
        if trade_date != anchor:
            return False
        response = getattr(exc, "response", None)
        if not isinstance(response, dict):
            return False
        code = str(response.get("Error", {}).get("Code", ""))
        return code in {"403", "AccessDenied"}
