# Data assumptions and calculation contract

All household data are synthetic. Fixture valuation dates are unspecified.
Targets and market inputs remain unapproved drafts, version `demo-stock-bond-v1`.

## Allocation

Holdings are aggregated across accounts, including repeated symbols. A stock/bond
classification produces current weights and target deviations in percentage points.
Hypothetical class adjustment = total fixture value × target weight − current class value.
Positive means add; negative means reduce. These are asset-class amounts, not orders
or a security-level trade list. An account filter illustrates the household target.

Garcia reference: USD 146,750 total; USD 117,200 stocks and USD 29,550 bonds.
Stock weight is 79.8637138%. Against 60/40, stock drift is 19.8637138 percentage
points and the hypothetical stock adjustment is USD −29,150.

## Risk and return

Annual arithmetic expected returns are 6% for stocks and 2.5% for bonds. Annual
volatilities are 18% and 6%, with 0.1 correlation. These are invented development
inputs, not estimates from current market history.

Expected return = `w @ mu`; volatility = `sqrt(w @ covariance @ w)`.
Weights, covariance dimensions, symmetry, finite values and positive semidefiniteness
are validated. This coarse model excludes security-specific risk.

## Goal projection

Projections use nominal USD, annual IID lognormal gross returns matched to simple-return
moments, constant current fixture stock/bond weights and end-year cash flows.
Depletion is absorbing: failed paths do not restart with future contributions.
Success requires no depletion and final assets at least equal to the target.

The output includes actual target, horizon, flows, median, p10/p90, depletion,
seed and a 95% Wilson interval for Monte Carlo sampling only. It does not measure
uncertainty in financial assumptions. Zero simulated successes do not prove impossibility.

Explicit overrides preserve zero. Omitted inputs retain draft defaults and their
sources. Limits are 120 years, 100,000 paths and 5 million path-years.

Material stored assumptions include Chen's eight-year goal versus a general 25-year
profile horizon, Okafor's invented home-goal deadline, and Patel's USD 50,400 annual
withdrawals. Outputs retain these conflicts and notes.

Taxes, fees, inflation, account access restrictions and sustainable-income optimization
are not modeled. Live quotes do not automatically revalue holdings or calibrate returns.
Five-point fixture prices cannot support reliable annual covariance estimates.
