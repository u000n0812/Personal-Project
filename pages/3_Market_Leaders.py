"""Page 3 — Market Leaders screen.

Ranks a universe of Korean stocks on four factor groups (Value, Growth,
Momentum, Quality) and flags market leaders: stocks that rank highly on
*all four* groups, or exceptionally on *at least one*. Scoring lives in
``factors/``; this page only renders it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
from data import client
from factors import pipeline, scoring
from factors.definitions import GROUPS, SUB_FACTORS, format_value
from ui import factor_charts, theme

st.set_page_config(page_title="Market Leaders", page_icon="🏆", layout="wide")
theme.register_theme()
mode = theme.sidebar_mode_badge()

st.title("🏆 Market Leaders")
st.caption(
    "Leaders rank highly across all four factors — Value, Growth, Momentum, "
    "Quality — or post an exceptionally strong score in at least one. "
    "Percentiles are relative to the screened universe."
)

# ---------------------------------------------------------------------------
# Sidebar controls
# ---------------------------------------------------------------------------
default_all, default_stand = pipeline.get_thresholds()
with st.sidebar:
    st.divider()
    st.subheader("Leader screen")
    scope = st.radio(
        "Universe", ["Screening universe + holdings", "My holdings only"],
        help="Holdings-only ranks your positions against each other — "
             "'leader' then means leader within your portfolio.",
    )
    all_round = st.slider(
        "All-round: every factor ≥ percentile", 50, 90, int(default_all * 100), step=5,
    ) / 100
    standout = st.slider(
        "Standout: any factor ≥ percentile", 75, 99, int(default_stand * 100), step=1,
    ) / 100
    leaders_only = st.toggle("Show leaders only", value=False)
# Non-widget key survives page switches, so Page 1 uses the same thresholds.
st.session_state["_leader_thresholds"] = (all_round, standout)

# ---------------------------------------------------------------------------
# Score the universe
# ---------------------------------------------------------------------------
holdings = client.get_holdings(mode)
names = pipeline.resolve_universe(holdings, include_screen=scope.startswith("Screening"))
with st.spinner(f"Scoring {len(names)} stocks…"):
    board, fund = pipeline.build_leaderboard(names, mode, all_round, standout)

held = set(holdings["ticker"])
table = board.table.join(board.groups)
table["held"] = table.index.isin(held)

# Provenance — never let synthetic fundamentals pass as real.
if fund.source == "synthetic":
    msg = (f"Fundamentals are **synthetic** (no file at `{config.FUNDAMENTALS_PATH}`). "
           "Value, Growth, Quality and the estimate-based Momentum inputs are demo data")
    if mode == "live":
        st.warning(msg + "; prices are live, so only price momentum is real.", icon="⚠️")
    else:
        st.info(msg + ".", icon="🧪")
else:
    st.success(f"Fundamentals loaded from `{fund.detail}`.", icon="📄")
    if fund.missing_columns:
        st.warning("Fundamentals file is missing columns (treated as NaN): "
                   + ", ".join(f"`{c}`" for c in fund.missing_columns))
    if fund.missing_tickers:
        st.warning(f"{len(fund.missing_tickers)} ticker(s) not in the fundamentals file — "
                   "price momentum alone is too little data to score any factor group, "
                   f"so they can't qualify: {', '.join(fund.missing_tickers)}")

# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------
n_all = int((table.classification == scoring.ALL_ROUND).sum())
n_stand = int((table.classification == scoring.STANDOUT).sum())
held_leaders = table[table.held & table.leader]

k1, k2, k3, k4 = st.columns(4)
k1.metric("Stocks screened", f"{len(table)}")
k2.metric("All-round leaders", f"{n_all}", help=f"Every factor ≥ {all_round:.0%} percentile.")
k3.metric("Standout leaders", f"{n_stand}", help=f"Any factor ≥ {standout:.0%} percentile.")
k4.metric("Your holdings that lead", f"{len(held_leaders)} / {len(held & set(table.index))}")

st.divider()

# ---------------------------------------------------------------------------
# Leaderboard table
# ---------------------------------------------------------------------------
st.subheader("Leaderboard")
view = table[table.leader] if leaders_only else table
view = view.reset_index().rename(columns={"index": "ticker"})
for col in (*GROUPS, "composite"):
    view[col] = (view[col] * 100).round(0)
view["held"] = np.where(view["held"], "●", "")
st.dataframe(
    view[["rank", "ticker", "name", "held", *GROUPS, "composite",
          "classification", "standout_in", "tags"]],
    hide_index=True,
    width="stretch",
    height=min(38 + 35 * len(view), 560),
    column_config={
        "rank": st.column_config.NumberColumn("#", format="%d", width="small"),
        "ticker": "Ticker",
        "name": "Name",
        "held": st.column_config.TextColumn("Held", width="small"),
        **{g: st.column_config.ProgressColumn(g, min_value=0, max_value=100, format="%d")
           for g in GROUPS},
        "composite": st.column_config.NumberColumn("Composite", format="%d"),
        "classification": "Leader",
        "standout_in": "Standout in",
        "tags": "Tags",
    },
)
st.caption(
    "Factor columns are percentiles (100 = best in universe). Composite = mean of "
    "the four. Blank factor = too little data (under "
    f"{config.LEADER_MIN_COVERAGE:.0%} of its inputs). ● = in your portfolio."
)

# ---------------------------------------------------------------------------
# Leader map + factor heatmap
# ---------------------------------------------------------------------------
c1, c2 = st.columns([11, 9])

with c1:
    st.subheader("Leader map")
    st.caption("Right of the dotted line: strong on **every** factor (all-round). "
               "Above the dashed line: exceptional on **one** (standout). "
               "Hover any point for its name.")
    plotted = table.dropna(subset=["breadth", "peak"])
    fig = go.Figure()
    fig.add_shape(type="rect", x0=all_round * 100, x1=101, y0=all_round * 100, y1=101,
                  fillcolor=theme.LEADER_COLORS[scoring.ALL_ROUND], opacity=0.07, line_width=0)
    fig.add_shape(type="rect", x0=0, x1=101, y0=standout * 100, y1=101,
                  fillcolor=theme.LEADER_COLORS[scoring.STANDOUT], opacity=0.07, line_width=0)
    fig.add_vline(x=all_round * 100, line=dict(color=theme.BASELINE, dash="dot", width=1))
    fig.add_hline(y=standout * 100, line=dict(color=theme.BASELINE, dash="dash", width=1))
    for cls, label in (("", "Other"), (scoring.STANDOUT, scoring.STANDOUT),
                       (scoring.ALL_ROUND, scoring.ALL_ROUND)):
        sub = plotted[plotted.classification == cls]
        if sub.empty:
            continue
        # Standouts pile up along the top edge by construction, so only the
        # (few) all-rounders get text labels; hover names everything else.
        labelled = cls == scoring.ALL_ROUND
        fig.add_trace(go.Scatter(
            x=sub.breadth * 100, y=sub.peak * 100, name=label,
            mode="markers+text" if labelled else "markers",
            text=sub.name if labelled else None, textposition="bottom center",
            textfont=dict(size=11, color=theme.INK),
            marker=dict(size=11, color=theme.LEADER_COLORS[cls],
                        line=dict(color=theme.SURFACE, width=2)),
            customdata=np.stack([sub.name, sub.standout_in.replace("", "—")], axis=-1),
            hovertemplate="<b>%{customdata[0]}</b><br>Weakest factor: %{x:.0f}"
                          "<br>Strongest factor: %{y:.0f}<br>Standout in: %{customdata[1]}"
                          "<extra></extra>",
        ))
    mine = plotted[plotted.held]
    fig.add_trace(go.Scatter(
        x=mine.breadth * 100, y=mine.peak * 100, name="Your holding", mode="markers",
        marker=dict(size=19, symbol="circle-open", color=theme.INK, line=dict(width=1.5)),
        hoverinfo="skip",
    ))
    fig.update_layout(
        height=470, hovermode="closest",
        xaxis=dict(title="Weakest factor percentile (breadth)", range=[0, 101]),
        yaxis=dict(title="Strongest factor percentile (peak)", range=[0, 104]),
    )
    st.plotly_chart(fig, width="stretch")
    if len(plotted) < len(table):
        st.caption(f"{len(table) - len(plotted)} stock(s) not plotted — a factor group "
                   "lacked enough data to score.")

with c2:
    top_n = 15
    st.subheader(f"Top {top_n} — factor profile")
    top = table.dropna(subset=["composite"]).head(top_n)
    heat = go.Figure(go.Heatmap(
        z=(top[list(GROUPS)] * 100).values, x=list(GROUPS), y=top.name,
        zmin=0, zmax=100, colorscale=theme.SEQUENTIAL,
        texttemplate="%{z:.0f}", textfont=dict(size=11),
        hovertemplate="%{y} · %{x}: %{z:.0f}<extra></extra>",
        colorbar=dict(thickness=12, outlinewidth=0, title=dict(text="pctl", side="top")),
        xgap=2, ygap=2,
    ))
    heat.update_layout(height=470, hovermode="closest", yaxis=dict(autorange="reversed"),
                       xaxis=dict(side="top", tickangle=0, tickfont=dict(size=11)),
                       margin=dict(t=40))
    st.plotly_chart(heat, width="stretch")

# ---------------------------------------------------------------------------
# Drill-down: one stock's sub-factor breakdown
# ---------------------------------------------------------------------------
st.subheader("Factor breakdown")
options = list(table.index)
default_pick = options.index(held_leaders.index[0]) if len(held_leaders) else 0
pick = st.selectbox(
    "Stock", options, index=default_pick,
    format_func=lambda t: f"{t} · {table.at[t, 'name']}"
                          + (f" — {table.at[t, 'classification']}" if table.at[t, "leader"] else ""),
)

order = factor_charts.SUB_FACTOR_ORDER
pcts = board.percentiles.loc[pick]
d1, d2 = st.columns([3, 2])

with d1:
    st.plotly_chart(factor_charts.subfactor_bars(pcts), width="stretch")

with d2:
    row = board.table.loc[pick]
    g = board.groups.loc[pick]
    rank_txt = "n/a" if np.isnan(row["rank"]) else f"#{row['rank']:.0f}"
    st.markdown(
        f"**{row['name']}** · composite rank **{rank_txt}** of {len(table)}  \n"
        + " · ".join(f"{grp} **{'n/a' if np.isnan(g[grp]) else f'{g[grp] * 100:.0f}'}**"
                     for grp in GROUPS)
    )
    if row["leader"]:
        st.success(f"{row['classification']}"
                   + (f" — standout in {row['standout_in']}" if row["standout_in"] else ""))
    if row["tags"]:
        st.info(f"Tags: {row['tags']}")
    raw = board.metrics.loc[pick]
    detail = pd.DataFrame({  # same row order as the chart; group = bar color
        "Input": [sf.label for sf in order],
        "Value": [format_value(sf, raw[sf.key]) for sf in order],
        "Pctl": [pcts[sf.key] * 100 for sf in order],
    })
    st.dataframe(detail, hide_index=True, width="stretch", height=560,
                 column_config={"Pctl": st.column_config.NumberColumn("Pctl", format="%.0f")})
    rets = {k: raw.get(f"ret_{k}") for k in ("1M", "3M", "6M", "12M")}
    st.caption("Returns — " + " · ".join(
        f"{k}: {theme.pct(v, 1)}" for k, v in rets.items())
        + f" · trend agreement {raw.get('trend_agreement', np.nan):.0%}")

# ---------------------------------------------------------------------------
# Methodology
# ---------------------------------------------------------------------------
with st.expander("Methodology & data schema"):
    st.markdown(f"""
**Leader rules** (percentiles within the screened universe)
- **All-round leader** — every factor group ≥ {all_round:.0%}.
- **Standout leader** — at least one factor group ≥ {standout:.0%}.

**Scoring.** Each input is ranked across the universe (direction-adjusted so
100 = best; debt-to-equity ranks lower-is-better). A factor group is the
average of its inputs' percentiles, re-ranked to a percentile. A group needs
≥ {config.LEADER_MIN_COVERAGE:.0%} of its inputs present, otherwise it is blank
and the stock cannot qualify as all-round.

**Tags**
- *Operating leverage* — revenue **and** operating-margin estimates both
  rising: the phase where leaders' prices tend to accelerate.
- *Value-trap risk* — Value ≥ {scoring.VALUE_TRAP_VALUE_MIN:.0%} with Growth and
  Momentum both < {scoring.VALUE_TRAP_OTHERS_MAX:.0%}: cheap without a catalyst.
- *Speculative risk* — Momentum ≥ {scoring.SPECULATIVE_MOMENTUM_MIN:.0%} with
  Quality < {scoring.SPECULATIVE_QUALITY_MAX:.0%}: a theme-driven run on weak fundamentals.

**Price momentum** averages the ranks of 1/3/6/12-month returns, then shrinks
toward neutral by how much the horizons disagree in direction.

**Inputs** — supply these columns in `{config.FUNDAMENTALS_PATH}` (fractions;
`pp` = percentage-point change as a fraction):
""")
    st.dataframe(
        pd.DataFrame([{"Column": sf.key, "Factor": sf.group, "Unit": sf.fmt,
                       "Better": "higher" if sf.higher_is_better else "lower",
                       "Definition": sf.note} for sf in SUB_FACTORS]),
        hide_index=True, width="stretch",
    )
