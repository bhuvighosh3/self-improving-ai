"""Offline integrity tests using deliberately corrupted copies of the fixtures."""

from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "portfolio_validator", ROOT / "scripts/validate_portfolio_data.py"
)
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class PortfolioDataTests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / "work"
        scratch.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=scratch)
        assert Path(self.temporary.name).resolve().is_relative_to(scratch.resolve())
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.data = self.root / "src/self_improving_ai/data"
        shutil.copytree(ROOT / "src/self_improving_ai/data/portfolio", self.data / "portfolio")
        (self.data / "clients").mkdir()
        shutil.copy2(ROOT / "src/self_improving_ai/data/clients/households.json",
                     self.data / "clients/households.json")

    def edit(self, name, mutation):
        path = self.data / "portfolio" / name
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
        mutation(doc)
        path.write_text(json.dumps(doc), encoding="utf-8")

    def assert_rejected(self, fragment):
        result = validator.validate_project(self.root)
        self.assertEqual(result["status"], "error", result)
        self.assertTrue(any(fragment in error for error in result["errors"]), result)

    def test_original_data_covers_five_clients_ten_assets_fifteen_cases(self):
        result = validator.validate_project(self.root)
        self.assertEqual(result["status"], "success", result)
        self.assertEqual((result["client_count"], result["ticker_count"], result["case_count"]),
                         (5, 10, 15))
        self.assertTrue(any("withdrawals" in warning for warning in result["warnings"]))

    def test_missing_asset(self):
        self.edit("asset_class_map.json", lambda d: d["assets"].pop("AAPL"))
        self.assert_rejected("Asset coverage")

    def test_invalid_asset_class(self):
        self.edit("asset_class_map.json",
                  lambda d: d["assets"]["AAPL"].update(asset_class="ETF"))
        self.assert_rejected("invalid asset class")

    def test_unknown_client(self):
        self.edit("target_allocations.json",
                  lambda d: d["allocations"][0].update(client_id="CLI-999"))
        self.assert_rejected("coverage")

    def test_duplicate_client(self):
        self.edit("target_allocations.json",
                  lambda d: d["allocations"].append(d["allocations"][0]))
        self.assert_rejected("duplicate client_id")

    def test_wrong_weight_sum(self):
        self.edit("target_allocations.json",
                  lambda d: d["allocations"][0]["weights"].update(stock=.7))
        self.assert_rejected("summing to 1")

    def test_percent_instead_of_decimal(self):
        self.edit("target_allocations.json",
                  lambda d: d["allocations"][0].update(weights={"stock": 60, "bond": 40}))
        self.assert_rejected("decimals")

    def test_boolean_weight_is_not_numeric(self):
        self.edit("target_allocations.json",
                  lambda d: d["allocations"][0].update(weights={"stock": True, "bond": 0}))
        self.assert_rejected("decimals")

    def test_negative_contribution(self):
        self.edit("financial_goals.json",
                  lambda d: d["goals"][0].update(annual_contribution=-1))
        self.assert_rejected("annual_contribution")

    def test_missing_units(self):
        self.edit("financial_goals.json", lambda d: d.pop("currency"))
        self.assert_rejected("Goal units")

    def test_fractional_horizon(self):
        self.edit("financial_goals.json", lambda d: d["goals"][0].update(years=1.5))
        self.assert_rejected("years must")

    def test_non_finite_json(self):
        path = self.data / "portfolio/financial_goals.json"
        path.write_text('{"target_amount": NaN}', encoding="utf-8")
        self.assert_rejected("Non-finite")

    def test_duplicate_json_key(self):
        path = self.data / "portfolio/target_allocations.json"
        path.write_text('{"scope":"x", "scope":"y"}', encoding="utf-8")
        self.assert_rejected("Duplicate JSON key")

    def test_missing_file(self):
        (self.data / "portfolio/financial_goals.json").unlink()
        self.assert_rejected("financial_goals.json")

    def test_unknown_case_client(self):
        self.edit("portfolio_advisor_cases.json",
                  lambda d: d["cases"][0].update(client_id="CLI-999"))
        self.assert_rejected("unrecognized client_id")

    def test_duplicate_case_id(self):
        self.edit("portfolio_advisor_cases.json",
                  lambda d: d["cases"][1].update(case_id=d["cases"][0]["case_id"]))
        self.assert_rejected("unique")

    def test_invalid_demo_reference(self):
        self.edit("portfolio_advisor_cases.json",
                  lambda d: d.update(demo_case_ids=["A-001", "A-999"]))
        self.assert_rejected("demo case IDs")

    def test_demo_needs_external_api_case(self):
        self.edit("portfolio_advisor_cases.json",
                  lambda d: d.update(demo_case_ids=["A-001", "A-008"]))
        self.assert_rejected("external API")


if __name__ == "__main__":
    unittest.main()
