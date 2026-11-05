"""Manually query real market data. Never substitute mocked or local fixture prices."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from self_improving_ai.tools.portfolio.market_data_api import (  # noqa: E402
    get_external_price_history,
    get_market_quote,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default="AAPL")
    parser.add_argument("--start", help="Inclusive YYYY-MM-DD; requires --end")
    parser.add_argument("--end", help="Inclusive YYYY-MM-DD; requires --start")
    parser.add_argument("--output", type=Path, help="Optionally save normalized JSON")
    parser.add_argument("--env-file", type=Path,
                        help="Optional dotenv file; requires the project's python-dotenv package")
    args = parser.parse_args()
    if bool(args.start) != bool(args.end):
        parser.error("Provide both --start and --end, or neither for a quote")
    if args.env_file:
        if not args.env_file.is_file():
            parser.error("The --env-file path does not exist")
        try:
            from dotenv import dotenv_values
        except ImportError:
            parser.error("--env-file requires python-dotenv; alternatively set TWELVE_DATA_API_KEY")
        value = dotenv_values(args.env_file).get("TWELVE_DATA_API_KEY")
        if value and not os.environ.get("TWELVE_DATA_API_KEY"):
            os.environ["TWELVE_DATA_API_KEY"] = value
    from self_improving_ai.connection_store import restore_connections
    restore_connections()
    result = (get_external_price_history(args.symbol, args.start, args.end)
              if args.start else get_market_quote(args.symbol))
    rendered = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
