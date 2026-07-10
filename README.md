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
config.py                  # credentials loading, ETF universe, defaults
data/
  client.py                # thin PyKis wrapper + caching + synthetic fallback
  synthetic.py             # deterministic demo data generator
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
asserting alignment, no-lookahead timing, and metric sanity.
