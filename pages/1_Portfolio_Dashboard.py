"""Page 1 — Portfolio Dashboard.

Live holdings from PyKis (or the synthetic sample), with P/L breakdown,
portfolio weights, and per-holding factor exposures (momentum + carry).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
from data import client
from strategies import carry as carry_mod
from ui import theme

st.set_page_config(page_title="Portfolio Dashboard", page_icon="📊", layout="wide")
theme.register_theme()
mode = theme.sidebar_mode_badge()

st.title("📊 Portfolio Dashboard")

# ---------------------------------------------------------------------------
# Holdings snapshot + derived columns
# ---------------------------------------------------------------------------
holdings = client.get_holdings(mode)
if holdings.empty:
    st.warning("No holdings returned — nothing to display.")
    st.stop()

holdings = holdings.assign(
    market_value=lambda d: d.quantity * d.current_price,
    cost_value=lambda d: d.quantity * d.avg_price,
)
holdings["pl_krw"] = holdings.market_value - holdings.cost_value
holdings["pl_pct"] = holdings.pl_krw / holdings.cost_value
holdings["weight"] = holdings.market_value / holdings.market_value.sum()
holdings = holdings.sort_values("market_value", ascending=False).reset_index(drop=True)

# ---------------------------------------------------------------------------
# Factor exposures: trailing momentum + carry proxy per holding
# ---------------------------------------------------------------------------
window = st.sidebar.selectbox(
    "Momentum window (trading days)", config.MOMENTUM_WINDOWS, index=2
)

end = pd.Timestamp.today().normalize()
start = end - pd.Timedelta(days=int(max(config.MOMENTUM_WINDOWS) * 2.2))

momentum, carry_vals = {}, {}
for ticker in holdings.ticker:
    df = client.get_ohlcv(ticker, start, end, mode)
    close = df["close"].dropna()
    if len(close) > window:
        momentum[ticker] = float(close.iloc[-1] / close.iloc[-(window + 1)] - 1.0)
    else:
        momentum[ticker] = np.nan
    # Carry proxy — synthetic data ships a real column; live mode uses the
    # placeholder in strategies/carry.py until the real source is wired in.
    carry_vals[ticker] = float(carry_mod.carry_score(df, {}).iloc[-1])

holdings["momentum"] = holdings.ticker.map(momentum)
holdings["carry"] = holdings.ticker.map(carry_vals)


def zscore(s: pd.Series) -> pd.Series:
    sd = s.std(ddof=0)
    return (s - s.mean()) / sd if sd and not np.isnan(sd) else s * 0.0


holdings["momentum_z"] = zscore(holdings.momentum)
holdings["carry_z"] = zscore(holdings.carry)

# ---------------------------------------------------------------------------
# KPI row
# ---------------------------------------------------------------------------
total_mv = holdings.market_value.sum()
total_pl_pct = holdings.pl_krw.sum() / holdings.cost_value.sum()
port_momentum = float((holdings.weight * holdings.momentum).sum())

k1, k2, k3 = st.columns(3)
k1.metric("Total market value", theme.krw(total_mv))
k2.metric("Unrealized P/L", theme.krw(holdings.pl_krw.sum()), delta=theme.pct(total_pl_pct))
k3.metric(
    f"Portfolio momentum ({window}d)",
    theme.pct(port_momentum),
    help="Value-weighted trailing return across holdings.",
)

st.divider()

# ---------------------------------------------------------------------------
# Holdings table
# ---------------------------------------------------------------------------
st.subheader("Holdings")
display = holdings.copy()
for col in ("avg_price", "current_price", "market_value", "pl_krw"):
    display[col] = display[col].round(0)  # whole ₩ in the table
st.dataframe(
    display[["ticker", "name", "quantity", "avg_price", "current_price",
             "market_value", "pl_krw", "pl_pct", "weight"]],
    hide_index=True,
    width="stretch",
    column_config={
        "ticker": "Ticker",
        "name": "Name",
        "quantity": st.column_config.NumberColumn("Qty", format="localized"),
        "avg_price": st.column_config.NumberColumn("Avg price (₩)", format="localized"),
        "current_price": st.column_config.NumberColumn("Price (₩)", format="localized"),
        "market_value": st.column_config.NumberColumn("Market value (₩)", format="localized"),
        "pl_krw": st.column_config.NumberColumn("P/L (₩)", format="localized"),
        "pl_pct": st.column_config.NumberColumn("P/L (%)", format="percent"),
        "weight": st.column_config.ProgressColumn("Weight", format="percent",
                                                  min_value=0, max_value=1),
    },
)

# ---------------------------------------------------------------------------
# Weights donut + P/L bars
# ---------------------------------------------------------------------------
c1, c2 = st.columns(2)

with c1:
    st.subheader("Portfolio weights")
    top = holdings.head(8)
    labels = list(top.name)
    values = list(top.market_value)
    colors = theme.PALETTE[: len(top)]
    if len(holdings) > 8:  # fold the tail into "Other" — never invent a 9th hue
        labels.append("Other")
        values.append(holdings.market_value.iloc[8:].sum())
        colors.append(theme.MUTED)
    donut = go.Figure(
        go.Pie(labels=labels, values=values, hole=0.55, sort=False,
               marker=dict(colors=colors, line=dict(color=theme.SURFACE, width=2)),
               textinfo="label+percent", textposition="outside",
               hovertemplate="%{label}<br>%{value:,.0f}₩ · %{percent}<extra></extra>")
    )
    donut.update_layout(showlegend=False, height=380,
                        margin=dict(l=120, r=120, t=30, b=30))
    st.plotly_chart(donut, width="stretch")

with c2:
    st.subheader("Unrealized P/L by holding")
    st.caption("Red = gain, blue = loss (Korean market convention); signs are explicit.")
    pl = holdings.sort_values("pl_krw")
    bar = go.Figure(
        go.Bar(
            x=pl.pl_krw, y=pl.name, orientation="h",
            marker_color=[theme.UP if v >= 0 else theme.DOWN for v in pl.pl_krw],
            text=[theme.pct(v) for v in pl.pl_pct], textposition="auto",
            cliponaxis=False,
            hovertemplate="%{y}<br>%{x:,.0f}₩<extra></extra>",
        )
    )
    bar.update_layout(height=380, hovermode="y", margin=dict(r=80),
                      xaxis_title="Unrealized P/L (₩)", yaxis_title=None)
    st.plotly_chart(bar, width="stretch")

# ---------------------------------------------------------------------------
# Factor exposures
# ---------------------------------------------------------------------------
st.subheader("Factor exposures")
st.caption(
    "Momentum = trailing return over the selected window. Carry = annualized "
    "carry proxy (placeholder until the real roll-yield source is wired in — "
    "see `strategies/carry.py`)."
)

f1, f2 = st.columns([3, 2])

with f1:
    st.dataframe(
        holdings[["ticker", "name", "weight", "momentum", "momentum_z", "carry", "carry_z"]],
        hide_index=True,
        width="stretch",
        column_config={
            "ticker": "Ticker",
            "name": "Name",
            "weight": st.column_config.NumberColumn("Weight", format="percent"),
            "momentum": st.column_config.NumberColumn(f"Momentum {window}d", format="percent"),
            "momentum_z": st.column_config.NumberColumn("Mom z", format="%.2f"),
            "carry": st.column_config.NumberColumn("Carry (ann.)", format="percent"),
            "carry_z": st.column_config.NumberColumn("Carry z", format="%.2f"),
        },
    )

with f2:
    z = holdings.set_index("name")[["momentum_z", "carry_z"]]
    heat = go.Figure(
        go.Heatmap(
            z=z.values, x=["Momentum (z)", "Carry (z)"], y=z.index,
            colorscale=theme.DIVERGING, zmid=0.0,
            texttemplate="%{z:.2f}", textfont=dict(size=11),
            hovertemplate="%{y} · %{x}: %{z:.2f}<extra></extra>",
            colorbar=dict(thickness=12, outlinewidth=0),
        )
    )
    heat.update_layout(height=max(300, 34 * len(z)), hovermode="closest",
                       yaxis=dict(autorange="reversed"))
    st.plotly_chart(heat, width="stretch")

# ---------------------------------------------------------------------------
# Account NAV (only when the live endpoint provides it)
# ---------------------------------------------------------------------------
nav = client.get_daily_nav(mode)
if nav is not None and len(nav) > 1:
    st.subheader("Account NAV")
    fig = go.Figure(
        go.Scatter(x=nav.index, y=nav.values, mode="lines",
                   line=dict(color=theme.PALETTE[0], width=2), name="NAV")
    )
    fig.update_layout(height=300, yaxis_title="NAV (₩)")
    st.plotly_chart(fig, width="stretch")
