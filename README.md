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
factors/
  definitions.py           # factor catalogue: groups, inputs, units, direction
  price.py                 # trailing returns + trend-aligned price momentum
  scoring.py               # percentile scoring + leader classification (pure)
  pipeline.py              # glue: fetch data → score (shared by pages 1 & 3)
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
ui/theme.py                # chart palette, Plotly template, shared chrome
tests/smoke_test.py        # engine sanity checks (python -m tests.smoke_test)
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
