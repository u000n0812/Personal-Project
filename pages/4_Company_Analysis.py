"""Page 4 — Company Analysis.

Pick any KOSPI or NASDAQ company. Its latest price and fundamentals are
fetched live; it is then scored on Value / Growth / Momentum / Quality and
ranked against the largest companies in its market (daily peer snapshot).
Data access: ``data/company.py``; scoring: ``factors/company.py``.
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
from data import company as company_data
from data.providers import describe_freshness
from factors import pipeline as leader_pipeline
from factors.company import score_company
from factors.definitions import GROUPS, format_value
from factors.price import trailing_returns
from ui import factor_charts, theme

st.set_page_config(page_title="Company Analysis", page_icon="🔎", layout="wide")
theme.register_theme()
theme.sidebar_mode_badge(show_status=False)

st.title("🔎 Company Analysis")


def money(value: float, currency: str, compact: bool = False) -> str:
    if value is None or np.isnan(value):
        return "–"
    if currency == "KRW":
        return f"₩{value / 1e12:,.1f}T" if compact else f"₩{value:,.0f}"
    symbol = "$" if currency == "USD" else f"{currency} "
    return f"{symbol}{value / 1e9:,.1f}B" if compact else f"{symbol}{value:,.2f}"


# ---------------------------------------------------------------------------
# Source + listing (with explicit fallbacks)
# ---------------------------------------------------------------------------
with st.sidebar:
    st.divider()
    market = st.radio("Market", list(config.MARKETS), horizontal=True)

source = "synthetic" if st.session_state.get("force_synthetic", False) else "yahoo"
fallback_reason, listing_note = None, None
if source == "yahoo":
    try:
        listing = company_data.listing("yahoo", market)
    except Exception as err:  # noqa: BLE001
        snap = company_data.peers("yahoo", market)
        if snap is not None:  # listing source down, but we have yesterday's peers
            listing = snap[0].reset_index()[["ticker", "name", "market_cap"]]
            listing_note = f"Listing source unreachable ({type(err).__name__}); showing snapshot companies."
        else:
            fallback_reason, source = f"{type(err).__name__}: {err}", "synthetic"
if source == "synthetic":
    listing = company_data.listing("synthetic", market)

names = dict(zip(listing["ticker"], listing["name"]))
with st.sidebar:
    pick = st.selectbox(
        f"Company ({len(listing):,} listed)", list(listing["ticker"]), key=f"pick_{market}",
        format_func=lambda t: f"{t} · {names.get(t, '')}",
        help="Type to search by ticker or name.",
    )
    typed = st.text_input("…or enter a ticker", key=f"typed_{market}",
                          placeholder="005930" if market == "KOSPI" else "AAPL").strip().upper()
    if listing_note:
        st.caption(listing_note)

ticker = typed or pick
if market == "KOSPI" and ticker.isdigit():
    ticker = ticker.zfill(6)

if fallback_reason:
    st.warning(
        f"Live data unavailable — {fallback_reason[:220]}. "
        "Showing **synthetic demo data**: every number on this page is made up.", icon="⚠️")
elif source == "synthetic":
    st.info("Synthetic demo data (forced in the sidebar).", icon="🧪")

# ---------------------------------------------------------------------------
# Peers snapshot
# ---------------------------------------------------------------------------
snap = company_data.peers(source, market)
with st.sidebar:
    st.subheader("Peer universe")
    if snap is not None:
        meta = snap[1]
        st.caption(f"{meta.get('companies', len(snap[0])):,} largest {market} companies · "
                   f"prices as of {meta.get('price_date', '?')} · {meta.get('provider', '')}")
        age = company_data.snapshot_age_days(meta)
        if source == "yahoo" and age is not None and age > config.SNAPSHOT_STALE_DAYS:
            st.warning(f"Snapshot is {age} days old — rebuild for current rankings.")
    else:
        st.warning(f"No {market} peer snapshot yet — rankings need one.")
    if source == "yahoo" and st.button(f"Build {market} snapshot (top {config.PEER_TOP_N})",
                                       help="Fetches every peer from Yahoo — a few minutes. "
                                            "Or schedule `python -m data.snapshot`."):
        bar = st.progress(0.0, text="Fetching listing and prices…")
        try:
            built = company_data.rebuild_peers(market, bar)
            st.success(f"Built: {built['companies']} companies, {len(built['failed'])} failed.")
            st.rerun()
        except Exception as err:  # noqa: BLE001
            st.error(f"Snapshot build failed — {type(err).__name__}: {err}")

    st.caption(
        "Prices: **KIS real-time**" if source == "yahoo" and config.has_credentials()
        else "Prices: **Yahoo Finance** (US real-time · KRX ~20 min delayed)" if source == "yahoo"
        else "Prices: **synthetic**"
    )

# ---------------------------------------------------------------------------
# Selected company — always live; failures are reported, never faked
# ---------------------------------------------------------------------------
try:
    info = company_data.company(source, ticker, market)
    quote = company_data.quote(source, ticker, market)
    hist = company_data.history(source, ticker, market)
except Exception as err:  # noqa: BLE001
    st.error(f"Couldn't fetch **{ticker}** ({market}) — {type(err).__name__}: {err}")
    st.stop()

# Momentum uses the latest quote: it replaces/extends the daily close series.
tz = config.MARKETS[market]["tz"]
quote_day = pd.Timestamp(pd.Timestamp(quote.as_of).tz_convert(tz).date())
prices = hist.copy()
prices.loc[quote_day] = quote.price
prices = prices.sort_index()
returns = trailing_returns(prices.to_frame(ticker)).loc[ticker]

target = pd.Series({**info.metrics, **returns.to_dict(), "name": info.name,
                    "sector": info.sector, "industry": info.industry})

# ---------------------------------------------------------------------------
# Header: identity + live price
# ---------------------------------------------------------------------------
st.header(info.name)
st.caption(" · ".join(x for x in (ticker, market, info.sector, info.industry) if x))

level, fresh_label = describe_freshness(quote.as_of, market, datetime.now(timezone.utc))
currency = quote.currency or info.currency or config.MARKETS[market]["currency"]
p1, p2, p3 = st.columns([1, 1, 2])
p1.metric("Last price", money(quote.price, currency),
          delta=None if np.isnan(quote.change) else f"{quote.change:+.2%}")
p2.metric("Market cap", money(info.market_cap, currency, compact=True))
with p3:
    st.markdown("**Price freshness**")
    st.badge(fresh_label,
             icon={"live": ":material/bolt:", "delayed": ":material/schedule:",
                   "close": ":material/history:"}[level],
             color={"live": "green", "delayed": "orange", "close": "gray"}[level])
    st.caption(f"Source: {quote.source}")

st.divider()

# ---------------------------------------------------------------------------
# Scores + ranks
# ---------------------------------------------------------------------------
if snap is None:
    st.info(
        f"Build the {market} peer snapshot (sidebar) to rank {info.name} against the "
        f"{config.PEER_TOP_N} largest {market} companies. Its raw factor inputs are below.",
        icon="ℹ️")
    st.dataframe(pd.DataFrame({
        "Input": [sf.label for sf in factor_charts.SUB_FACTOR_ORDER],
        "Factor": [sf.group for sf in factor_charts.SUB_FACTOR_ORDER],
        "Value": [format_value(sf, target.get(sf.key, np.nan))
                  for sf in factor_charts.SUB_FACTOR_ORDER],
    }), hide_index=True, width="stretch")
    st.stop()

peers, meta = snap
all_round, standout = leader_pipeline.get_thresholds()
score = score_company(ticker, target, peers, all_round, standout, config.LEADER_MIN_COVERAGE)
n = score.universe_size

k1, k2, k3, k4 = st.columns(4)
k1.metric("Composite score", "–" if np.isnan(score.composite) else f"{score.composite * 100:.0f}",
          help="Mean of the four factor percentiles (0–100).")
k2.metric(f"{market} rank", "–" if np.isnan(score.rank) else f"#{score.rank:.0f} / {n}",
          help=f"Composite rank among the {n} companies scored "
               f"(top-{config.PEER_TOP_N} peers + this company).")
if not np.isnan(score.rank):
    k2.caption(f"Top {score.rank / n:.0%} of the market")
k3.metric("Leader status", score.classification.replace(" leader", "") or "—",
          help=f"All-round: every factor ≥ {all_round:.0%} percentile. "
               f"Standout: any factor ≥ {standout:.0%}.")
if score.standout_in:
    k3.caption(f"Standout in {score.standout_in}")
k4.metric(f"Sector rank · {score.sector or 'n/a'}",
          "–" if np.isnan(score.sector_rank) else f"#{score.sector_rank:.0f} / {score.sector_size}")
if score.tags:
    st.caption(f"Tags: **{score.tags}**")
if not score.in_snapshot:
    st.caption(f"{info.name} isn't among the {config.PEER_TOP_N} largest peers; it was "
               "added to the universe for scoring.")

cols = st.columns(4)
for col, group in zip(cols, GROUPS):
    pct = score.group_pct[group]
    with col.container(border=True):
        st.metric(group, "n/a" if np.isnan(pct) else f"{pct * 100:.0f}",
                  help="Percentile within the market (100 = best).")
        st.caption("Too little data" if np.isnan(pct)
                   else f"#{score.group_rank[group]:.0f} of {n} in {market}")

# ---------------------------------------------------------------------------
# Where it sits in the market
# ---------------------------------------------------------------------------
st.subheader(f"Where it ranks among {n} {market} companies")
board = score.board
rows = ["Composite", *GROUPS]
values = board.groups.assign(Composite=board.table["composite"])[rows] * 100
rng = np.random.default_rng(0)
strip = go.Figure()
others = values.drop(index=ticker)
for i, row_name in enumerate(rows):
    strip.add_trace(go.Scatter(
        x=others[row_name], y=i + rng.uniform(-0.28, 0.28, len(others)), mode="markers",
        marker=dict(size=6, color=theme.MUTED, opacity=0.45), name="Peers",
        showlegend=i == 0, text=board.table["name"].reindex(others.index),
        hovertemplate="%{text}: %{x:.0f}<extra></extra>",
    ))
target_vals = values.loc[ticker]
strip.add_trace(go.Scatter(
    x=target_vals.values, y=list(range(len(rows))), mode="markers+text", name=info.name,
    marker=dict(size=16, symbol="diamond",
                color=[theme.INK] + [theme.GROUP_COLORS[g] for g in GROUPS],
                line=dict(color=theme.SURFACE, width=2)),
    text=[("n/a" if np.isnan(v) else f"{v:.0f}") for v in target_vals.values],
    textposition="top center", textfont=dict(size=12, color=theme.INK),
    hovertemplate=info.name + " · %{x:.0f}<extra></extra>",
))
strip.add_vline(x=standout * 100, line=dict(color=theme.BASELINE, dash="dash", width=1),
                annotation_text="standout", annotation_position="top")
strip.add_vline(x=all_round * 100, line=dict(color=theme.BASELINE, dash="dot", width=1),
                annotation_text="all-round", annotation_position="top")
strip.update_layout(
    height=380, hovermode="closest",
    xaxis=dict(title="Percentile score (100 = best)", range=[-2, 104]),
    yaxis=dict(tickvals=list(range(len(rows))), ticktext=rows, autorange="reversed",
               showgrid=False, zeroline=False),
)
st.plotly_chart(strip, width="stretch")

# ---------------------------------------------------------------------------
# Sub-factor breakdown
# ---------------------------------------------------------------------------
st.subheader("Factor breakdown")
pcts = board.percentiles.loc[ticker]
raw = board.metrics.loc[ticker]
medians = board.metrics.median(numeric_only=True)
st.plotly_chart(factor_charts.subfactor_bars(pcts, height=470), width="stretch")
order = factor_charts.SUB_FACTOR_ORDER
st.dataframe(pd.DataFrame({
    "Factor": [sf.group for sf in order],
    "Input": [sf.label for sf in order],
    "Value": [format_value(sf, raw[sf.key]) for sf in order],
    "Market median": [format_value(sf, medians.get(sf.key, np.nan)) for sf in order],
    "Pctl": [pcts[sf.key] * 100 for sf in order],
    "Note": [info.notes.get(sf.key, "") for sf in order],
}), hide_index=True, width="stretch", height=560,
    column_config={"Pctl": st.column_config.NumberColumn("Pctl", format="%.0f"),
                   "Note": st.column_config.TextColumn("Note", width="large")})
st.caption("Returns (incl. latest quote) — " + " · ".join(
    f"{k}: {theme.pct(returns.get(f'ret_{k}'), 1)}" for k in ("1M", "3M", "6M", "12M")))

# ---------------------------------------------------------------------------
# Price + peer context
# ---------------------------------------------------------------------------
st.subheader("Price · 1 year")
year = prices[prices.index >= prices.index.max() - pd.Timedelta(days=365)]
fig = go.Figure(go.Scatter(x=year.index, y=year.values, mode="lines", name=info.name,
                           line=dict(color=theme.PALETTE[0], width=2),
                           hovertemplate="%{x|%Y-%m-%d}: %{y:,.2f}<extra></extra>"))
fig.add_trace(go.Scatter(x=[year.index[-1]], y=[year.iloc[-1]], mode="markers",
                         marker=dict(size=9, color=theme.PALETTE[0],
                                     line=dict(color=theme.SURFACE, width=2)),
                         showlegend=False, hoverinfo="skip"))
fig.update_layout(height=320, showlegend=False, yaxis_title=currency, hovermode="x")
st.plotly_chart(fig, width="stretch")

st.subheader(f"{market} leaderboard")
table = board.table.join(board.groups[list(GROUPS)])
top = table.head(10)
if ticker not in top.index:
    top = pd.concat([top, table.loc[[ticker]]])
view = top.reset_index().rename(columns={"index": "ticker"})
view["sel"] = np.where(view["ticker"] == ticker, "▶", "")
for col in (*GROUPS, "composite"):
    view[col] = (view[col] * 100).round(0)
st.dataframe(
    view[["sel", "rank", "ticker", "name", "sector", "composite", *GROUPS, "classification"]],
    hide_index=True, width="stretch",
    column_config={"sel": st.column_config.TextColumn("", width="small"),
                   "rank": st.column_config.NumberColumn("#", format="%d"),
                   "ticker": "Ticker", "name": "Name", "sector": "Sector",
                   "composite": st.column_config.NumberColumn("Composite", format="%d"),
                   "classification": "Leader",
                   **{g: st.column_config.NumberColumn(g, format="%d") for g in GROUPS}},
)

# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------
with st.expander("Data sources & freshness"):
    failed = meta.get("failed", {})
    st.markdown(f"""
- **Price:** {quote.source}, {fresh_label}. Quotes refresh every
  {company_data.QUOTE_TTL}s; with KIS keys in `.env`, KIS real-time quotes are used.
- **This company's fundamentals:** {"synthetic" if source == "synthetic" else "Yahoo Finance"},
  fetched live (cached {company_data.COMPANY_TTL // 3600}h).
- **Peers:** {meta.get('companies', len(peers))} largest {market} companies by market cap,
  prices as of **{meta.get('price_date', '?')}**, built {meta.get('built_at', '?')}
  ({len(failed)} companies failed to fetch and are excluded).
- **Scoring:** each input is ranked across peers + this company; a factor is the mean
  of its inputs' percentiles, re-ranked; composite = mean of the four factors. A factor
  needs ≥ {config.LEADER_MIN_COVERAGE:.0%} of its inputs, otherwise it's n/a.
- **Proxies:** free sources lack consensus revision history and Korean foreign-ownership
  data — see the *Note* column above for each affected input.
""")
