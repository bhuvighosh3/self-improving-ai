> Archived team/handoff reference. This describes its original design or historical state. For current implementation and verification, start with the project README.

# Component A market data starter

This extension supplies standalone market-data tools, supplemental synthetic scenarios,
offline tests, and Advisor question specifications for the Component A owner to integrate.
The existing Agent and financial calculation tools have not been extended here.

## Current verification

- 49 offline unit tests passed in the bundled Python 3.13 runtime.
- Data validation passed: 5 clients, 10 holding symbols, 15 Advisor cases.
- Missing-key CLI behavior was verified without a network request.
- AAPL quote succeeded in the user's local CLI run; the pasted output is saved in
  examples/reported_aapl_quote_20261030T195900Z.json. This was not independently rerun.
- SPY quote succeeded; the saved JSON was inspected.
- All four basic live checks passed in the user's local environment: AAPL/SPY
  quotes and AAPL/SPY daily history. After the end-day correction, each history
  file contains 21 ascending unique daily rows from September 1 through 30, 2026.
- Saved dates, counts, currency and positive finite numeric closes were checked.
  The date-boundary correction is also covered by offline regression tests.
- Fund permissions, complete history coverage, account plan and latency remain unverified.
- No real account connection, orders, remote Git operations, or email delivery.

## Run without installing the full application

Use Python 3.11 or later. The adapter, validator and unittest suite use only the
Python standard library; they do not require Gemini, Google ADK, Node, or a dashboard.

From the project root in PowerShell:

    python scripts/validate_portfolio_data.py
    $env:PYTHONPATH = (Join-Path (Get-Location) "src")
    python -m unittest discover -s tests/test_tools -v

Exit status: 0 for success, 1 for validation or API errors, 2 for CLI usage errors.
The validator's scenario-confirmation warnings are expected and do not approve the scenarios.
Tests intercept all outbound market-data requests and use fabricated prices.

## Configure the provider key locally

This implementation uses Twelve Data. Create your own account at
https://twelvedata.com and use its dashboard to obtain a key. Never put a real key
in source files, output examples, or an email attachment.

Option 1, environment variable, no package installation needed:

    $env:TWELVE_DATA_API_KEY = "YOUR_OWN_KEY"
    python scripts/check_market_data.py --symbol AAPL

Option 2, a local dotenv file, using the project's existing python-dotenv dependency:

    python -m pip install python-dotenv
    Copy-Item market_data.env.example .env.market_data

Edit .env.market_data locally, then run:

    python scripts/check_market_data.py --env-file .env.market_data --symbol AAPL

The script reads only TWELVE_DATA_API_KEY from that file. An already-set nonempty
environment variable takes precedence. The adapter functions themselves read the
environment and do not implicitly load files. No dependency configuration was changed.
The copy's .gitignore excludes .env.* files. Do not include them when packaging.

## Reproduce the four completed basic live checks

These checks have already succeeded. The commands are retained for reproduction.
Each command below makes one real provider request. Run them separately and inspect
the status; do not substitute local fixtures if a symbol or plan is unsupported.

    python scripts/check_market_data.py --symbol AAPL --output examples/live_aapl_quote.json
    python scripts/check_market_data.py --symbol SPY --output examples/live_spy_quote.json
    python scripts/check_market_data.py --symbol AAPL --start 2026-09-01 --end 2026-09-30 --output examples/live_aapl_history.json
    python scripts/check_market_data.py --symbol SPY --start 2026-09-01 --end 2026-09-30 --output examples/live_spy_history.json

If using a dotenv file, append --env-file .env.market_data to each command.
Choose another completed date range if needed. Record outcomes in
LIVE_VERIFICATION.md. Quotes report the provider's available data, not a guarantee
of real-time or consolidated exchange coverage.

Provider choice and published limitations, reviewed 2026-10-30:

- The adapter uses /quote and /time_series, both documented at 1 credit per symbol.
- The official Basic pricing page lists 8 API credits per minute and 800 per day.
  The Basic daily quota resets at midnight UTC according to the credits guide.
- Official product pages advertise US stock/ETF availability. Access to a specific
  symbol, date range, or fund still needs testing with the actual account.
- The pricing page lists mutual-fund NAV under Pro. Do not assume that VTSAX/VTIAX
  are accessible with Basic; a 403 is ACCESS_DENIED, not permission to substitute an ETF.
- The adapter does not automatically retry, cache, or fill missing dates. A rate-limit
  error is retryable by the caller after checking the applicable minute/daily quota.
- Its initial history range is capped at 3650 elapsed calendar days per request.
  This is a client-side safety limit, not a claim about the provider's available history.

Official sources:
https://twelvedata.com/docs
https://twelvedata.com/pricing
https://support.twelvedata.com/en/articles/5615854-credits

## Tool contract

Module: src/self_improving_ai/tools/portfolio/market_data_api.py

    get_market_quote(symbol: str) -> dict
    get_external_price_history(symbol: str, start_date: str, end_date: str) -> dict

Inputs accept one US-style stock/fund ticker, stripped and uppercased, including
dots and hyphens. Batches and other asset types are outside this starter's scope.
Date strings must be valid YYYY-MM-DD values; both date bounds are inclusive.
Provider requests use exchange-local T00:00:00 and T23:59:59 boundaries
to avoid dropping the ending day's close with a date-only midnight cutoff.
Invalid inputs are rejected before any provider request.

Quote success fields:
status, symbol, price (positive finite float), currency, as_of, source,
price_type, bar_date, last_quote_at_utc, is_market_open, timeliness,
retrieved_at_utc, warnings.

as_of/bar_date are the daily bar's exchange-local date. They are NOT the fetch time.
last_quote_at_utc, when supplied, is the provider's last-minute-candle timestamp.
timeliness stays unverified; market-open status does not prove real-time access.
No previous-close or local-price fallback is used.

History success fields:
status, symbol, currency, source, start_date, end_date, interval,
price_type, adjustment, prices [{date, close}], data_start, data_end,
count, retrieved_at_utc, warnings.

History requests explicitly use adjust=splits. split_adjusted_close is not a
dividend-reinvested total-return series. Returned dates are sorted, identical duplicates
are collapsed, and conflicting same-date prices are errors. Rows outside the requested
bounds are filtered. Missing trading sessions and a partially formed current-day bar
remain the calculation owner's responsibility.

Error shape:

    {
      "status": "error",
      "source": "twelve_data",
      "symbol": "AAPL",
      "error": {
        "code": "MISSING_API_KEY",
        "message": "Set TWELVE_DATA_API_KEY before querying.",
        "retryable": false
      }
    }

Error codes include INVALID_SYMBOL, INVALID_DATE, INVALID_DATE_RANGE,
DATE_RANGE_TOO_LARGE, MISSING_API_KEY, INVALID_API_KEY, AUTHENTICATION_FAILED,
ACCESS_DENIED, SYMBOL_NOT_FOUND, NO_DATA, TIMEOUT, NETWORK_ERROR, RATE_LIMITED,
PROVIDER_UNAVAILABLE, INVALID_REQUEST, INVALID_RESPONSE and INCOMPLETE_DATA.
Provider errors are recognized in HTTP failures and JSON error bodies.
Ambiguous provider 404s map to NO_DATA; SYMBOL_NOT_FOUND requires explicit provider text.
Provider messages and exception details are not exposed because they can echo secrets.
Requests use a 10-second timeout and header authentication.

examples/offline_contract_examples.json contains normalized success/error examples
generated with an intercepted transport and invented prices. It is NOT real API evidence.

## Supplemental data fields

All four JSON files are under src/self_improving_ai/data/portfolio/.
households.json and the original price fixture were not changed.

| File | Main fields | Meaning |
| --- | --- | --- |
| asset_class_map.json | assets[ticker].asset_class, instrument_type | Coarse underlying stock/bond exposure; ETF is a wrapper, not an asset class |
| target_allocations.json | allocations[].client_id, weights | All-account client targets, decimal weights summing to 1 |
| financial_goals.json | goals[].client_id, goal_type, target_amount, years, annual_contribution, annual_withdrawal, assumption | Nominal USD scenario; cash flows in USD/year at year end |
| portfolio_advisor_cases.json | cases[], demo_case_ids | 15 English question specifications; expected tools, data and outputs |

Targets and goals are draft synthetic scenarios, not facts inferred from client risk labels.
Every invented parameter is marked in assumption text. Starting portfolio values use the
sum of fixture market_value values. Do not mix those with today's quotes silently.
No market_assumptions.json was created: return, volatility, covariance, inflation
and projection-model choices must be agreed with the calculation owner first.

Specific owner decisions:
- CLI-003 uses the CRM's 8-year early-retirement horizon, despite a 25-year profile horizon.
- CLI-004's 3-year down-payment scenario is invented; it is not the 10-year general horizon.
- CLI-005 includes USD 50,400 annual withdrawals based on the CRM's monthly spend.
  Do not run it through a model that silently ignores withdrawals.
- Confirm whether goals operate across all accounts and whether restricted accounts
  can contribute to a goal. Account access/tax rules are not modeled by these scenarios.

## Demo questions and integration

1. A-001: Garcia holdings. The existing get_holdings tool can run this now.
2. A-003: AAPL quote for Garcia's holding. The independent CLI is ready; real
   provider access still needs a key and live verification.
3. A-008: Garcia versus the illustrative 60/40 target. Question/data are ready;
   calculation and Agent integration remain pending the owner.

The cases are specifications, not an executing Agent evaluation harness.
OWNER_PENDING:* names are descriptive placeholders, not implemented functions.
Financial results are deliberately not hard-coded into question expectations.

Once the owner is ready, import the two tool functions and add them to their
standalone Agent's tools list. Agree symbol/ticker naming, output shape and error
handling first. This copy does not change Agent instructions or register new tools.

Local dotenv variants were added to .gitignore. Existing fixture loader fixes: pricing.py now resolves
data/prices/price_history.json under self_improving_ai/data rather than src/data.
Fixture regression tests verify AAPL prices and Garcia holdings can be read. Both existing loaders now read JSON explicitly as UTF-8, fixing a Windows default-encoding failure on the household fixture. Existing period selection
behavior is unchanged: the local mock tool still returns the full small fixture.

## Files and handoff status

New source: market_data_api.py
New scripts: check_market_data.py, validate_portfolio_data.py
New tests: test_market_data_api.py, test_portfolio_data.py, test_local_pricing.py
New data: asset_class_map.json, target_allocations.json, financial_goals.json,
portfolio_advisor_cases.json
Other additions: market_data.env.example, this README, LIVE_VERIFICATION.md,
examples/offline_contract_examples.json, examples/offline_validation_report.json,
examples/offline_test_report.txt, CHANGE_MANIFEST.json.

The original source folder is untouched. This is a local project copy with no
Git metadata or credentials. The accompanying ZIP excludes Python caches, work
directories, real dotenv files and node_modules. Only the scoped offline suite was
run; no claim is made about the dashboard, full project suite or Agent integration.
