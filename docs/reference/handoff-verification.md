> Archived team/handoff reference. This describes its original design or historical state. For current implementation and verification, start with the project README.

# Live provider verification

Status: ALL FOUR BASIC LIVE CHECKS PASSED, based on user output/files.
AAPL and SPY quotes succeeded; both corrected daily ranges include September 30.
The assistant inspected the saved results; it did not make authenticated requests.
Account plan and quote timeliness remain unverified.

| Check | Status | Evidence or remaining work |
| --- | --- | --- |
| AAPL quote | Success, user-reported | examples/reported_aapl_quote_20261030T195900Z.json |
| SPY quote | Success, saved result inspected | examples/live_spy_quote.json |
| AAPL daily history | Corrected inclusive interval verified | 21 rows, 2026-09-01 through 2026-09-30; examples/live_aapl_history.json |
| SPY daily history | Corrected inclusive interval verified | 21 rows, 2026-09-01 through 2026-09-30; examples/live_spy_history.json |
| VTSAX / VTIAX coverage | Pending account check | Success or explicit access/coverage error |
| Actual quote latency | Unverified | Account/feed entitlement and provider timing documentation |
| Earliest accessible historical date | Unverified | Actual symbol/account history check |
| Minute and daily quota | Published only | Account dashboard and observed error behavior |

## Date boundary correction

Initially both history requests asked for September 1 through September 30,
2026, but returned 20 valid sorted numeric rows ending September 29.
After the correction, both AAPL and SPY returned 21 rows ending September 30.
The assistant inspected both saved JSON files: counts, ascending unique dates,
requested boundaries, USD currency and positive finite numeric closes are consistent.
This verifies these two observed intervals, not every trading calendar or symbol.

Twelve Data's official guide illustrates that a date-only end_date can exclude
the daily price for that date:
https://support.twelvedata.com/en/articles/5214728-getting-historical-data

The adapter now sends start_date at T00:00:00 and end_date at T23:59:59 in
exchange-local time, and retains the inclusive local date filter.
Public function parameters and returned requested dates remain YYYY-MM-DD.
A regression test models a provider datetime cutoff and covers month, week
and single-day requests. All 49 offline tests passed after the correction.
The user reran both symbols successfully after the correction.
AAPL retrieved_at_utc: 2026-10-31T00:40:35.088986+00:00.
SPY retrieved_at_utc: 2026-10-31T00:42:58.143767+00:00.

Initial results were preserved unchanged in examples/history_before_end_date_fix/.
The four planned basic queries are complete. No repeat requests are needed
for this handoff. Fund coverage, latency and broader historical range are separate checks.

## Quote evidence

AAPL: USD 344.63; bar date 2026-10-30; provider last-minute-candle timestamp
2026-10-30T19:59:00+00:00; fetched 2026-10-31T00:31:08.265804+00:00.

SPY: USD 755.71997; bar date 2026-10-30; provider last-minute-candle timestamp
2026-10-30T19:59:00+00:00; fetched 2026-10-31T00:34:47.647081+00:00.

Both report is_market_open=false and timeliness=unverified.
Success does not establish real-time entitlement or other symbol permissions.

Account plan: not provided
Python version for user run: not provided
Owner confirmation of scenario data/contract: pending

Do not record keys or raw Authorization headers here.
Offline mocked examples do not prove live access.
