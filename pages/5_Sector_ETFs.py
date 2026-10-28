"""Page 5 — Sector ETFs.

Tracks one representative ETF per sector (``config.SECTOR_ETFS``) against
its market benchmark: period returns, relative strength across horizons,
risk, and the top-ranked stocks in each sector from the Market Leaders
scores. Analytics live in ``factors/sector.py``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
from data import company as company_data
from factors import pipeline
from factors.sector import CHART_PERIODS, performance, period_start, rebased
from ui import theme

st.set_page_config(page_title="Sector ETFs", page_icon="📊", layout="wide")
theme.register_theme()
theme.sidebar_mode_badge(show_status=False)

st.title("📊 Sector ETFs")
st.caption("One representative ETF per sector, compared with the market benchmark. "
           "Use it to see which sectors lead and lag, then drill into their stocks.")

MARKET_LABELS = {"KOSPI": "Korea", "NASDAQ": "US"}
with st.sidebar:
    st.divider()
    market = st.radio("Market", list(config.SECTOR_ETFS), horizontal=True,
                      format_func=lambda m: MARKET_LABELS.get(m, m), key="etf_market")
    period = st.radio("Chart period", CHART_PERIODS, index=CHART_PERIODS.index("1Y"),
                      horizontal=True, key="etf_period")

spec = config.SECTOR_ETFS[market]
bench, bench_label = spec["benchmark"]
etfs = pd.DataFrame(spec["etfs"], columns=["sector", "ticker", "label"])
dup = etfs["sector"].duplicated(keep=False)
etfs["display"] = etfs["sector"].where(~dup, etfs["sector"] + " (" + etfs["label"] + ")")
display = dict(zip(etfs["ticker"], etfs["display"])) | {bench: f"Benchmark · {bench_label}"}
tickers = (*etfs["ticker"], bench)

# ---------------------------------------------------------------------------
# Prices (free Yahoo source; labelled synthetic fallback if unreachable)
# ---------------------------------------------------------------------------
source, fallback = pipeline.resolve_source(), None
try:
    close = company_data.etf_closes(source, tickers, market)
except Exception as err:  # noqa: BLE001
    if source == "synthetic":
        raise
    fallback, source = f"{type(err).__name__}: {err}", "synthetic"
    close = company_data.etf_closes(source, tickers, market)

if fallback:
    st.warning(f"Live prices unavailable — {fallback[:220]}. Showing **synthetic demo "
               "data**: every number on this page is made up.", icon="⚠️")
elif source == "synthetic":
    st.info("Synthetic demo data (forced in the sidebar).", icon="🧪")
if "PLACEHOLDER" in spec["label"]:
    st.caption(f"⚠️ {spec['label']}: verify the codes in `config.SECTOR_ETFS` — the "
               "*Name at source* column shows what each code actually is.")

perf = performance(close, bench)
missing = [t for t in tickers if t not in perf.index or pd.isna(perf.at[t, "last"])]
if missing:
    st.warning("No prices for: " + ", ".join(f"{display[t]} ({t})" for t in missing))

start = period_start(close.index, period)
growth = rebased(close, start)
period_ret = growth.iloc[-1] / 100.0 - 1.0
sectors_ret = period_ret.drop(bench).dropna().sort_values(ascending=False)
bench_ret = period_ret.get(bench, np.nan)
as_of = close.dropna(how="all").index.max()

# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------
k1, k2, k3, k4 = st.columns(4)
k1.metric(f"Benchmark · {period}", theme.pct(bench_ret, 1), help=f"{bench_label} ({bench})")
if len(sectors_ret):
    k2.metric(f"Leading sector · {period}", display[sectors_ret.index[0]],
              delta=theme.pct(sectors_ret.iloc[0], 1))
    k3.metric(f"Lagging sector · {period}", display[sectors_ret.index[-1]],
              delta=theme.pct(sectors_ret.iloc[-1], 1))
    k4.metric("Sectors beating benchmark", f"{(sectors_ret > bench_ret).sum()} / {len(sectors_ret)}")
st.caption(f"Daily closes as of **{as_of:%Y-%m-%d}** · {company_data.provider(source).name}"
           " (during market hours the latest bar is intraday).")

# ---------------------------------------------------------------------------
# Period returns (all sectors) + relative strength heatmap
# ---------------------------------------------------------------------------
c1, c2 = st.columns([1, 1])
with c1:
    st.subheader(f"Return · {period}")
    order = sectors_ret.sort_values()
    vals = order.values * 100
    points = [0.0, *vals, bench_ret * 100]
    lo, hi = float(np.nanmin(points)), float(np.nanmax(points))
    pad = 0.22 * (hi - lo or 1.0)  # room for outside labels on both sides
    bars = go.Figure(go.Bar(
        x=vals, y=[display[t] for t in order.index], orientation="h",
        marker=dict(color=[theme.UP if v >= 0 else theme.DOWN for v in order.values],
                    cornerradius=4),
        text=[theme.pct(v, 1) for v in order.values], textposition="outside",
        cliponaxis=False, hovertemplate="%{y}: %{x:+.1f}%<extra></extra>",
    ))
    bars.update_xaxes(range=[lo - (pad if lo < 0 else 0), hi + pad])
    if not np.isnan(bench_ret):
        bars.add_vline(x=bench_ret * 100, line=dict(color=theme.INK, dash="dash", width=1),
                       annotation_text=f"benchmark {bench_ret:+.1%}",
                       annotation_position="top")
    bars.update_layout(height=max(360, 34 * len(order) + 80), hovermode="closest",
                       xaxis=dict(title="Return (%)", ticksuffix="%"),
                       margin=dict(r=70))
    st.plotly_chart(bars, width="stretch")
    st.caption("Red = gain, blue = loss (Korean market convention).")

with c2:
    st.subheader("Relative strength vs benchmark")
    horizons = ["1W", "1M", "3M", "6M", "YTD", "1Y"]
    if "excess_1W" not in perf.columns:
        st.info("Benchmark prices unavailable — relative strength can't be computed.")
        st.stop()
    rs = perf.loc[list(etfs["ticker"]), [f"excess_{h}" for h in horizons]] * 100
    rs = rs.loc[sectors_ret.index.intersection(rs.index)]  # same order as the leaders
    lim = float(np.nanmax(np.abs(rs.values))) if rs.notna().any().any() else 1.0
    heat = go.Figure(go.Heatmap(
        z=rs.values, x=horizons, y=[display[t] for t in rs.index],
        zmin=-lim, zmax=lim, zmid=0, colorscale=theme.DIVERGING,
        texttemplate="%{z:+.1f}", textfont=dict(size=11), xgap=2, ygap=2,
        hovertemplate="%{y} · %{x}: %{z:+.1f} pp vs benchmark<extra></extra>",
        colorbar=dict(thickness=12, outlinewidth=0, title=dict(text="pp", side="top")),
    ))
    heat.update_layout(height=max(360, 34 * len(rs) + 80), hovermode="closest",
                       yaxis=dict(autorange="reversed"), xaxis=dict(side="top", tickangle=0),
                       margin=dict(t=40))
    st.plotly_chart(heat, width="stretch")
    st.caption("Sector return minus benchmark return, in percentage points. A row that is "
               "red across horizons is a persistent leader.")

# ---------------------------------------------------------------------------
# Growth-of-100 comparison (≤ 7 sectors at a time; colors stay with the ETF)
# ---------------------------------------------------------------------------
st.subheader(f"Performance comparison · {period}")
default = [*sectors_ret.index[:2], *sectors_ret.index[-2:]] if len(sectors_ret) >= 4 \
    else list(sectors_ret.index)
chosen = st.multiselect(
    "Sectors to compare (max 7)", list(etfs["ticker"]), default=default, max_selections=7,
    format_func=lambda t: display[t], key=f"etf_chosen_{market}",
)

# Stable color slots: a sector keeps its color while selected, so adding or
# removing others never repaints it.
slots = st.session_state.setdefault(f"etf_colors_{market}", {})
for t in [t for t in slots if t not in chosen]:
    del slots[t]
for t in chosen:
    if t not in slots:
        slots[t] = min(set(range(len(theme.PALETTE))) - set(slots.values()))

def spread_labels(ends: dict[str, float], min_gap: float) -> dict[str, float]:
    """Nudge end-of-line label positions apart so none sit closer than
    ``min_gap`` (data units), keeping their order."""
    placed: dict[str, float] = {}
    for key, y in sorted(ends.items(), key=lambda kv: kv[1]):
        prev = max(placed.values(), default=None)
        placed[key] = y if prev is None or y - prev >= min_gap else prev + min_gap
    return placed


lines = go.Figure()
if bench in growth:
    lines.add_trace(go.Scatter(
        x=growth.index, y=growth[bench], name=display[bench], mode="lines",
        line=dict(color=theme.MUTED, width=2, dash="dash"),
        hovertemplate="%{y:.1f}<extra>" + bench_label + "</extra>"))
for t in chosen:
    color = theme.PALETTE[slots[t]]
    lines.add_trace(go.Scatter(
        x=growth.index, y=growth[t], name=display[t], mode="lines",
        line=dict(color=color, width=2),
        hovertemplate="%{y:.1f}<extra>" + display[t] + "</extra>"))
if 0 < len(chosen) <= 4:  # direct labels when few lines (the legend always shows)
    ends = {t: growth[t].dropna().iloc[-1] for t in chosen if growth[t].notna().any()}
    span = float(np.nanmax(growth[chosen].values) - np.nanmin(growth[chosen].values)) or 1.0
    for t, y in spread_labels(ends, min_gap=0.06 * span).items():
        lines.add_annotation(x=growth.index[-1], y=y, text=display[t], showarrow=False,
                             xanchor="left", xshift=6, font=dict(size=11, color=theme.INK))
lines.add_hline(y=100, line=dict(color=theme.BASELINE, width=1))
lines.update_layout(height=420, yaxis_title="Growth of 100", margin=dict(r=150))
st.plotly_chart(lines, width="stretch")

# ---------------------------------------------------------------------------
# Full table
# ---------------------------------------------------------------------------
st.subheader("All sector ETFs")
names_at_source = company_data.security_names(source, tickers, market)
table = pd.concat([etfs, pd.DataFrame([{"sector": "Benchmark", "ticker": bench,
                                        "label": bench_label}])], ignore_index=True)
table = table.join(perf, on="ticker")
table["source_name"] = table["ticker"].map(names_at_source).fillna("")
ret_cols = ["ret_1D", "ret_1W", "ret_1M", "ret_3M", "ret_6M", "ret_YTD", "ret_1Y"]
st.dataframe(
    table[["sector", "ticker", *ret_cols, "vol_1Y", "mdd_1Y", "last", "label", "source_name"]],
    hide_index=True, width="stretch",
    column_config={
        "sector": st.column_config.TextColumn("Sector", width="medium"),
        "ticker": st.column_config.TextColumn("Ticker", width="small"),
        "label": st.column_config.TextColumn("ETF", width="medium"),
        "source_name": st.column_config.TextColumn(
            "Name at source", width="medium",
            help="What the data source calls this code — check it matches."),
        "last": st.column_config.NumberColumn("Last", format="localized", width="small"),
        **{c: st.column_config.NumberColumn(c.replace("ret_", ""), format="percent",
                                            width="small") for c in ret_cols},
        "vol_1Y": st.column_config.NumberColumn("Vol 1Y", format="percent", width="small",
                                                help="Annualized volatility of daily returns."),
        "mdd_1Y": st.column_config.NumberColumn("Max DD 1Y", format="percent", width="small"),
    },
)

# ---------------------------------------------------------------------------
# Leading stocks in each sector (Market Leaders scores)
# ---------------------------------------------------------------------------
st.subheader(f"Top-ranked {market} stocks by sector")
all_round, standout = pipeline.get_thresholds()
mb = pipeline.market_board(source, market, all_round, standout)
if mb is None:
    st.info(f"Build the {market} peer snapshot (Market Leaders page sidebar) to see the "
            "top-ranked stocks in each sector.", icon="ℹ️")
else:
    board = mb.board.table.join(mb.board.groups)
    top = (board[board["sector"].isin(etfs["sector"])]
           .sort_values("composite", ascending=False)
           .groupby("sector", sort=False).head(3).copy())
    by_return = dict.fromkeys(etfs.set_index("ticker").loc[sectors_ret.index, "sector"])
    top["sector_order"] = top["sector"].map({s: i for i, s in enumerate(by_return)})
    top = top.sort_values(["sector_order", "composite"], ascending=[True, False])
    top["name_shown"] = top["name_local"].fillna(top["name"]) if market == "KOSPI" else top["name"]
    top["composite"] = (top["composite"] * 100).round(0)
    shown = top.reset_index().rename(columns={"index": "ticker"})
    st.dataframe(
        shown[["sector", "ticker", "name_shown", "composite", "rank", "classification",
               "standout_in"]],
        hide_index=True, width="stretch",
        column_config={
            "sector": "Sector", "ticker": "Ticker", "name_shown": "Name",
            "composite": st.column_config.ProgressColumn("Composite", min_value=0,
                                                         max_value=100, format="%d"),
            "rank": st.column_config.NumberColumn(f"{market} rank", format="%d"),
            "classification": "Leader", "standout_in": "Standout in",
        },
    )
    st.caption(f"Up to 3 stocks per sector from the {market} peer snapshot "
               f"(prices as of {mb.meta.get('price_date', '?')}), ordered like the "
               "return chart above. US sector ETFs hold S&P 500 stocks, so NASDAQ "
               "names are a partial view of each sector.")
    st.page_link("pages/3_Market_Leaders.py", icon="🏆",
                 label="Filter by sector on the Market Leaders page →")
