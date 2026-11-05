"""Offline contract tests; every network request is intercepted."""

from __future__ import annotations

import copy
import io
import json
import os
import unittest
from datetime import datetime
from http.client import IncompleteRead
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse

from self_improving_ai.tools.portfolio import market_data_api as api

QUOTE = {
    "symbol": "AAPL", "currency": "USD", "datetime": "2026-09-30",
    "last_quote_at": 1790773200, "close": "123.45", "is_market_open": False,
}
HISTORY = {
    "meta": {"symbol": "AAPL", "currency": "USD"},
    "values": [{"datetime": "2026-09-03", "close": "103.50"},
               {"datetime": "2026-09-01", "close": "101.25"},
               {"datetime": "2026-09-02", "close": "102.00"}],
    "status": "ok",
}


def response(payload):
    data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    return io.BytesIO(data)


class MarketDataTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"TWELVE_DATA_API_KEY": "fake-offline-test-key"},
                              clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.transport_patch = patch.object(api, "urlopen")
        self.transport = self.transport_patch.start()
        self.addCleanup(self.transport_patch.stop)
        self.transport.side_effect = AssertionError("Unexpected request in offline test")

    def serve(self, payload):
        self.transport.side_effect = lambda *a, **kw: response(payload)

    def history(self, start="2026-09-01", end="2026-09-30"):
        return api.get_external_price_history("AAPL", start, end)

    def assert_error(self, result, code):
        self.assertEqual(result["status"], "error", result)
        self.assertEqual(result["error"]["code"], code, result)
        self.assertEqual(result["source"], "twelve_data")
        self.assertNotIn("prices", result)
        self.assertNotIn("price", result)

    def test_quote_normalization_and_secret_not_in_url(self):
        self.serve(QUOTE)
        result = api.get_market_quote(" aapl ")
        self.assertEqual(result["price"], 123.45)
        self.assertEqual(result["symbol"], "AAPL")
        self.assertEqual(result["currency"], "USD")
        self.assertEqual(result["as_of"], "2026-09-30")
        self.assertEqual(result["timeliness"], "unverified")
        self.assertEqual(result["last_quote_at_utc"], "2026-09-30T13:00:00+00:00")
        request = self.transport.call_args.args[0]
        self.assertNotIn("fake-offline-test-key", request.full_url)
        self.assertEqual(request.get_header("Authorization"), "apikey fake-offline-test-key")
        self.assertEqual(self.transport.call_args.kwargs["timeout"], 10)
        self.assertNotIn("fake-offline-test-key", json.dumps(result))

    def test_stock_and_etf_quotes(self):
        for symbol in ("AAPL", "SPY", "BND"):
            with self.subTest(symbol=symbol):
                self.serve({**QUOTE, "symbol": symbol})
                self.assertEqual(api.get_market_quote(symbol)["status"], "success")

    def test_missing_quote_timestamp_is_not_invented(self):
        payload = {k: v for k, v in QUOTE.items() if k != "last_quote_at"}
        self.serve(payload)
        self.assertIsNone(api.get_market_quote("AAPL")["last_quote_at_utc"])

    def test_history_sorted_numeric_and_adjusted(self):
        self.serve(HISTORY)
        result = self.history()
        self.assertEqual([p["date"] for p in result["prices"]],
                         ["2026-09-01", "2026-09-02", "2026-09-03"])
        self.assertEqual(result["count"], 3)
        self.assertEqual(result["price_type"], "split_adjusted_close")
        self.assertEqual(result["prices"][0]["close"], 101.25)
        query = parse_qs(urlparse(self.transport.call_args.args[0].full_url).query)
        self.assertEqual(query["adjust"], ["splits"])
        self.assertEqual(query["outputsize"], ["5000"])
        self.assertEqual(query["interval"], ["1day"])

    def test_history_bounds_are_inclusive_and_outliers_filtered(self):
        self.serve(HISTORY)
        result = self.history("2026-09-02", "2026-09-02")
        self.assertEqual(result["prices"], [{"date": "2026-09-02", "close": 102.0}])

    def test_exchange_end_day_is_included_with_provider_datetime_cutoff(self):
        # Reproduce a provider that compares daily closes against an exclusive
        # datetime cutoff. A date-only cutoff is midnight, before that day's close.
        available = [
            {"datetime": "2026-09-29", "close": "101"},
            {"datetime": "2026-09-30", "close": "102"},
            {"datetime": "2026-10-01", "close": "103"},
        ]

        def provider(request, **kwargs):
            params = parse_qs(urlparse(request.full_url).query)
            begin = datetime.fromisoformat(params["start_date"][0])
            cutoff = datetime.fromisoformat(params["end_date"][0])
            rows = [row for row in available
                    if begin <= datetime.fromisoformat(row["datetime"] + "T16:00:00") < cutoff]
            return response({"meta": HISTORY["meta"], "values": rows, "status": "ok"})

        self.transport.side_effect = provider
        for begin in ("2026-09-01", "2026-09-28", "2026-09-30"):
            with self.subTest(start=begin):
                result = self.history(begin, "2026-09-30")
                self.assertEqual(result["status"], "success", result)
                self.assertEqual(result["data_end"], "2026-09-30")
                self.assertEqual(result["end_date"], "2026-09-30")
                self.assertTrue(all(p["date"] <= "2026-09-30" for p in result["prices"]))

    def test_missing_dates_are_not_filled(self):
        payload = copy.deepcopy(HISTORY)
        del payload["values"][2]
        self.serve(payload)
        self.assertEqual(self.history()["count"], 2)

    def test_identical_duplicate_dates_are_deduplicated(self):
        payload = copy.deepcopy(HISTORY)
        payload["values"].append(payload["values"][0])
        self.serve(payload)
        self.assertEqual(self.history()["count"], 3)

    def test_conflicting_duplicate_dates_rejected(self):
        payload = copy.deepcopy(HISTORY)
        payload["values"].append({"datetime": "2026-09-01", "close": "999"})
        self.serve(payload)
        self.assert_error(self.history(), "INVALID_RESPONSE")

    def test_invalid_local_symbols_do_not_query(self):
        for value in ("", "  ", "AAPL,SPY", "AAPL&apikey=bad", None, 3, "../AAPL"):
            with self.subTest(value=value):
                self.assert_error(api.get_market_quote(value), "INVALID_SYMBOL")
                self.assert_error(api.get_external_price_history(value, "2026-09-01",
                                                                 "2026-09-30"), "INVALID_SYMBOL")
        self.transport.assert_not_called()

    def test_missing_key_does_not_query_or_fallback(self):
        os.environ.pop("TWELVE_DATA_API_KEY")
        self.assert_error(api.get_market_quote("AAPL"), "MISSING_API_KEY")
        self.assert_error(self.history(), "MISSING_API_KEY")
        self.transport.assert_not_called()

    def test_invalid_key_header_characters(self):
        os.environ["TWELVE_DATA_API_KEY"] = "key\ninjected"
        self.assert_error(api.get_market_quote("AAPL"), "INVALID_API_KEY")
        self.transport.assert_not_called()

    def test_invalid_dates_do_not_query(self):
        for value in ("2026-02-30", "2026-9-01", "20260901", "", None, "2026-09-01T12:00"):
            with self.subTest(value=value):
                self.assert_error(self.history(value), "INVALID_DATE")
        self.transport.assert_not_called()

    def test_reversed_dates_do_not_query(self):
        self.assert_error(self.history("2026-09-30", "2026-09-01"), "INVALID_DATE_RANGE")
        self.transport.assert_not_called()

    def test_oversize_date_range_does_not_query(self):
        self.assert_error(self.history("2000-01-01", "2026-09-30"), "DATE_RANGE_TOO_LARGE")
        self.transport.assert_not_called()

    def test_provider_symbol_error_even_on_http_200(self):
        self.serve({"status": "error", "code": 400,
                    "message": "symbol is invalid or not found fake-offline-test-key"})
        result = api.get_market_quote("NOSUCHSYMBOL")
        self.assert_error(result, "SYMBOL_NOT_FOUND")
        self.assertNotIn("fake-offline-test-key", json.dumps(result))

    def test_provider_error_codes_in_response_body(self):
        for code, expected in ((401, "AUTHENTICATION_FAILED"), (403, "ACCESS_DENIED"),
                               (404, "NO_DATA"), (429, "RATE_LIMITED"),
                               (500, "PROVIDER_UNAVAILABLE"), (400, "INVALID_REQUEST")):
            with self.subTest(code=code):
                self.serve({"status": "error", "code": code, "message": "Provider error"})
                result = self.history()
                self.assert_error(result, expected)
                self.assertEqual(result["error"]["provider_code"], code)

    def test_http_errors_and_retryability(self):
        for code, expected in ((401, "AUTHENTICATION_FAILED"), (403, "ACCESS_DENIED"),
                               (404, "NO_DATA"), (429, "RATE_LIMITED"),
                               (503, "PROVIDER_UNAVAILABLE")):
            with self.subTest(code=code):
                self.transport.side_effect = HTTPError(
                    "https://api.twelvedata.com/quote", code, "error", {},
                    io.BytesIO(b'{"message": "private provider message"}'))
                result = api.get_market_quote("AAPL")
                self.assert_error(result, expected)
                self.assertEqual(result["error"]["retryable"], code in (429, 503))

    def test_http_error_with_invalid_body(self):
        self.transport.side_effect = HTTPError(
            "https://api.twelvedata.com/quote", 429, "error", {}, io.BytesIO(b"<html>"))
        self.assert_error(self.history(), "RATE_LIMITED")

    def test_network_timeout(self):
        for exc in (TimeoutError("secret"), URLError(TimeoutError("secret"))):
            with self.subTest(exc=type(exc).__name__):
                self.transport.side_effect = exc
                self.assert_error(api.get_market_quote("AAPL"), "TIMEOUT")
        self.assertEqual(self.transport.call_count, 2)  # No automatic retry.

    def test_network_failure(self):
        self.transport.side_effect = URLError("private URL")
        self.assert_error(self.history(), "NETWORK_ERROR")

    def test_incomplete_network_response(self):
        self.transport.side_effect = IncompleteRead(b"partial", 20)
        self.assert_error(self.history(), "NETWORK_ERROR")

    def test_no_data(self):
        for payload in ({}, {"values": []}, {"meta": HISTORY["meta"], "values": None}):
            with self.subTest(payload=payload):
                self.serve(payload)
                self.assert_error(self.history(), "NO_DATA")
        self.serve({})
        self.assert_error(api.get_market_quote("AAPL"), "NO_DATA")

    def test_no_rows_in_requested_dates(self):
        self.serve(HISTORY)
        self.assert_error(self.history("2026-09-10", "2026-09-12"), "NO_DATA")

    def test_malformed_json_and_wrong_response_types(self):
        for payload in (b"{bad", b"\xff", [], "text"):
            with self.subTest(payload=payload):
                self.serve(payload)
                self.assert_error(api.get_market_quote("AAPL"), "INVALID_RESPONSE")

    def test_bad_prices_rejected(self):
        for value in ("NaN", "Infinity", "-1", "0", True, {}, []):
            with self.subTest(value=value):
                self.serve({**QUOTE, "close": value})
                self.assert_error(api.get_market_quote("AAPL"), "INVALID_RESPONSE")

    def test_missing_or_mismatched_metadata(self):
        for changes in ({"currency": None}, {"symbol": "SPY"}, {"datetime": "bad"},
                        {"last_quote_at": "nan"}, {"is_market_open": "false"}):
            with self.subTest(changes=changes):
                self.serve({**QUOTE, **changes})
                self.assert_error(api.get_market_quote("AAPL"), "INVALID_RESPONSE")

    def test_malformed_history_rows(self):
        for rows in ("not a list", [None], [{"datetime": "bad", "close": "1"}],
                     [{"datetime": "2026-09-01", "close": "NaN"}]):
            with self.subTest(rows=rows):
                self.serve({**HISTORY, "values": rows})
                self.assert_error(self.history(), "INVALID_RESPONSE")

    def test_history_requires_currency_and_matching_symbol(self):
        for metadata in (None, {}, {"symbol": "SPY", "currency": "USD"},
                         {"symbol": "AAPL"}):
            with self.subTest(metadata=metadata):
                self.serve({**HISTORY, "meta": metadata})
                self.assert_error(self.history(), "INVALID_RESPONSE")


if __name__ == "__main__":
    unittest.main()
