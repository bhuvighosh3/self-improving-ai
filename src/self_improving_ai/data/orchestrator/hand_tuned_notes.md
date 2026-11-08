## Additional guidance (hand-tuned baseline)
- Tax questions need lot-level data: use get_holdings_v2 before asking the portfolio agent for tax_impact or tax_loss_harvest.
- Prices: stocks and ETFs use get_intraday_price; mutual funds use get_fund_nav and the answer must mention the as-of date.
- Outreach after a market event: get_market_event, then compute_book_exposure, then triage_clients, then draft_client_note for the clients triage returns.
- When drafting any client note while a market event is live, call get_market_event first so the note can reference it.
- Rate shocks are passed in basis points (shock_bps=25 for 0.25%).
