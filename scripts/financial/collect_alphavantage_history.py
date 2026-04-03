"""Fetch historical OHLCV data from Alpha Vantage REST API.

Usage:
    python scripts/financial/collect_alphavantage_history.py --symbols AAPL,MSFT --interval 5min
"""

import argparse
import os
import sys

from dotenv import load_dotenv
from loguru import logger

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from financial_transactions.config import HistoricalConfig
from financial_transactions.streaming.alphavantage_collector import AlphaVantageCollector


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Alpha Vantage Historical Data Collector")
    parser.add_argument("--symbols", type=str, default="AAPL,MSFT,GOOGL", help="Comma-separated symbols")
    parser.add_argument("--interval", type=str, default="5min", help="Data interval (1min, 5min, 15min, 30min, 60min)")
    parser.add_argument("--output-dir", type=str, default="./data/historical", help="Output directory")
    args = parser.parse_args()

    api_key = os.getenv("ALPHAVANTAGE_API_KEY", "")
    if not api_key:
        logger.error("ALPHAVANTAGE_API_KEY not set")
        sys.exit(1)

    config = HistoricalConfig(
        alphavantage_api_key=api_key,
        symbols=args.symbols.split(","),
        interval=args.interval,
    )

    os.makedirs(args.output_dir, exist_ok=True)

    collector = AlphaVantageCollector(config, spark=None, output_path=args.output_dir)
    df = collector.fetch_all_symbols()

    if not df.empty:
        output_file = os.path.join(args.output_dir, f"historical_{args.interval}.csv")
        collector.save_to_csv(df, output_file)
        logger.info(f"Saved {len(df)} records to {output_file}")
    else:
        logger.warning("No data fetched")


if __name__ == "__main__":
    main()
