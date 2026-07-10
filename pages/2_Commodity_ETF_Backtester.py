"""Page 2 — Commodity ETF Strategy Backtester.

Every sidebar change reruns the (cached-data, vectorized) pipeline instantly:
fetch → align → signal → backtest → charts. Strategy logic is pluggable via
``strategies/`` — this page never looks inside a signal function.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
import strategies
from backtest import drawdown_series, run_backtest
from data import client
from strategies import carry as carry_mod
from ui import theme

st.set_page_config(page_title="ETF Backtester", page_icon="🧪", layout="wide")
theme.register_theme()
mode = theme.sidebar_mode_badge()

st.title("🧪 Commodity ETF Strategy Backtester")

# ---------------------------------------------------------------------------
# Sidebar controls — Streamlit reruns this script on every change
# ---------------------------------------------------------------------------
with st.sidebar:
    st.divider()
    st.subheader("Backtest settings")
    tickers = st.multiselect(
        "ETF universe (placeholders — edit `config.py`)",
        options=list(config.COMMODITY_ETFS),
        default=list(config.COMMODITY_ETFS),
        format_func=lambda t: f"{t} · {config.COMMODITY_ETFS[t].split(' — ')[0]}",
    )
    strategy_name = st.selectbox("Strategy", list(strategies.STRATEGIES))
    lookback = st.slider("Lookback (trading days)", 20, 252, config.DEFAULT_LOOKBACK, step=5)
    rebalance = st.selectbox("Rebalancing", ["daily", "weekly", "monthly"], index=2)
    cost_bps = st.number_input(
        "Transaction cost (bps, one-way)", 0.0, 100.0, config.DEFAULT_COST_BPS, step=1.0
    )
    years = st.slider("History (years)", 1, 10, config.DEFAULT_HISTORY_YEARS)

if not tickers:
    st.info("Select at least one ETF in the sidebar to run a backtest.")
    st.stop()

# ---------------------------------------------------------------------------
# Data → aligned panel → signals → weights
# ---------------------------------------------------------------------------
end = pd.Timestamp.today().normalize()
start = end - pd.DateOffset(years=years)

history = {t: client.get_ohlcv(t, start, end, mode) for t in tickers}
close = client.build_close_panel(history)
aligned = client.align_history(history, close.index)

params = {"lookback": lookback}
signal_fn = strategies.STRATEGIES[strategy_name]
signals = strategies.build_signal_panel(aligned, signal_fn, params)

if strategy_name == "Carry":
    # Carry returns continuous scores: rank cross-sectionally over a basket
    # (long high carry / short low carry), or take the sign for one asset.
    signals = (
        carry_mod.rank_weights(signals) if len(tickers) > 1
        else np.sign(signals)
    )
else:
    # Directional signals (±1 per asset) → equal capital split.
    signals = signals / len(tickers)

if len(close.dropna(how="all")) <= lookback:
    st.warning(
        f"Only {len(close)} trading days of history for a {lookback}-day lookback — "
        "extend the history range or shorten the lookback."
    )
    st.stop()

result = run_backtest(close, signals, rebalance=rebalance, cost_bps=cost_bps)

# ---------------------------------------------------------------------------
# KPI cards (deltas compare against buy-and-hold)
# ---------------------------------------------------------------------------
FMT = {
    "CAGR": lambda v: theme.pct(v, 2),
    "Sharpe": lambda v: "–" if pd.isna(v) else f"{v:.2f}",
    "Max Drawdown": lambda v: theme.pct(v, 1),
    "Volatility": lambda v: f"{v:.1%}",
    "Hit Ratio": lambda v: "–" if pd.isna(v) else f"{v:.1%}",
}
cols = st.columns(len(result.metrics))
for col, (name, value) in zip(cols, result.metrics.items()):
    bench_value = result.benchmark_metrics.get(name)
    delta = None
    if bench_value is not None and not (pd.isna(value) or pd.isna(bench_value)):
        diff = value - bench_value
        delta = (f"{diff:+.2f}" if name == "Sharpe" else f"{diff:+.2%}") + " vs B&H"
    # Max Drawdown is negative, so a positive delta (shallower drawdown) is
    # good → "normal". Only Volatility reads better when lower.
    col.metric(name, FMT[name](value), delta=delta,
               delta_color="inverse" if name == "Volatility" else "normal")

st.caption(
    f"{strategy_name} · {lookback}d lookback · {rebalance} rebalance · "
    f"{cost_bps:.0f} bps costs · {len(result.equity)} trading days · "
    "benchmark = equal-weight buy-and-hold of the selected ETFs."
)

# ---------------------------------------------------------------------------
# Equity curve: strategy vs. buy-and-hold
# ---------------------------------------------------------------------------
st.subheader("Equity curve")
eq = go.Figure()
eq.add_trace(go.Scatter(
    x=result.benchmark.index, y=result.benchmark, name="Buy & hold",
    line=dict(color=theme.MUTED, width=2, dash="dash"),
    hovertemplate="%{y:.3f}<extra>Buy & hold</extra>",
))
eq.add_trace(go.Scatter(
    x=result.equity.index, y=result.equity, name=strategy_name,
    line=dict(color=theme.PALETTE[0], width=2),
    hovertemplate="%{y:.3f}<extra>" + strategy_name + "</extra>",
))
eq.update_layout(height=420, yaxis_title="Growth of ₩1", xaxis_title=None)
st.plotly_chart(eq, width="stretch")

# ---------------------------------------------------------------------------
# Drawdown (underwater) chart
# ---------------------------------------------------------------------------
st.subheader("Drawdown")
dd = drawdown_series(result.equity)
uw = go.Figure(go.Scatter(
    x=dd.index, y=dd, name="Drawdown",
    line=dict(color=theme.DOWN, width=2),
    fill="tozeroy", fillcolor="rgba(42, 120, 214, 0.18)",
    hovertemplate="%{y:.1%}<extra>Drawdown</extra>",
))
uw.update_layout(height=280, yaxis_title="Drawdown", yaxis_tickformat=".0%")
st.plotly_chart(uw, width="stretch")

# ---------------------------------------------------------------------------
# Table views (accessibility + sanity-checking)
# ---------------------------------------------------------------------------
with st.expander("Data tables — monthly returns & current weights"):
    monthly = pd.DataFrame({
        strategy_name: result.returns.add(1).resample("ME").prod().sub(1),
        "Buy & hold": result.benchmark_returns.add(1).resample("ME").prod().sub(1),
    })
    monthly.index = monthly.index.strftime("%Y-%m")
    st.dataframe(
        monthly.style.format("{:+.2%}"),
        width="stretch",
        height=300,
    )
    latest = result.weights.iloc[-1].rename("weight").to_frame()
    latest["name"] = [config.COMMODITY_ETFS.get(t, t) for t in latest.index]
    st.dataframe(
        latest[["name", "weight"]],
        width="stretch",
        column_config={"weight": st.column_config.NumberColumn("Current weight", format="percent")},
    )
