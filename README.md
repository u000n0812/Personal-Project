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
  fundamentals.py          # optional fundamentals override file
  synthetic.py             # deterministic demo data generator
  providers/               # market-data providers: Yahoo+FDR (free), synthetic
  snapshot.py              # daily top-N peer snapshots (CLI: python -m data.snapshot)
  indexes.py               # Nasdaq-100 membership (Nasdaq → Wikipedia → cache)
  company.py               # Streamlit caching, KIS quote override, fallbacks
factors/
  definitions.py           # factor catalogue: groups, inputs, units, direction
  price.py                 # trailing returns + trend-aligned price momentum
  scoring.py               # percentile scoring + leader classification (pure)
  pipeline.py              # glue: snapshots → scores (shared by pages 1, 3, 4, 5)
  company.py               # score a market (market- or sector-relative) or one company
  sector.py                # sector ETF performance + per-sector summaries (pure)
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
  5_Sector_ETFs.py
  6_Dictionary.py
  7_Sentiment.py
sentiment/
  model.py                 # readings, shrinkage, family-balanced composite, summary
  market.py                # market Fear & Greed (US, Korea) from price series
  price.py                 # price behavior relative to the market index
  text.py                  # headline/post tone (VADER + finance lexicon; Korean stems)
  sources.py               # StockTwits, Reddit, news, analysts, options, short, KIS flows
  engine.py                # orchestration (each source isolated)
  history.py               # daily records (data/sentiment/history.parquet)
  collect.py               # CLI: python -m sentiment.collect (cron a watchlist)
  synthetic.py             # demo readings
glossary/
  entries.py               # dictionary content (plain data: definition, formula, example…)
  __init__.py              # lookup + search (English, abbreviations, Korean)
ui/theme.py                # chart palette, Plotly template, shared chrome
ui/factor_charts.py        # sub-factor chart shared by pages 3 & 4
ui/snapshot_controls.py    # sidebar snapshot status + build button
ui/tables.py               # table search (ticker / English / Korean name)
ui/metric_views.py         # key-metric value columns per factor
tests/smoke_test.py        # engine + leader-screen checks (python -m tests.smoke_test)
tests/test_company.py      # Yahoo parsing, freshness, ranking, snapshots (offline)
tests/test_sectors.py      # sector ranking, search, ETF analytics, overrides (offline)
tests/test_nasdaq100.py    # Nasdaq-100 parsing/coverage, key-metric values (offline)
tests/test_glossary.py     # dictionary links, completeness, formulas, search
tests/test_sentiment.py    # sentiment parsers, aggregation, Fear & Greed, history
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

`pages/3_Market_Leaders.py` ranks **KOSPI and/or NASDAQ** stocks on four factor
groups and flags **market leaders**: stocks that rank highly on *all four*, or
exceptionally on *at least one*. The universe is the top-N companies by market
cap in each market, from the daily peer snapshots (see Company Analysis below),
plus your holdings. With **Both**, the two markets share one table, but each
stock is ranked only within its own market.

- **Universe: KOSPI | NASDAQ | Nasdaq-100 | Both.** The NASDAQ snapshot always
  includes **every Nasdaq-100 member**, even ones outside the top N. Members
  get an *NDX ✓* column. *Nasdaq-100* ranks just the index's 100 companies
  among themselves, one line per company (GOOG is folded into GOOGL).
  Membership is fetched when the snapshot is built: Nasdaq's official list
  first, then Wikipedia, then the last list fetched successfully. The page
  reports coverage, e.g. "all 100 members covered", or names any member that
  couldn't be fetched.
- **Columns: Scores | Value | Growth | Momentum | Quality | All metrics.**
  *Scores* shows factor percentiles. Each factor view shows that factor's
  **key metric values** per company next to its score:

  | View | Values shown |
  |---|---|
  | Value | P/E, earnings yield, P/B, dividend yield, cash-flow yield |
  | Growth | forward revenue growth, op-margin change (pp), forward EPS growth, long-term growth |
  | Momentum | 1M / 3M / 6M / 12M returns, 1M EPS revision, 3M foreign-ownership change (pp) |
  | Quality | operating margin, ROE, ROIC, debt/equity |

  Values stay numeric, so columns sort correctly. *None* means not available,
  e.g. P/E for a loss-maker. The Portfolio Dashboard has the same views for
  your holdings (*Key metrics by factor*).
- **Search:** matches ticker, English name or Korean listing name (e.g. `삼성`,
  `Samsung`, `005930`, `NVDA`).
- **Sector filter:** applies to the table, sector overview and leader map.
  There are also toggles for leaders only and your holdings only.
- **Rank within: Market | Sector.** *Sector* ranks each stock only against its
  own sector (Yahoo's classification). This is a sector-neutral ranking, so
  structurally cheap or highly leveraged sectors (e.g. banks) don't crowd the
  Value or Quality lists. Sectors with fewer than `MIN_SECTOR_SIZE` (5)
  companies are ranked against the whole market; the *Ranked vs* column shows
  which applied.
- **Sectors tab:** median factor percentiles per sector (always market-relative,
  so sectors are comparable), leader counts and share, and median 3M/12M returns.

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
group can't be all-round. Percentiles are relative to the ranking scope
(market or sector).

The Portfolio Dashboard, Market Leaders and Company Analysis pages all rank
against the same snapshots, so a stock gets the same scores everywhere. The
dashboard shows each holding's sector, leader status and the share of your
portfolio in leaders.

### Plugging in better fundamentals (optional override file)

The free data uses proxies for a few consensus inputs (see Company Analysis).
If you have better data, e.g. FnGuide/DataGuide consensus revisions, put it
in `data/fundamentals.csv` (or `.parquet`, or any path in the
`FUNDAMENTALS_PATH` env var). Its values **override** the snapshot's for
matching tickers, on every page:

```
ticker,earnings_yield,dividend_yield,book_to_market,cash_flow_yield,
fwd_revenue_revision,fwd_op_margin_change,fwd_eps_growth,long_term_growth,
payout_ratio,eps_revision_1m,foreign_own_chg_3m,fwd_op_margin,roe,roic,debt_to_equity
```

- Supply any subset of the columns. Blank cells don't override.
- All rates are fractions (`0.05` = 5%). `*_change`/`*_chg_*` columns hold
  percentage-point changes as fractions (`0.01` = +1pp).
- `ticker`: KRX 6-digit codes (leading zeros are restored if Excel drops
  them) or NASDAQ symbols. `long_term_growth` may be omitted; it's derived
  from `roe` and `payout_ratio`.
- The page reports how many companies and which columns were overridden.

The full column reference (definitions, units, direction) is in the page's
*Methodology & data* expander and in `factors/definitions.py`. To add or drop
an input, edit `SUB_FACTORS` there; scoring and UI follow automatically.

## Sector ETFs

`pages/5_Sector_ETFs.py` tracks one representative ETF per sector against the
market benchmark, for the US (Select Sector SPDRs vs SPY) and Korea (vs
KODEX 200):

- **KPIs:** benchmark return, the leading and lagging sectors, and how many
  sectors beat the benchmark over the chosen period (1M to 3Y).
- **Charts:**
  - Period returns for all sectors.
  - A relative-strength heatmap: sector minus benchmark at 1W, 1M, 3M, 6M, YTD
    and 1Y. A row that's red across horizons is a persistent leader.
  - A growth-of-100 comparison of up to 7 sectors. Each sector keeps its color
    while selected.
- **Table:** returns, 1Y volatility, max drawdown, and *Name at source*, which
  shows what each code resolves to.
- **Leading stocks:** the top-ranked stocks in each sector, from the Market
  Leaders scores.

The ETF list lives in `config.SECTOR_ETFS`. Sector keys use Yahoo's sector
names, so each ETF links to its stocks. **The Korean codes (TIGER 200 sector
series) are placeholders: verify them** using the *Name at source* column, or
swap in your own.

## Investor Sentiment

`pages/7_Sentiment.py` tracks investor psychology at two levels and keeps them
separate:

1. **Market mood:** a Fear & Greed index (0 = extreme fear, 100 = extreme
   greed) for the US and Korean markets. Each component is scored as its
   percentile within its own past year, and the scores are averaged. All
   inputs are Yahoo price series, so the full history is available at once.

   | US | Korea |
   |---|---|
   | S&P 500 vs 125-day average · distance from 52-week high | KOSPI vs 125-day average · distance from 52-week high |
   | VIX vs 50-day average | KOSPI 20-day realized volatility |
   | Stocks − Treasuries (SPY − TLT, 20d) | Won strength (USD/KRW, 20d) |
   | Junk − investment-grade bonds (HYG − LQD, 20d) | KOSDAQ − KOSPI (20d risk appetite) |
   | Equal- − cap-weight (RSP − SPY, 20d) | |

   CNN's US Fear & Greed is shown alongside as an external cross-check.

2. **Company sentiment:** a 0–100 index from five independent *families*:

   | Family | Sources | Markets |
   |---|---|---|
   | Crowd | StockTwits (users tag posts bullish/bearish) · Reddit (r/stocks, r/investing, r/wallstreetbets, r/StockMarket) | US (Reddit also searches KR names) |
   | News | Google News headlines, English or Korean | both |
   | Analysts | rating level and its 3-month trend, plus up/downgrades (Yahoo) | both |
   | Positioning | options put/call ratio · short interest (Yahoo) · foreign + institutional net buying (KIS) | US · US · KOSPI |
   | Price | RSI, 52-week position and trend of **stock ÷ market index** | both |

   The page shows the composite and its gap to market mood (the
   company-specific part), the bullish share of posts and headlines,
   attention (today's volume vs the 7-day average), source agreement and
   coverage, a rule-based written summary, the source table, the posts and
   headlines themselves, and the history.

**Objectivity safeguards**
- Families are averaged first, then weighted equally, so two chat sites can't
  outvote analysts and prices.
- Every reading is shrunk toward neutral by n / (n + 10), so thin evidence
  barely moves the index.
- Headlines are de-duplicated (syndicated copies count once) and capped at 3
  per outlet.
- Sell-side ratings skew bullish, so half the analyst score is the 3-month
  *change*.
- The Price family is measured against the market index, so a stock that just
  rides the market reads neutral.
- Korean retail flows are shown but not scored, since they are often read
  contrarily.
- Disagreement and coverage are reported, not hidden. Unavailable sources
  show as unavailable, never filled in.

**Tracking over time.** Market mood and relative price behavior are rebuilt
from price history. Crowd, news, analyst and positioning readings can't be
reconstructed after the fact, so each live page visit records today's
reading in `data/sentiment/history.parquet`. To record a watchlist
(`SENTIMENT_WATCHLIST` in `config.py`) every day, run:

```bash
python -m sentiment.collect                          # watchlist
python -m sentiment.collect --market NASDAQ --tickers NVDA TSLA
```

Suggested cron (KST): `30 16 * * 1-5` for KOSPI and `30 6 * * 2-6` for NASDAQ.

**Setup.**
- Reddit needs a free "script" app (reddit.com/prefs/apps): put
  `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET` in `.env`.
- Korean investor flows use your KIS keys.
- Everything else needs no key.

**Text scoring and caveats.** English uses VADER plus a finance vocabulary;
stock VADER rates "beats earnings, rallies to record high" as neutral. Korean
uses finance stems (상승/하락, 호재/악재, 순매수/순매도 …). The scoring is
transparent and reproducible but misses sarcasm and some negations; swap
`sentiment.text.score_text` for a model such as FinBERT if you need more.

Sentiment describes psychology, not value. Extreme readings are often read
contrarily. Use it alongside the factor analysis, not instead of it. Terms
are explained in the Dictionary (Sentiment category).

**Adding a source:** write a `fetch_*`/`parse_*` pair in `sentiment/sources.py`
that returns a `Reading` with a family, a score in [-1, 1] and its evidence
`n`. Then add it in `sentiment/engine.py`; the aggregation and UI pick it up.

## Dictionary

`pages/6_Dictionary.py` explains every term the app uses (about 100 entries):
factors and scoring, each Value / Growth / Momentum / Quality metric, financial
statement basics, market-leader rules, portfolio fields, backtest statistics,
sectors and ETFs, and data concepts.

- **Every entry** has a definition, its Korean name and aliases, and
  clickable related concepts.
- **Metrics** (P/E, P/B, ROE, ROIC, Sharpe, MDD, …) add what the metric
  measures, the formula, a worked example, how to read it, and *In this app*:
  exactly how the app computes it, including any free-data proxy.
- **Search** works in English, by abbreviation (`PER`, `PBR`, `MDD`) or in
  Korean (`주가순자산비율`, `샤프`), with a category filter and an A–Z list.
- **Deep links:** link to any entry with `?term=<id>`, e.g. `/Dictionary?term=pb`.

Content is plain data in `glossary/entries.py`. To add a term, append an
`Entry` and reference related entries by id. `tests/test_glossary.py` fails
if a link is broken, or if a metric you add to the scoring model
(`factors/definitions.py`) or the metric columns (`ui/metric_views.py`) has no
dictionary entry. Map new metric keys to entries in `glossary.FOR_METRIC`.

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
python -m tests.test_company
python -m tests.test_sectors
python -m tests.test_nasdaq100
python -m tests.test_glossary
python -m tests.test_sentiment
```

All six run offline. `smoke_test` runs the synthetic generator through both reference strategies and the engine,
asserting alignment, no-lookahead timing, and metric sanity. It also checks the
leader screen: factor directions, negative-equity handling, the long-term-growth
derivation, both leader rules, the coverage rule, and trend agreement.
