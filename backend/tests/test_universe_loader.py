import gzip
import io
from datetime import date

from app.data.universe_loader import PolygonFlatFileUniverseLoader
from app.models.polygon_day_aggregate import PolygonDayAggregate
from app.models.symbol import Symbol
from app.models.universe_daily import (
    UNIVERSE_KIND_MARKET,
    UNIVERSE_SOURCE_POLYGON_FLATFILE,
    UniverseDaily,
)


class FakeS3Client:
    def __init__(self, payload: bytes | dict[str, bytes]) -> None:
        self.payload = payload
        self.calls = []

    def get_object(self, *, Bucket, Key):
        self.calls.append({"Bucket": Bucket, "Key": Key})
        if isinstance(self.payload, dict):
            if Key not in self.payload:
                raise KeyError(Key)
            payload = self.payload[Key]
        else:
            payload = self.payload
        return {"Body": io.BytesIO(payload)}


class FakeClientError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


class ErroringS3Client(FakeS3Client):
    def get_object(self, *, Bucket, Key):
        self.calls.append({"Bucket": Bucket, "Key": Key})
        if isinstance(self.payload, dict):
            payload = self.payload.get(Key)
            if isinstance(payload, Exception):
                raise payload
            if payload is None:
                raise KeyError(Key)
            return {"Body": io.BytesIO(payload)}
        return super().get_object(Bucket=Bucket, Key=Key)


def _gzip_csv(text: str) -> bytes:
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb") as gz:
        gz.write(text.encode("utf-8"))
    return buffer.getvalue()


def test_parse_day_aggregate_stream_filters_by_close_and_skips_bad_rows(db):
    payload = _gzip_csv(
        "ticker,volume,open,close,high,low,timestamp,vwap,transactions\n"
        "LCID,500000,3.25,3.45,3.50,3.10,1712946600000,3.40,10\n"
        "BADROW,not-a-number,3.0,3.5,3.6,2.9,1712946600000,3.2,1\n"
        "AAPL,1000000,150.0,150.5,151.0,149.5,1712946600000,150.2,20\n"
    )
    loader = PolygonFlatFileUniverseLoader(db, s3_client=FakeS3Client(payload))

    records, stats = loader.parse_day_aggregate_stream(
        io.BytesIO(payload),
        date(2026, 4, 13),
        max_close=10.0,
        min_close=1.0,
    )

    assert [record.ticker for record in records] == ["LCID"]
    assert stats.total_rows == 3
    assert stats.valid_rows == 2
    assert stats.filtered_rows == 1
    assert stats.skipped_rows == 1


def test_load_universe_from_s3_persists_only_universe_related_rows(db):
    payload = _gzip_csv(
        "ticker,volume,open,close,high,low,timestamp,vwap,transactions\n"
        "LCID,500000,3.25,3.45,3.50,3.10,1712946600000,3.40,10\n"
        "AAPL,1000000,150.0,150.5,151.0,149.5,1712946600000,150.2,20\n"
        "F,900000,9.80,9.95,10.10,9.70,1712946600000,9.90,12\n"
    )
    s3_client = FakeS3Client(payload)
    loader = PolygonFlatFileUniverseLoader(db, s3_client=s3_client)

    tickers = loader.load_universe_from_s3(date(2026, 4, 13), max_close=10.0, min_close=1.0)
    db.commit()

    assert tickers == ["F", "LCID"]
    day_rows = db.query(PolygonDayAggregate).order_by(PolygonDayAggregate.ticker.asc()).all()
    assert [row.ticker for row in day_rows] == ["F", "LCID"]
    universe_rows = db.query(UniverseDaily).order_by(UniverseDaily.ticker.asc()).all()
    assert [row.ticker for row in universe_rows] == ["F", "LCID"]
    assert all(row.universe_kind == UNIVERSE_KIND_MARKET for row in universe_rows)
    assert all(row.source == UNIVERSE_SOURCE_POLYGON_FLATFILE for row in universe_rows)

    symbols = db.query(Symbol).order_by(Symbol.ticker.asc()).all()
    assert [symbol.ticker for symbol in symbols] == ["F", "LCID"]
    assert all(symbol.is_active for symbol in symbols)

    assert s3_client.calls[0]["Key"].endswith("2026/04/2026-04-13.csv.gz")


def test_load_latest_universe_from_s3_falls_back_to_most_recent_available_file(db):
    latest_payload = _gzip_csv(
        "ticker,volume,open,close,high,low,timestamp,vwap,transactions\n"
        "LCID,500000,3.25,3.45,3.50,3.10,1712860200000,3.40,10\n"
    )
    s3_client = FakeS3Client(
        {
            "us_stocks_sip/day_aggs_v1/2026/04/2026-04-10.csv.gz": latest_payload,
        }
    )
    loader = PolygonFlatFileUniverseLoader(db, s3_client=s3_client)

    trade_date, tickers, stats = loader.load_latest_universe_from_s3(
        as_of=date(2026, 4, 13),
        max_lookback_days=3,
        max_close=10.0,
        min_close=1.0,
    )
    db.commit()

    assert trade_date == date(2026, 4, 10)
    assert tickers == ["LCID"]
    assert stats.filtered_rows == 1
    assert len(s3_client.calls) == 2


def test_load_latest_universe_from_s3_skips_weekends_before_probing_s3(db):
    latest_payload = _gzip_csv(
        "ticker,volume,open,close,high,low,timestamp,vwap,transactions\n"
        "LCID,500000,3.25,3.45,3.50,3.10,1712860200000,3.40,10\n"
    )
    s3_client = FakeS3Client(
        {
            "us_stocks_sip/day_aggs_v1/2026/04/2026-04-17.csv.gz": latest_payload,
        }
    )
    loader = PolygonFlatFileUniverseLoader(db, s3_client=s3_client)

    trade_date, tickers, stats = loader.load_latest_universe_from_s3(
        as_of=date(2026, 4, 19),
        max_lookback_days=3,
        max_close=10.0,
        min_close=1.0,
    )

    assert trade_date == date(2026, 4, 17)
    assert tickers == ["LCID"]
    assert stats.filtered_rows == 1
    assert [call["Key"] for call in s3_client.calls] == ["us_stocks_sip/day_aggs_v1/2026/04/2026-04-17.csv.gz"]


def test_load_latest_universe_from_s3_continues_past_anchor_access_denied(db):
    latest_payload = _gzip_csv(
        "ticker,volume,open,close,high,low,timestamp,vwap,transactions\n"
        "LCID,500000,3.25,3.45,3.50,3.10,1712860200000,3.40,10\n"
    )
    s3_client = ErroringS3Client(
        {
            "us_stocks_sip/day_aggs_v1/2026/04/2026-04-21.csv.gz": FakeClientError("403"),
            "us_stocks_sip/day_aggs_v1/2026/04/2026-04-20.csv.gz": latest_payload,
        }
    )
    loader = PolygonFlatFileUniverseLoader(db, s3_client=s3_client)

    trade_date, tickers, stats = loader.load_latest_universe_from_s3(
        as_of=date(2026, 4, 21),
        max_lookback_days=1,
        max_close=10.0,
        min_close=1.0,
    )

    assert trade_date == date(2026, 4, 20)
    assert tickers == ["LCID"]
    assert stats.filtered_rows == 1


def test_parse_day_aggregate_stream_accepts_nanosecond_timestamps(db):
    payload = _gzip_csv(
        "ticker,volume,open,close,high,low,timestamp,vwap,transactions\n"
        "LCID,500000,3.25,3.45,3.50,3.10,1744934400000000000,3.40,10\n"
    )
    loader = PolygonFlatFileUniverseLoader(db, s3_client=FakeS3Client(payload))

    records, stats = loader.parse_day_aggregate_stream(
        io.BytesIO(payload),
        date(2026, 4, 18),
        max_close=10.0,
        min_close=1.0,
    )

    assert stats.filtered_rows == 1
    assert records[0].source_ts is not None
    assert records[0].source_ts.year == 2025
