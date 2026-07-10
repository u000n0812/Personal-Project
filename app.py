"""Korean-Market Quant Dashboard — entry point.

Run with:  streamlit run app.py
"""

import streamlit as st

import config
from ui import theme

st.set_page_config(
    page_title="Korean Quant Dashboard",
    page_icon="📈",
    layout="wide",
)

theme.register_theme()
mode = theme.sidebar_mode_badge()

st.title("📈 Korean-Market Quant Dashboard")
st.caption("Portfolio monitoring + commodity-ETF strategy backtesting on the KIS Open API.")

if mode == "synthetic":
    st.info(
        "Running in **synthetic-data mode** — every chart works on a deterministic "
        "demo dataset. Copy `.env.example` to `.env` and add your KIS credentials "
        "to switch to live data.",
        icon="🧪",
    )

col1, col2 = st.columns(2)
with col1:
    st.subheader("📊 Portfolio Dashboard")
    st.write(
        "Live holdings with unrealized P/L, portfolio weights, and per-holding "
        "factor exposures (momentum & carry)."
    )
    st.page_link("pages/1_Portfolio_Dashboard.py", label="Open Portfolio Dashboard →")
with col2:
    st.subheader("🧪 Commodity ETF Backtester")
    st.write(
        "TSMOM and carry strategies over Korean-listed commodity ETFs, with "
        "instant re-runs on every parameter change."
    )
    st.page_link("pages/2_Commodity_ETF_Backtester.py", label="Open Backtester →")

st.divider()
st.markdown(
    f"""
    **Plugging in your own strategy** — drop a `compute_signal(prices, params) -> pd.Series`
    function into `strategies/` and register it in `strategies/__init__.py`; the UI picks
    it up automatically. The ETF universe ({len(config.COMMODITY_ETFS)} placeholder tickers)
    lives in `config.py`. Details in the README.
    """
)
