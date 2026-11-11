"""Page 7 — Investor sentiment.

Market mood (a Fear & Greed index for the US and Korean markets) kept
separate from company-specific sentiment, which combines independent source
families — Crowd, News, Analysts, Positioning, Price — so no single
community or data source dominates. Supplementary to the factor analysis,
not a forecast. Logic in ``sentiment/``; visuals in ``ui/sentiment_views.py``.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
from data import company as company_data
from factors import pipeline
from sentiment import engine, history
from sentiment.market import SPECS
from sentiment.model import FAMILIES, FAMILY_NOTES, band, readings_frame, summarize
from ui import sentiment_views as sv
from ui import theme

st.set_page_config(page_title="Sentiment", page_icon="🧭", layout="wide")
theme.register_theme()
theme.sidebar_mode_badge(show_status=False)

st.title("🧭 Investor Sentiment")
st.caption("How investors feel — about the market as a whole, and about one company in "
           "particular. A supplementary lens on investor psychology, not a forecast.")

# ---------------------------------------------------------------------------
# Source + fallbacks (public data; synthetic when forced or unreachable)
# ---------------------------------------------------------------------------
source, fallback = pipeline.resolve_source(), None
moods: dict[str, engine.MarketSentiment] = {}
for mk in ("NASDAQ", "KOSPI"):
    try:
        moods[mk] = sv.market_mood(source, mk)
        if moods[mk].history.empty:
            raise LookupError(f"no price data for the {mk} Fear & Greed inputs")
    except Exception as err:  # noqa: BLE001
        if source == "synthetic":
            raise
        fallback, source = f"{type(err).__name__}: {err}", "synthetic"
        break
if fallback:  # a live market failed: show both markets from the same (demo) source
    moods = {mk: sv.market_mood("synthetic", mk) for mk in ("NASDAQ", "KOSPI")}
if fallback:
    st.warning(f"Live data unavailable — {fallback[:200]}. Showing **synthetic demo data**: "
               "every number on this page is made up.", icon="⚠️")
elif source == "synthetic":
    st.info("Synthetic demo data (forced in the sidebar).", icon="🧪")

# ---------------------------------------------------------------------------
# 1. Market mood — market-wide, about no company in particular
# ---------------------------------------------------------------------------
st.header("Market mood")
st.caption("A Fear & Greed index per market: each component is scored against its own past "
           "year, then averaged (0 = extreme fear, 100 = extreme greed). Red = greed, "
           "blue = fear.")
cols = st.columns(2)
for col, mk in zip(cols, ("NASDAQ", "KOSPI")):
    mood = moods[mk]
    with col.container(border=True):
        st.subheader(mood.name)
        m1, m2, m3 = st.columns(3)
        m1.metric("Fear & Greed", f"{mood.latest:.0f}", help="0–100, today")
        m1.caption(f"**{band(mood.latest)}**")
        m2.metric("1 week ago", f"{mood.latest - mood.change(5):.0f}",
                  delta=f"{mood.change(5):+.0f}", delta_color="off")
        m3.metric("1 month ago", f"{mood.latest - mood.change(21):.0f}",
                  delta=f"{mood.change(21):+.0f}", delta_color="off")
        st.plotly_chart(sv.band_bar(mood.latest), width="stretch",
                        config={"displayModeBar": False})
        if mood.cnn:
            st.caption(f"External reference — CNN Fear & Greed: **{mood.cnn['score']:.0f}** "
                       f"({mood.cnn['rating']}). Different inputs; use it as a cross-check.")
        latest = mood.history.iloc[-1]
        comps = [{"Component": c.label, "Score": latest.get(c.key, np.nan), "What it measures":
                  c.explain} for c in SPECS[mk]["components"]]
        with st.expander("Components"):
            st.dataframe(pd.DataFrame(comps), hide_index=True, width="stretch",
                         column_config={"Score": st.column_config.ProgressColumn(
                             "Score", min_value=0, max_value=100, format="%d")})

# ---------------------------------------------------------------------------
# 2. Company sentiment
# ---------------------------------------------------------------------------
st.divider()
target = st.session_state.pop("_sentiment_target", None)  # set by Company Analysis
with st.sidebar:
    st.divider()
    markets = list(config.MARKETS)
    if target:
        st.session_state["sent_market"] = target[0]
    market = st.radio("Market", markets, horizontal=True, key="sent_market")
universe = company_data.market_universe(source, market)
if universe is not None:
    frame = universe[0]
    if "market_cap" in frame.columns:  # largest companies first
        frame = frame.sort_values("market_cap", ascending=False, na_position="last")
    names = frame["name"].astype(str).to_dict()
    local = frame.get("name_local", frame["name"]).fillna(frame["name"]).astype(str).to_dict()
else:  # no snapshot yet: try the live listing; a typed ticker always works
    try:
        listing = company_data.listing(source, market)
    except Exception:  # noqa: BLE001
        listing = pd.DataFrame(columns=["ticker", "name"])
    names = dict(zip(listing["ticker"], listing["name"]))
    local = dict(names)
options = list(names)
with st.sidebar:
    if target and target[1] in options:
        st.session_state[f"sent_pick_{market}"] = target[1]
    pick = st.selectbox("Company", options, key=f"sent_pick_{market}",
                        format_func=lambda t: f"{t} · {local.get(t) or names.get(t, '')}") \
        if options else None
    typed = st.text_input("…or enter a ticker", key=f"sent_typed_{market}",
                          placeholder="005930" if market == "KOSPI" else "NVDA").strip().upper()
    if universe is None and source != "synthetic":
        st.caption("Build the peer snapshot (Market Leaders) for the full company list.")
ticker = typed or pick or (target[1] if target else "")
if not ticker:
    st.info("Enter a ticker in the sidebar to analyze a company.")
    st.stop()
if market == "KOSPI" and ticker.isdigit():
    ticker = ticker.zfill(6)
if target and target[1] not in options:
    ticker = target[1]
name = names.get(ticker, ticker)
name_local = local.get(ticker, name)
display_name = name_local if market == "KOSPI" else name

try:
    stock = sv.stock_mood(source, ticker, market, name, name_local)
except Exception as err:  # noqa: BLE001 — report, never fake a live company's data
    st.error(f"Couldn't analyze **{ticker}** — {type(err).__name__}: {err}")
    st.stop()
c, mood = stock.composite, moods[market]

# Record live readings once per day per company, so trends build up.
if source != "synthetic" and not np.isnan(c.index):
    key = (date.today().isoformat(), market, ticker)
    recorded = st.session_state.setdefault("_sentiment_recorded", set())
    if key not in recorded:
        try:
            history.record(stock, mood.latest)
            recorded.add(key)
        except Exception:  # noqa: BLE001 — history is best-effort
            pass

st.header(f"{display_name} · company sentiment")
st.caption(f"{ticker} · {market}. Built from independent source families, each weighted "
           "equally; thin evidence is pulled toward neutral.")
gap = c.index - mood.latest
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Sentiment index", "–" if np.isnan(c.index) else f"{c.index:.0f}",
          help="0 = extreme fear · 100 = extreme greed")
k1.caption(f"**{c.label}**")
k2.metric("vs market mood", "–" if np.isnan(gap) else f"{gap:+.0f} pts",
          help=f"Stock sentiment minus the {mood.name} Fear & Greed index — the "
               "company-specific part of the mood.")
k2.caption(f"{mood.name}: {mood.latest:.0f} ({band(mood.latest).lower()})")
k3.metric("Bullish share", "–" if np.isnan(c.bull_ratio) else f"{c.bull_ratio:.0%}",
          help="Share of classified posts and headlines that are bullish.")
k3.caption(f"bull/bear n = {c.bull_n}")
k4.metric("Attention", "–" if np.isnan(c.attention) else f"{c.attention:.1f}×",
          help="Posts and headlines in the last 24h vs the 7-day daily average.")
k4.caption("vs usual volume")
k5.metric("Coverage", f"{c.coverage} / {len(FAMILIES)}",
          help="Source families with data.")
k5.caption(c.agreement_label)

f1, f2 = st.columns([1, 1])
with f1:
    st.markdown("**By source family**")
    st.plotly_chart(sv.family_bars(c), width="stretch")
with f2:
    st.markdown("**Summary**")
    for line in summarize(display_name, c, mood.latest, band(mood.latest), mood.name):
        st.markdown(f"- {line}")

st.markdown("**Sources**")
st.dataframe(
    readings_frame(c.readings), hide_index=True, width="stretch",
    column_config={
        "Score": st.column_config.NumberColumn(format="%.0f", help="0–100, before shrinkage"),
        "Evidence (n)": st.column_config.NumberColumn(format="%.0f"),
        "Weight": st.column_config.ProgressColumn(
            "Weight", min_value=0, max_value=1, format="%.2f",
            help="n / (n + 10): how much of the score survives shrinkage toward neutral"),
        "Adjusted": st.column_config.NumberColumn(format="%.0f", help="After shrinkage"),
        "Note": st.column_config.TextColumn(width="large"),
    },
)

# ---------------------------------------------------------------------------
# 3. Over time
# ---------------------------------------------------------------------------
st.subheader("Sentiment over time")
period_days = {"3M": 63, "6M": 126, "1Y": 252}[
    st.segmented_control("Period", ["3M", "6M", "1Y"], default="6M", key="sent_period") or "6M"]
market_line = mood.history["index"].iloc[-period_days:]
price_line = (stock.price_history * 50 + 50).iloc[-period_days:]
recorded = history.load(ticker, market) if source != "synthetic" else pd.DataFrame()
fig = go.Figure()
fig.add_trace(go.Scatter(x=market_line.index, y=market_line, name=f"{mood.name} Fear & Greed",
                         line=dict(color=theme.MUTED, width=2, dash="dash")))
fig.add_trace(go.Scatter(x=price_line.index, y=price_line, name="Price behavior vs market",
                         line=dict(color=theme.PALETTE[0], width=2)))
if not recorded.empty:
    fig.add_trace(go.Scatter(x=recorded.index, y=recorded["index"], name="Composite (recorded)",
                             mode="lines+markers", line=dict(color=theme.PALETTE[4], width=2),
                             marker=dict(size=8, line=dict(color=theme.SURFACE, width=2))))
fig.add_hline(y=50, line=dict(color=theme.BASELINE, width=1))
fig.update_layout(height=360, yaxis=dict(range=[0, 100], title="0 fear · 100 greed"))
st.plotly_chart(fig, width="stretch")
st.caption(
    "Market mood and price behavior are rebuilt from price history. Crowd, news, analyst and "
    "positioning readings can't be reconstructed after the fact, so the composite line grows "
    "as readings are recorded — each live visit records today's reading; schedule "
    "`python -m sentiment.collect` to record a watchlist daily."
    + (f" {len(recorded)} recorded day(s) so far." if not recorded.empty else ""))

daily = engine.daily_item_scores(c)
if len(daily):
    att = go.Figure(go.Bar(x=daily.index, y=daily["count"],
                           marker=dict(color=[theme.UP if s >= 0 else theme.DOWN
                                              for s in daily["score"]], cornerradius=3),
                           customdata=daily["score"],
                           hovertemplate="%{x|%b %d}: %{y} items, mean tone %{customdata:+.2f}"
                                         "<extra></extra>"))
    att.update_layout(height=200, yaxis_title="Posts + headlines", hovermode="closest",
                      margin=dict(t=10))
    st.markdown("**Daily volume of posts and headlines** (color = average tone)")
    st.plotly_chart(att, width="stretch")

# ---------------------------------------------------------------------------
# 4. What's being said
# ---------------------------------------------------------------------------
with_items = [r for r in c.readings if r.items]
if with_items:
    st.subheader("What's being said")
    tabs = st.tabs([f"{r.source} ({len(r.items)})" for r in with_items])
    for tab, r in zip(tabs, with_items):
        with tab:
            rows = pd.DataFrame([{
                "When": i["time"].strftime("%Y-%m-%d %H:%M") if hasattr(i.get("time"), "strftime")
                else "", "Text": i["text"], "Tone": i["score"], "By": i.get("by", ""),
                "Link": i.get("url") or None} for i in r.items])
            st.dataframe(rows, hide_index=True, width="stretch", column_config={
                "Tone": st.column_config.NumberColumn(format="%+.2f",
                                                      help="−1 bearish … +1 bullish"),
                "Text": st.column_config.TextColumn(width="large"),
                "Link": st.column_config.LinkColumn(display_text="open")})

with st.expander("Methodology, sources and caveats"):
    st.markdown(f"""
**Two levels, never mixed.** *Market mood* uses only market-wide price series. *Company
sentiment* uses sources about the company; its Price family is measured **relative to the
market index** (stock ÷ index), so a stock that simply rises with the market reads neutral.
The gap between the two shows how much of the mood is company-specific.

**Families (equal weight):** {"; ".join(f"*{f}* — {n}" for f, n in FAMILY_NOTES.items())}

**Objectivity safeguards**
- Families are averaged first, then combined equally, so no single community dominates.
- Each reading is shrunk toward neutral by n / (n + 10) — a handful of posts barely moves it.
- Headlines are de-duplicated (syndicated copies count once) and capped at 3 per outlet.
- Analyst ratings skew bullish, so half their weight is the 3-month *change* in ratings.
- Retail flows in Korea are shown but not scored (often read as contrarian).
- Disagreement and coverage are reported, not averaged away.

**Text scoring** is a transparent lexicon (VADER plus a finance vocabulary for English; a
finance stem list for Korean). It misses sarcasm and some negations.

**Sources:** StockTwits (public API), Reddit (official API — needs free keys in `.env`),
Google News RSS, Yahoo Finance (analysts, options, short interest, prices), KIS Open API
(Korean investor flows, needs keys), CNN Fear & Greed as an external US cross-check.

**Caveat:** sentiment describes psychology, not value. Extreme readings are often read
contrarily — crowded optimism or pessimism can precede reversals.
""")
