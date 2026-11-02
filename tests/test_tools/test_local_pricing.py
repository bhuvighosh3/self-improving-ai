"""Regression check that the existing local price tool reads the package fixture."""

import unittest

from self_improving_ai.tools.portfolio.pricing import get_price_history
from self_improving_ai.tools.portfolio.holdings import get_holdings


class LocalPricingTests(unittest.TestCase):
    def test_holdings_fixture_is_read_as_utf8_on_windows(self):
        result = get_holdings("CLI-001")
        self.assertEqual(len(result["accounts"]), 2)
        self.assertEqual(result["total_market_value"], 146750)
        self.assertEqual(result["accounts"][0]["account_id"], "ACC-001A")

    def test_existing_price_tool_returns_packaged_aapl_rows(self):
        result = get_price_history("AAPL")
        self.assertTrue(result["prices"], "Packaged AAPL prices should be found")
        self.assertTrue(all("date" in row and "close" in row for row in result["prices"]))


if __name__ == "__main__":
    unittest.main()
