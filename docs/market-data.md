# Twelve Data adapter

The handoff supplied the adapter, synthetic scenarios and Advisor cases. This
development copy integrates them with the A service, connection settings and Agent.
Original handoff notes are retained in [the reference copy](reference/market-data-handoff.md).

## Interface

- `get_market_quote(symbol)`: one ticker, latest available provider quote.
- `get_external_price_history(symbol, start_date, end_date)`: daily split-adjusted
  closes, ascending, within inclusive YYYY-MM-DD bounds.

Responses include status, source, symbol, currency and timing/range fields. Errors
are normalized without echoing provider messages or keys. The adapter uses a bounded
request and has no fixture fallback, automatic retries or gap filling.

The quote bar date is distinct from retrieval time and provider last-quote time.
`timeliness=unverified` remains explicit. A successful call does not establish real-time
entitlement. Split-adjusted history excludes dividend reinvestment and is not total return.
The client range limit is 3,650 calendar days; it does not promise that much account coverage.

To preserve inclusive end dates, daily requests use full exchange-local day boundaries
and still filter normalized rows locally. The earlier correction is documented in
[handoff verification](reference/handoff-verification.md).

## Configuration and manual checks

Configure Twelve Data through **Connections → Market data**. The optional shell
variable is `TWELVE_DATA_API_KEY`; `.env.example` also includes it. Saved UI overrides
take precedence in supported standalone commands.

```powershell
.\.venv\Scripts\python.exe scripts/check_market_data.py --symbol AAPL
.\.venv\Scripts\python.exe scripts/check_market_data.py --symbol SPY --start 2026-10-26 --end 2026-10-30
```

These commands make real requests. Ordinary tests intercept provider transport.
The 2026-11-02 audit verified all ten holding symbols plus SPY, and AAPL/SPY daily
history. This is observed account coverage, not a general promise for all symbols,
funds, history ranges or subscription tiers. See the [live audit](reports/live-audit-2026-11-02.md).

Provider documentation: [Quote](https://twelvedata.com/docs/market-data/quote),
[Time series](https://twelvedata.com/docs/market-data/time-series),
[API keys](https://twelvedata.com/account/api-keys).
