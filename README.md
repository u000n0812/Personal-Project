# Korean-Market Quant Dashboard + Commodity ETF Backtester

A local Streamlit app for monitoring a Korean-equity portfolio (KIS Open API via
PyKis) and backtesting commodity-ETF strategies. Strategy logic is pluggable —
drop in your own signal function without touching the UI, data layer, or engine.

## Quick start

```bash
pip install -r requirements.txt
streamlit run app.py
```

That's it — with no API keys the app runs in **synthetic-data mode**: a
deterministic demo dataset (seeded per ticker) drives every page, including the
backtester. For live data:

```bash
cp .env.example .env   # then fill in APP_KEY, APP_SECRET, ACCOUNT_NO, KIS_ID
```

Credentials are only ever read from `.env` (see `config.py`); the sidebar shows
which data source is active and has a "force synthetic" toggle.

## Project layout

```
app.py                     # entry point (streamlit run app.py)
config.py                  # credentials, ETF + screening universes, defaults
data/
  client.py                # thin PyKis wrapper + caching + synthetic fallback
  fundamentals.py          # fundamentals file loader (+ synthetic fallback)
  synthetic.py             # deterministic demo data generator
  providers/               # market-data providers: Yahoo+FDR (free), synthetic
  snapshot.py              # daily top-N peer snapshots (CLI: python -m data.snapshot)
  company.py               # Streamlit caching, KIS quote override, fallbacks
factors/
  definitions.py           # factor catalogue: groups, inputs, units, direction
  price.py                 # trailing returns + trend-aligned price momentum
  scoring.py               # percentile scoring + leader classification (pure)
  pipeline.py              # glue: fetch data → score (shared by pages 1 & 3)
  company.py               # score one company against its market's peers (pure)
strategies/
  __init__.py              # THE plug-in contract + registry (STRATEGIES dict)
  tsmom.py                 # reference: time-series momentum
  carry.py                 # reference: carry (placeholder proxy, see TODO)
backtest/
  engine.py                # vectorized engine — strategy-agnostic
  metrics.py               # CAGR, Sharpe, MDD, vol, hit ratio
pages/
  1_Portfolio_Dashboard.py
  2_Commodity_ETF_Backtester.py
  3_Market_Leaders.py
  4_Company_Analysis.py
ui/theme.py                # chart palette, Plotly template, shared chrome
ui/factor_charts.py        # sub-factor chart shared by pages 3 & 4
tests/smoke_test.py        # engine + leader-screen checks (python -m tests.smoke_test)
tests/test_company.py      # Yahoo parsing, freshness, ranking, snapshots (offline)
```

## Swapping in your own strategy

Write one pure function with this exact signature (full contract in
`strategies/__init__.py`):

```python
# strategies/my_strategy.py
import pandas as pd

def compute_signal(prices: pd.DataFrame, params: dict) -> pd.Series:
    """prices: single-asset daily history (guaranteed 'close' column).
    Return desired exposure per day: +1 long, -1 short, 0 flat,
    fractional = conviction. Use only data up to each date (no lookahead —
    the engine applies a 1-day execution shift for you)."""
    ...
```

Register it and it appears in the backtester's strategy select box:

```python
# strategies/__init__.py
from strategies import my_strategy
STRATEGIES["My Strategy"] = my_strategy.compute_signal
```

The engine (`backtest/engine.py`) never imports a strategy — it consumes any
dates × tickers weights panel, so nothing else changes.

## Where to add real carry / roll-yield data

`strategies/carry.py` → `carry_score()` carries a marked `TODO(you)` block.
Today it resolves, in order: a `carry` column on the price frame (synthetic mode
provides one) → `params["carry"]` (a Series you supply) → a **placeholder**
moving-average-slope proxy that is explicitly *not* real carry. Replace it with
roll yield from the underlying futures curve (front/next contract prices) or the
issuer's roll schedule, returning an **annualized** rate so cross-sectional
ranking stays comparable.

## Market Leaders screen

`pages/3_Market_Leaders.py` ranks a stock universe on four factor groups and
flags **market leaders**: stocks that rank highly on *all four*, or
exceptionally on *at least one*.

| Group | Inputs |
|---|---|
| **Value** | earnings yield (E/P), dividend yield, book-to-market (B/P), cash-flow yield |
| **Growth** | fwd-12M revenue revision, fwd-12M op-margin change, fwd-12M EPS growth, long-term growth (ROE × retention) |
| **Momentum** | 1M EPS revision, price momentum (1/3/6/12M, trend-aligned), 3M foreign-ownership change |
| **Quality** | fwd-12M operating margin, ROE, ROIC, debt-to-equity (lower = better) |

**Scoring** (`factors/scoring.py`, pure pandas): every input is ranked into a
percentile across the universe, direction-adjusted so 100 = best. A group is
the mean of its inputs' percentiles, re-ranked. Then:

- **All-round leader** — every group ≥ 60th percentile (sidebar slider)
- **Standout leader** — any group ≥ 95th percentile (sidebar slider)

Price momentum averages the 1/3/6/12-month return ranks, then shrinks toward
neutral when the horizons disagree in direction. Tags add context:
*Operating leverage* (revenue and margin estimates both rising),
*Value-trap risk* (cheap with no growth/momentum confirmation),
*Speculative risk* (strong momentum on weak quality).

**Missing data:** a NaN input drops out of its own ranking only. A group
needs ≥ 50% of its inputs, otherwise it's blank, and a stock with a blank
group can't be all-round. Percentiles are relative to the screened universe.
In "holdings only" mode that means leaders *within your portfolio*.

The Portfolio Dashboard shows each holding's leader status and the share of
your portfolio in leaders, using the same scoring.

### Where to plug in real fundamentals

The KIS API doesn't provide forward-12M consensus estimates, so fundamentals
come from a **file you supply**: `data/fundamentals.csv` (or `.parquet`, or
any path in the `FUNDAMENTALS_PATH` env var). One row per stock:

```
ticker,name,earnings_yield,dividend_yield,book_to_market,cash_flow_yield,
fwd_revenue_revision,fwd_op_margin_change,fwd_eps_growth,long_term_growth,
payout_ratio,eps_revision_1m,foreign_own_chg_3m,fwd_op_margin,roe,roic,debt_to_equity
```

- All rates are fractions (`0.05` = 5%). `*_change`/`*_chg_*` columns hold
  percentage-point changes as fractions (`0.01` = +1pp).
- `ticker` is the 6-digit KRX code; leading zeros are restored if your export
  drops them. `long_term_growth` may be omitted: it's derived from `roe` and
  `payout_ratio`.
- When the file exists, **its tickers define the screening universe** (plus
  your holdings). Missing columns and uncovered tickers are reported on the page.
- Without a file, deterministic synthetic fundamentals are used, and the page
  says so prominently.

The full column reference (definitions, units, direction) is in the page's
*Methodology & data schema* expander and in `factors/definitions.py`. To add or
drop an input, edit `SUB_FACTORS` there; scoring and UI follow automatically.
For a live source, see the `TODO(you)` in `data/fundamentals.py`.

## Company Analysis (any KOSPI / NASDAQ company)

`pages/4_Company_Analysis.py`: pick any KOSPI or NASDAQ listing (searchable,
or type a ticker). The page fetches the company's latest price and
fundamentals, scores it on Value / Growth / Momentum / Quality, and ranks it
against the **300 largest companies in its market** (`PEER_TOP_N` in `.env`).
It shows the composite score, market rank, per-factor percentiles and ranks,
sector rank, leader status, and an input-by-input breakdown vs. the market median.

**Data — free, no API keys.** Listings come from FinanceDataReader (KRX
listing cache; Naver's NASDAQ ranking by market value). Prices, fundamentals
and analyst estimates come from Yahoo Finance via `yfinance`.

| | Source | Freshness |
|---|---|---|
| Price (with KIS keys in `.env`) | KIS quote | real-time |
| Price (no keys) | Yahoo | NASDAQ near real-time · KRX ~20 min delayed · previous close outside hours |
| Selected company's fundamentals | Yahoo, fetched live | cached 6h |
| Peers | daily Parquet snapshot | prices as of the snapshot date |

Each quote's own timestamp drives the freshness badge (Real-time / Intraday ·
N min delayed / Previous close), so the page never claims to be fresher than
the data is.

**Peer snapshots.** Ranking against a market needs every peer's fundamentals.
That's ~1,200 Yahoo requests per market, too many for each page load, so peers
are fetched once a day and saved to `data/snapshots/<market>/<date>.parquet`:

```bash
python -m data.snapshot --market KOSPI NASDAQ    # a few minutes per market
```

You can also use the sidebar's *Build snapshot* button. Suggested cron, KST:
`0 17 * * 1-5` for KOSPI and `0 7 * * 2-6` for NASDAQ. Rate-limited fetches
back off and retry. Companies that still fail are skipped and counted in the
snapshot metadata.

**Free-data proxies.** Free sources don't carry consensus *revision history*
or Korean foreign-ownership data, so these inputs differ from the
Market Leaders definitions. Each one is flagged in the page's *Note* column:

- Fwd-12M revenue revision → consensus revenue growth for next fiscal year
- Fwd-12M op-margin change → change over the last two fiscal years (trailing)
- Fwd-12M operating margin → trailing-12M operating margin
- Foreign ownership Δ (3M) → unavailable. Momentum is scored on the other two
  inputs (coverage rule).

Every peer uses the same proxies, so rankings stay like-for-like.

**Fallbacks.** If the listing sources are unreachable, the page uses
yesterday's snapshot companies, or failing that, synthetic demo data with a
prominent warning. A failed fetch for the selected company is shown as an
error, never filled with synthetic numbers.

**Swapping the data vendor:** implement the four methods in
`data/providers/base.py` (`listing`, `company`, `closes`, `quote`) and register
the class in `data/providers/__init__.py`. Scoring (`factors/company.py`) and
the page are vendor-agnostic.

## Placeholder ETF universe

`config.COMMODITY_ETFS` ships with example Korean-listed commodity ETF codes
**as placeholders** — verify or replace them before doing anything real. It is
the single source of truth for the backtester's pick list.

## Design notes

- **Missing data / alignment** (explicit policy, `data/client.py`): series are
  aligned on the union of trading days; gaps ≤ 5 days are forward-filled;
  longer gaps and pre-listing days stay NaN and the engine forces weight 0
  (non-investable) on those days.
- **No lookahead**: signals computed at close of day *t* earn returns from
  *t + 1*; costs are charged on turnover the day positions change.
- **Vectorized**: the engine is pure pandas column arithmetic — no per-row
  Python loops in the hot path.
- **Benchmark**: equal-weight buy-and-hold of the selected ETFs, bought at each
  asset's first available price, never rebalanced.
- **Colors**: gains red / losses blue per Korean market convention; values
  always carry explicit signs so color is never the only encoding.

## If Streamlit becomes limiting

The seams are already in place: `data/`, `strategies/`, and `backtest/` are
pure-Python modules with no Streamlit dependency in their logic (only caching
decorators in `data/client.py`). If you outgrow Streamlit — multi-user access,
auth, sub-second streaming quotes, or complex client-side interactivity — the
natural split is a **FastAPI** service exposing `data` + `backtest` as JSON
endpoints and a **Next.js** front end for the charts. Until then, Streamlit's
rerun-on-widget-change model is exactly the fast-iteration loop this project
wants.

## Sanity checks

```bash
python -m tests.smoke_test
```

Runs the synthetic generator through both reference strategies and the engine,
asserting alignment, no-lookahead timing, and metric sanity. It also checks the
leader screen: factor directions, negative-equity handling, the long-term-growth
derivation, both leader rules, the coverage rule, and trend agreement.
