#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from datetime import date
from pathlib import Path


def env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    return default if value in (None, "") else value


def build_key(trade_date: date, prefix: str) -> str:
    return f"{prefix}/{trade_date.year:04d}/{trade_date.month:02d}/{trade_date.isoformat()}.csv.gz"


def build_local_filename(kind: str, trade_date: date) -> str:
    return f"{kind}_aggs_v1_{trade_date.isoformat()}.csv.gz"


def get_s3_client(endpoint_url: str):
    try:
        import boto3
    except ImportError as exc:
        raise SystemExit("boto3 is required to download Polygon flatfiles") from exc

    return boto3.client("s3", endpoint_url=endpoint_url)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download Polygon flatfiles from the configured flatfiles bucket."
    )
    parser.add_argument("--date", required=True, help="Trade date in YYYY-MM-DD format")
    parser.add_argument(
        "--kind",
        choices=("day", "am"),
        required=True,
        help="Flatfile type to download",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory to save the downloaded .csv.gz file into",
    )
    parser.add_argument(
        "--bucket",
        default=env_str("POLYGON_FLATFILES_BUCKET", "flatfiles"),
        help="Polygon flatfiles bucket name",
    )
    parser.add_argument(
        "--endpoint-url",
        default=env_str("POLYGON_FLATFILES_ENDPOINT_URL", "https://files.massive.com"),
        help="Polygon flatfiles endpoint URL",
    )
    parser.add_argument(
        "--prefix",
        default=None,
        help="Override the flatfile prefix directly",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    trade_date = date.fromisoformat(args.date)

    default_prefixes = {
        "day": env_str("POLYGON_DAY_AGGREGATE_PREFIX", "us_stocks_sip/day_aggs_v1"),
        "am": env_str("POLYGON_AM_AGGREGATE_PREFIX", "us_stocks_sip/am_aggs_v1"),
    }
    prefix = args.prefix or default_prefixes[args.kind]
    key = build_key(trade_date, prefix)

    output_dir = Path(args.output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / build_local_filename(args.kind, trade_date)

    s3 = get_s3_client(args.endpoint_url)
    s3.download_file(args.bucket, key, str(output_path))

    print(f"Downloaded s3://{args.bucket}/{key}")
    print(f"Saved to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
