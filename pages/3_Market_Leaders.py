"""Page 3 — Market Leaders screen.

Ranks KOSPI and/or NASDAQ stocks (the largest companies in each market, from
the daily peer snapshots) on Value, Growth, Momentum and Quality, and flags
market leaders: stocks that rank highly on *all four* groups, or
exceptionally on *at least one*. Rankings can be market-wide or within each
sector. Scoring lives in ``factors/``; this page only renders it.
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
from factors.sector import sector_summary
from ui import factor_charts, snapshot_controls, theme
from ui.tables import search_mask

st.set_page_config(page_title="Market Leaders", page_icon="🏆", layout="wide")
theme.register_theme()
kis_mode = theme.sidebar_mode_badge(show_status=False)

st.title("🏆 Market Leaders")
st.caption(
    "Leaders rank highly across all four factors (Value, Growth, Momentum, Quality) "
    "or post an exceptionally strong score in at least one. Each stock is ranked within "
    "its own market, or within its sector."
)

# ---------------------------------------------------------------------------
# Sidebar controls
# ---------------------------------------------------------------------------
default_all, default_stand = pipeline.get_thresholds()
with st.sidebar:
    st.divider()
    market_choice = st.radio("Market", ["KOSPI", "NASDAQ", "Both"], horizontal=True,
                             key="ml_market")
    rank_scope = st.radio(
        "Rank within", ["Market", "Sector"], horizontal=True, key="ml_scope",
        help="Sector: each stock is ranked only against its own sector (sector-neutral) — "
             "e.g. banks vs banks, so structurally cheap sectors don't dominate Value. "
             f"Sectors with fewer than {config.MIN_SECTOR_SIZE} companies are ranked "
             "against the whole market.",
    ).lower()
    all_round = st.slider(
        "All-round: every factor ≥ percentile", 50, 90, int(default_all * 100), step=5,
    ) / 100
    standout = st.slider(
        "Standout: any factor ≥ percentile", 75, 99, int(default_stand * 100), step=1,
    ) / 100
    st.subheader("Peer universe")
# Non-widget key survives page switches, so other pages use the same thresholds.
st.session_state["_leader_thresholds"] = (all_round, standout)

# ---------------------------------------------------------------------------
# Score each market (holdings are added to KOSPI if not already peers)
# ---------------------------------------------------------------------------
source = pipeline.resolve_source()
markets = ["KOSPI", "NASDAQ"] if market_choice == "Both" else [market_choice]
holdings = client.get_holdings(kis_mode)
held = set(holdings["ticker"])

boards, overview_boards = [], []
for market in markets:
    extras = tuple(holdings["ticker"]) if market == "KOSPI" else ()
    with st.spinner(f"Scoring {market}…"):
        mb = pipeline.market_board(source, market, all_round, standout, rank_scope, extras)
    snapshot_controls.peer_status(source, market, mb.meta if mb else None)
    if mb is None:
        continue
    boards.append(mb)
    # Sector comparisons need market-relative percentiles even in sector mode.
    overview_boards.append(mb if rank_scope == "market" else pipeline.market_board(
        source, market, all_round, standout, "market", extras))

if source == "synthetic":
    st.info("Synthetic demo data (forced in the sidebar) — every number is made up.", icon="🧪")
missing = [m for m in markets if m not in {b.market for b in boards}]
if missing:
    st.info(f"No peer snapshot for {' and '.join(missing)} yet. Build it from the sidebar "
            "(a few minutes per market) or run `python -m data.snapshot --market "
            f"{' '.join(missing)}`.", icon="ℹ️")
if not boards:
    st.stop()
for mb in boards:
    if mb.overrides.tickers:
        st.success(f"{mb.market}: {mb.overrides.tickers} companies use values from "
                   f"`{mb.overrides.path}` ({', '.join(mb.overrides.columns)}).", icon="📄")
    if mb.failed:
        st.warning(f"Couldn't fetch {len(mb.failed)} of your holdings, so they aren't ranked: "
                   + ", ".join(mb.failed))

board = pipeline.combine(boards)
table = board.table.join(board.groups[list(GROUPS)]).join(
    board.metrics[[c for c in ("ret_3M", "ret_12M") if c in board.metrics.columns]])
table["held"] = table.index.isin(held) & (table["market"] == "KOSPI")
table["display_name"] = table["name_local"].where(
    (table["market"] == "KOSPI") & table["name_local"].notna(), table["name"]).fillna(table["name"])

# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------
held_leaders = table[table["held"] & table["leader"]]
k1, k2, k3, k4 = st.columns(4)
k1.metric("Stocks screened", f"{len(table):,}",
          help=" + ".join(f"{b.market} {len(b.board.table)}" for b in boards))
k2.metric("All-round leaders", f"{(table.classification == scoring.ALL_ROUND).sum()}",
          help=f"Every factor ≥ {all_round:.0%} percentile.")
k3.metric("Standout leaders", f"{(table.classification == scoring.STANDOUT).sum()}",
          help=f"Any factor ≥ {standout:.0%} percentile.")
k4.metric("Your holdings that lead",
          f"{len(held_leaders)} / {int(table['held'].sum())}" if "KOSPI" in markets else "—")

# ---------------------------------------------------------------------------
# Filters (one row, above every view)
# ---------------------------------------------------------------------------
f1, f2, f3 = st.columns([2, 2, 1])
query = f1.text_input("🔍 Search company or ticker", key="ml_search",
                      placeholder="e.g. 삼성, Samsung, 005930, NVDA")
sectors = sorted(table["sector"].unique())
picked_sectors = f2.multiselect("Sectors", sectors, key="ml_sectors",
                                placeholder="All sectors")
with f3:
    leaders_only = st.toggle("Leaders only", key="ml_leaders_only")
    holdings_only = st.toggle("My holdings only", key="ml_holdings_only",
                              disabled="KOSPI" not in markets)

in_sectors = table["sector"].isin(picked_sectors) if picked_sectors else pd.Series(True, table.index)
view_mask = in_sectors & search_mask(table, query)
if leaders_only:
    view_mask &= table["leader"]
if holdings_only:
    view_mask &= table["held"]
view = table[view_mask]

tab_board, tab_sectors, tab_map = st.tabs(["📋 Leaderboard", "🏭 Sectors", "🗺️ Leader map"])

# ---------------------------------------------------------------------------
# Leaderboard + drill-down
# ---------------------------------------------------------------------------
with tab_board:
    st.caption(f"Showing **{len(view):,}** of {len(table):,} stocks"
               + (f" matching “{query.strip()}”" if query.strip() else "")
               + (f" · {', '.join(picked_sectors)}" if picked_sectors else ""))
    if view.empty:
        st.info("No stocks match the current search and filters.")
    else:
        shown = view.reset_index().rename(columns={"index": "ticker"})
        for col in (*GROUPS, "composite"):
            shown[col] = (shown[col] * 100).round(0)
        shown["held"] = np.where(shown["held"], "●", "")
        # Scores first; descriptive extras (sector, scope, tags) to the right.
        cols = ["rank", *(["market"] if len(markets) > 1 else []), "ticker", "display_name",
                "composite", *GROUPS, "classification", "held", "sector",
                *(["ranked_vs"] if rank_scope == "sector" else []), "standout_in", "tags"]
        st.dataframe(
            shown[cols], hide_index=True, width="stretch",
            height=min(38 + 35 * len(shown), 560),
            column_config={
                "rank": st.column_config.NumberColumn(
                    "#", format="%d", width="small", help="Composite rank within the "
                    "stock's market (or sector, in sector mode)."),
                "market": st.column_config.TextColumn("Market", width="small"),
                "ticker": st.column_config.TextColumn("Ticker", width="small"),
                "display_name": "Name", "sector": "Sector",
                "ranked_vs": st.column_config.TextColumn("Ranked vs", width="small"),
                "held": st.column_config.TextColumn("Held", width="small"),
                "composite": st.column_config.NumberColumn("Composite", format="%d",
                                                           width="small"),
                **{g: st.column_config.NumberColumn(g, format="%d", width="small")
                   for g in GROUPS},
                "classification": "Leader", "standout_in": "Standout in", "tags": "Tags",
            },
        )
        st.caption("Factor columns are percentiles (100 = best). Composite = mean of the four. "
                   f"Blank = too little data (under {config.LEADER_MIN_COVERAGE:.0%} of a "
                   "factor's inputs). ● = in your portfolio. Click a header to sort.")

        st.subheader("Factor breakdown")
        options = list(view.index)
        pick = st.selectbox(  # no key: resets cleanly when search/filters change options
            "Stock", options,
            format_func=lambda t: f"{t} · {table.at[t, 'display_name']}"
                                  + (f" ({table.at[t, 'market']})" if len(markets) > 1 else "")
                                  + (f" — {table.at[t, 'classification']}"
                                     if table.at[t, "leader"] else ""),
        )
        pcts = board.percentiles.loc[pick]
        d1, d2 = st.columns([3, 2])
        with d1:
            st.plotly_chart(factor_charts.subfactor_bars(pcts), width="stretch")
        with d2:
            row, g = table.loc[pick], board.groups.loc[pick]
            scope_txt = (f"{row['sector']} sector" if row["ranked_vs"] == "Sector"
                         else row["market"])
            rank_txt = "n/a" if np.isnan(row["rank"]) else f"#{row['rank']:.0f}"
            st.markdown(
                f"**{row['display_name']}** · {row['sector']} · rank **{rank_txt}** of "
                f"{int(row['scope_size'])} in {scope_txt}  \n"
                + " · ".join(f"{grp} **{'n/a' if np.isnan(g[grp]) else f'{g[grp] * 100:.0f}'}**"
                             for grp in GROUPS))
            if row["leader"]:
                st.success(f"{row['classification']}"
                           + (f" — standout in {row['standout_in']}" if row["standout_in"] else ""))
            if row["tags"]:
                st.info(f"Tags: {row['tags']}")
            raw = board.metrics.loc[pick]
            order = factor_charts.SUB_FACTOR_ORDER
            st.dataframe(pd.DataFrame({
                "Input": [sf.label for sf in order],
                "Value": [format_value(sf, raw[sf.key]) for sf in order],
                "Pctl": [pcts[sf.key] * 100 for sf in order],
            }), hide_index=True, width="stretch", height=560,
                column_config={"Pctl": st.column_config.NumberColumn("Pctl", format="%.0f")})
            st.page_link("pages/4_Company_Analysis.py", icon="🔎",
                         label="Live price & full analysis on Company Analysis →")

# ---------------------------------------------------------------------------
# Sector overview (always market-relative so sectors are comparable)
# ---------------------------------------------------------------------------
with tab_sectors:
    ov = pipeline.combine(overview_boards)
    ov_table = ov.table.join(ov.groups[list(GROUPS)]).join(
        ov.metrics[[c for c in ("ret_3M", "ret_12M") if c in ov.metrics.columns]])
    if picked_sectors:
        ov_table = ov_table[ov_table["sector"].isin(picked_sectors)]
    summary = sector_summary(ov_table)
    label = summary["sector"] + (" · " + summary["market"] if len(markets) > 1 else "")

    st.caption("Median **market-relative** percentiles of each sector's stocks "
               "(50 = market median), so sectors can be compared with each other.")
    cols_h = ["composite", *GROUPS]
    heat = go.Figure(go.Heatmap(
        z=(summary[cols_h] * 100).values, x=["Composite", *GROUPS], y=label,
        zmin=0, zmax=100, zmid=50, colorscale=theme.DIVERGING,
        texttemplate="%{z:.0f}", textfont=dict(size=11), xgap=2, ygap=2,
        customdata=np.repeat(summary["companies"].values[:, None], len(cols_h), axis=1),
        hovertemplate="%{y} · %{x}: median %{z:.0f} (%{customdata} stocks)<extra></extra>",
        colorbar=dict(thickness=12, outlinewidth=0, title=dict(text="pctl", side="top")),
    ))
    heat.update_layout(height=max(320, 30 * len(summary) + 90), hovermode="closest",
                       yaxis=dict(autorange="reversed"),
                       xaxis=dict(side="top", tickangle=0), margin=dict(t=40, l=10))
    st.plotly_chart(heat, width="stretch")

    shown = summary.copy()
    for col in ("composite", *GROUPS):
        shown[col] = (shown[col] * 100).round(0)
    st.dataframe(
        shown[[*(["market"] if len(markets) > 1 else []), "sector", "companies", "leaders",
               "leader_share", "composite", *GROUPS,
               *[c for c in ("ret_3M", "ret_12M") if c in shown.columns]]],
        hide_index=True, width="stretch",
        column_config={
            "market": "Market", "sector": "Sector", "companies": "Stocks",
            "leaders": "Leaders",
            "leader_share": st.column_config.ProgressColumn(
                "Leader share", min_value=0, max_value=1, format="percent"),
            "composite": st.column_config.NumberColumn("Composite", format="%d"),
            **{g: st.column_config.NumberColumn(g, format="%d") for g in GROUPS},
            "ret_3M": st.column_config.NumberColumn("Median 3M", format="percent"),
            "ret_12M": st.column_config.NumberColumn("Median 12M", format="percent"),
        },
    )
    st.page_link("pages/5_Sector_ETFs.py", icon="📊",
                 label="Sector-level performance on the Sector ETFs page →")

# ---------------------------------------------------------------------------
# Leader map + top factor profiles (sector filter applies; search doesn't)
# ---------------------------------------------------------------------------
with tab_map:
    mapped = table[in_sectors]
    c1, c2 = st.columns([11, 9])
    with c1:
        st.subheader("Leader map")
        st.caption("Right of the dotted line: strong on **every** factor (all-round). "
                   "Above the dashed line: exceptional on **one** (standout). "
                   "Hover any point for its name.")
        plotted = mapped.dropna(subset=["breadth", "peak"])
        fig = go.Figure()
        fig.add_shape(type="rect", x0=all_round * 100, x1=101, y0=all_round * 100, y1=101,
                      fillcolor=theme.LEADER_COLORS[scoring.ALL_ROUND], opacity=0.07, line_width=0)
        fig.add_shape(type="rect", x0=0, x1=101, y0=standout * 100, y1=101,
                      fillcolor=theme.LEADER_COLORS[scoring.STANDOUT], opacity=0.07, line_width=0)
        fig.add_vline(x=all_round * 100, line=dict(color=theme.BASELINE, dash="dot", width=1))
        fig.add_hline(y=standout * 100, line=dict(color=theme.BASELINE, dash="dash", width=1))
        for cls, label_cls in (("", "Other"), (scoring.STANDOUT, scoring.STANDOUT),
                               (scoring.ALL_ROUND, scoring.ALL_ROUND)):
            sub = plotted[plotted.classification == cls]
            if sub.empty:
                continue
            # Standouts pile up along the top edge by construction, so only the
            # (few) all-rounders get text labels; hover names everything else.
            labelled = cls == scoring.ALL_ROUND
            fig.add_trace(go.Scatter(
                x=sub.breadth * 100, y=sub.peak * 100, name=label_cls,
                mode="markers+text" if labelled else "markers",
                text=sub.display_name if labelled else None, textposition="bottom center",
                textfont=dict(size=11, color=theme.INK),
                marker=dict(size=10, color=theme.LEADER_COLORS[cls],
                            line=dict(color=theme.SURFACE, width=1.5)),
                customdata=np.stack([sub.display_name, sub.sector, sub.market,
                                     sub.standout_in.replace("", "—")], axis=-1),
                hovertemplate="<b>%{customdata[0]}</b> · %{customdata[2]} · %{customdata[1]}"
                              "<br>Weakest factor: %{x:.0f}<br>Strongest factor: %{y:.0f}"
                              "<br>Standout in: %{customdata[3]}<extra></extra>",
            ))
        mine = plotted[plotted.held]
        if len(mine):
            fig.add_trace(go.Scatter(
                x=mine.breadth * 100, y=mine.peak * 100, name="Your holding", mode="markers",
                marker=dict(size=18, symbol="circle-open", color=theme.INK, line=dict(width=1.5)),
                hoverinfo="skip",
            ))
        fig.update_layout(
            height=470, hovermode="closest",
            xaxis=dict(title="Weakest factor percentile (breadth)", range=[0, 101]),
            yaxis=dict(title="Strongest factor percentile (peak)", range=[0, 104]),
        )
        st.plotly_chart(fig, width="stretch")
        if len(plotted) < len(mapped):
            st.caption(f"{len(mapped) - len(plotted)} stock(s) not plotted — a factor group "
                       "lacked enough data to score.")
    with c2:
        top_n = 15
        st.subheader(f"Top {top_n} — factor profile")
        top = mapped.dropna(subset=["composite"]).head(top_n)
        names = top.display_name + (" · " + top.market if len(markets) > 1 else "")
        heat = go.Figure(go.Heatmap(
            z=(top[list(GROUPS)] * 100).values, x=list(GROUPS), y=names,
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
# Methodology
# ---------------------------------------------------------------------------
with st.expander("Methodology & data"):
    st.markdown(f"""
**Universe.** The {config.PEER_TOP_N} largest companies by market cap in each market, from
the daily peer snapshots (Yahoo Finance; see README). Your holdings are added to KOSPI if
they aren't already in it. With *Both*, each stock is still ranked only within its own market.

**Leader rules** (percentiles within the ranking scope)
- **All-round leader** — every factor group ≥ {all_round:.0%}.
- **Standout leader** — at least one factor group ≥ {standout:.0%}.

**Rank within Sector** ranks each stock only against its own sector (Yahoo's sector
classification), so sectors that are structurally cheap or highly leveraged (e.g. banks)
don't crowd the Value or Quality rankings. Sectors with fewer than {config.MIN_SECTOR_SIZE}
companies, and unclassified stocks, are ranked against the whole market. The *Ranked vs*
column shows which applied.

**Scoring.** Each input is ranked across the scope (direction-adjusted so 100 = best;
debt-to-equity ranks lower-is-better). A factor group is the average of its inputs'
percentiles, re-ranked. A group needs ≥ {config.LEADER_MIN_COVERAGE:.0%} of its inputs,
otherwise it is blank and the stock can't be all-round.

**Tags**
- *Operating leverage* — revenue **and** operating-margin estimates both rising.
- *Value-trap risk* — Value ≥ {scoring.VALUE_TRAP_VALUE_MIN:.0%} with Growth and
  Momentum both < {scoring.VALUE_TRAP_OTHERS_MAX:.0%}.
- *Speculative risk* — Momentum ≥ {scoring.SPECULATIVE_MOMENTUM_MIN:.0%} with
  Quality < {scoring.SPECULATIVE_QUALITY_MAX:.0%}.

**Override file.** Values in `{config.FUNDAMENTALS_PATH}` (if present) replace the snapshot's
for matching tickers — e.g. real consensus revisions in place of the free-data proxies.
Columns:
""")
    st.dataframe(
        pd.DataFrame([{"Column": sf.key, "Factor": sf.group, "Unit": sf.fmt,
                       "Better": "higher" if sf.higher_is_better else "lower",
                       "Definition": sf.note} for sf in SUB_FACTORS]),
        hide_index=True, width="stretch",
    )
