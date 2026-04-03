"""Collect real-time trade data from Finnhub WebSocket.

Usage:
    python scripts/financial/collect_finnhub_stream.py --duration 60 --symbols AAPL,MSFT
"""

import argparse
import os
import sys

from dotenv import load_dotenv
from loguru import logger

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from financial_transactions.config import StreamingConfig
from financial_transactions.streaming.finnhub_collector import FinnhubCollector


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Finnhub WebSocket Trade Collector")
    parser.add_argument("--duration", type=int, default=60, help="Duration in seconds (0=forever)")
    parser.add_argument("--symbols", type=str, default="AAPL,MSFT,GOOGL", help="Comma-separated symbols")
    parser.add_argument("--output", type=str, default="./data/landing/trades", help="Output path")
    parser.add_argument("--batch-interval", type=int, default=30, help="Flush interval in seconds")
    args = parser.parse_args()

    api_key = os.getenv("FINNHUB_API_KEY", "")
    if not api_key:
        logger.error("FINNHUB_API_KEY not set")
        sys.exit(1)

    config = StreamingConfig(
        finnhub_api_key=api_key,
        finnhub_symbols=args.symbols.split(","),
        batch_interval_seconds=args.batch_interval,
        landing_zone_path=args.output,
    )

    os.makedirs(args.output, exist_ok=True)

    collector = FinnhubCollector(config, spark=None, output_path=args.output)

    logger.info(f"Starting collector: symbols={args.symbols}, duration={args.duration}s")
    duration = args.duration if args.duration > 0 else None
    collector.start(duration=duration)


if __name__ == "__main__":
    main()
