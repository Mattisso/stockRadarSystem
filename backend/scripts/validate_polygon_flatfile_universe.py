#!/usr/bin/env python3
"""Validate direct Polygon flat-file universe loading.

Usage examples:

  python backend/scripts/validate_polygon_flatfile_universe.py --date 2026-04-14
  python backend/scripts/validate_polygon_flatfile_universe.py --latest --lookback-days 7

Environment variables used when flags are omitted:

  POLYGON_FLATFILES_BUCKET
  POLYGON_DAY_AGGREGATE_PREFIX
  UNIVERSE_MAX_PRICE
  UNIVERSE_MIN_PRICE
  AWS_ACCESS_KEY_ID
  AWS_SECRET_ACCESS_KEY
  AWS_DEFAULT_REGION
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value in (None, ""):
        return default
    return float(value)


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    return default if value in (None, "") else value


@dataclass(slots=True)
class FlatFileStats:
    total_rows: int = 0
    valid_rows: int = 0
    filtered_rows: int = 0
    skipped_rows: int = 0


def build_key(trade_date: date, prefix: str) -> str:
    return f"{prefix}/{trade_date.year:04d}/{trade_date.month:02d}/{trade_date.isoformat()}.csv.gz"


def get_s3_client():
    try:
        import boto3
    except ImportError as exc:
        raise SystemExit("boto3 is required to run this script") from exc
    return boto3.client("s3")


def parse_stream(stream, *, max_close: float, min_close: float) -> tuple[list[dict], FlatFileStats]:
    stats = FlatFileStats()
    records: list[dict] = []
    with gzip.GzipFile(fileobj=stream, mode="rb") as gz_stream:
        text_stream = io.TextIOWrapper(gz_stream, encoding="utf-8")
        reader = csv.DictReader(text_stream)
        for row in reader:
            stats.total_rows += 1
            ticker = _first(row, "ticker", "T")
            open_value = _parse_float(_first(row, "open", "o"))
            high_value = _parse_float(_first(row, "high", "h"))
            low_value = _parse_float(_first(row, "low", "l"))
            close_value = _parse_float(_first(row, "close", "c"))
            volume_value = _parse_int(_first(row, "volume", "v"))
            if not ticker or open_value is None or high_value is None or low_value is None or close_value is None or volume_value is None:
                stats.skipped_rows += 1
                continue
            stats.valid_rows += 1
            if close_value >= max_close or close_value < min_close:
                continue
            records.append(
                {
                    "ticker": ticker.upper(),
                    "open": open_value,
                    "high": high_value,
                    "low": low_value,
                    "close": close_value,
                    "volume": volume_value,
                }
            )
            stats.filtered_rows += 1
    return records, stats


def load_for_date(s3_client, *, bucket: str, prefix: str, trade_date: date, max_close: float, min_close: float):
    key = build_key(trade_date, prefix)
    obj = s3_client.get_object(Bucket=bucket, Key=key)
    records, stats = parse_stream(obj["Body"], max_close=max_close, min_close=min_close)
    return key, records, stats


def load_latest(s3_client, *, bucket: str, prefix: str, anchor: date, lookback_days: int, max_close: float, min_close: float):
    last_error = None
    for offset in range(lookback_days + 1):
        trade_date = anchor - timedelta(days=offset)
        try:
            key, records, stats = load_for_date(
                s3_client,
                bucket=bucket,
                prefix=prefix,
                trade_date=trade_date,
                max_close=max_close,
                min_close=min_close,
            )
            return trade_date, key, records, stats
        except Exception as exc:  # noqa: BLE001
            if _is_missing_object_error(exc):
                last_error = exc
                continue
            raise
    if last_error is not None:
        raise last_error
    raise FileNotFoundError("No flat file found in lookback window")


def _first(row: dict[str, str], *keys: str) -> str | None:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return None


def _parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _is_missing_object_error(exc: Exception) -> bool:
    if isinstance(exc, (FileNotFoundError, KeyError)):
        return True
    response = getattr(exc, "response", None)
    if not isinstance(response, dict):
        return False
    code = str(response.get("Error", {}).get("Code", ""))
    return code in {"404", "NoSuchKey", "NotFound"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate direct Polygon flat-file universe loading")
    parser.add_argument("--date", help="Trading date in YYYY-MM-DD format")
    parser.add_argument("--latest", action="store_true", help="Find latest available flat file in lookback window")
    parser.add_argument("--lookback-days", type=int, default=7, help="Lookback window for --latest")
    parser.add_argument("--bucket", default=_env_str("POLYGON_FLATFILES_BUCKET", "flatfiles"))
    parser.add_argument("--prefix", default=_env_str("POLYGON_DAY_AGGREGATE_PREFIX", "us_stocks_sip/day_aggs_v1"))
    parser.add_argument("--max-close", type=float, default=_env_float("UNIVERSE_MAX_PRICE", 10.0))
    parser.add_argument("--min-close", type=float, default=_env_float("UNIVERSE_MIN_PRICE", 1.0))
    parser.add_argument("--show-tickers", action="store_true", help="Print the filtered ticker list")
    args = parser.parse_args()
    if not args.date and not args.latest:
        parser.error("provide either --date YYYY-MM-DD or --latest")
    return args


def main() -> int:
    args = parse_args()
    s3_client = get_s3_client()
    try:
        if args.latest:
            trade_date, key, records, stats = load_latest(
                s3_client,
                bucket=args.bucket,
                prefix=args.prefix,
                anchor=datetime.now(timezone.utc).date(),
                lookback_days=args.lookback_days,
                max_close=args.max_close,
                min_close=args.min_close,
            )
        else:
            trade_date = date.fromisoformat(args.date)
            key, records, stats = load_for_date(
                s3_client,
                bucket=args.bucket,
                prefix=args.prefix,
                trade_date=trade_date,
                max_close=args.max_close,
                min_close=args.min_close,
            )
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"trade_date={trade_date.isoformat()}")
    print(f"s3_key={key}")
    print(f"total_rows={stats.total_rows}")
    print(f"valid_rows={stats.valid_rows}")
    print(f"filtered_rows={stats.filtered_rows}")
    print(f"skipped_rows={stats.skipped_rows}")

    if records:
        closes = [record["close"] for record in records]
        print(f"min_close={min(closes):.4f}")
        print(f"max_close={max(closes):.4f}")
    else:
        print("min_close=n/a")
        print("max_close=n/a")

    if args.show_tickers:
        for record in records:
            print(record["ticker"])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
