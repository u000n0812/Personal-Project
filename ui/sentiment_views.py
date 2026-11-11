"""Streamlit layer for sentiment: cached computations + shared visuals.

Colors follow the app's Korean-market convention used everywhere else:
red = greed / bullish, blue = fear / bearish, gray = neutral — always with
the text label alongside, so color never carries meaning alone.
"""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
import streamlit as st

import config
from data import client
from sentiment import engine
from sentiment.model import BANDS, FAMILIES, FAMILY_NOTES, Composite, band, to_index
from ui import theme

MARKET_TTL, STOCK_TTL = 3600, 1800
BAND_COLORS = ("#2a78d6", "#86b6ef", "#d9d8d2", "#ee9a99", "#e34948")  # fear → greed


@st.cache_data(ttl=MARKET_TTL, show_spinner="Computing market mood…")
def market_mood(source: str, market: str) -> engine.MarketSentiment:
    return engine.analyze_market(source, market)


@st.cache_data(ttl=STOCK_TTL, show_spinner="Gathering sentiment sources…")
def stock_mood(source: str, ticker: str, market: str, name: str,
               name_local: str) -> engine.StockSentiment:
    kis = None
    if source != "synthetic" and market == "KOSPI" and config.has_credentials():
        try:
            kis = client._kis_client()
        except Exception:  # noqa: BLE001 — flows then show as unavailable
            kis = None
    return engine.analyze_stock(source, ticker, market, name, name_local, kis=kis)


def band_bar(index: float, height: int = 92) -> go.Figure:
    """0–100 scale split into the five Fear & Greed bands, with a marker."""
    fig = go.Figure()
    lower = 0
    for (upper, label), color in zip(BANDS, BAND_COLORS):
        upper = min(upper, 100)
        fig.add_trace(go.Bar(x=[upper - lower], y=[""], base=lower, orientation="h",
                             marker=dict(color=color, line=dict(color=theme.SURFACE, width=2)),
                             hovertemplate=f"{label}: {lower}–{upper}<extra></extra>",
                             showlegend=False))
        lower = upper
    if not np.isnan(index):
        fig.add_trace(go.Scatter(x=[index], y=[""], mode="markers+text", text=[f"{index:.0f}"],
                                 textposition="top center", textfont=dict(color=theme.INK, size=13),
                                 marker=dict(symbol="triangle-down", size=16, color=theme.INK),
                                 hoverinfo="skip", showlegend=False))
    fig.update_layout(barmode="stack", height=height, margin=dict(l=8, r=8, t=24, b=26),
                      xaxis=dict(range=[0, 100], showgrid=False, tickvals=[0, 25, 45, 55, 75, 100],
                                 tickfont=dict(size=11, color=theme.MUTED), side="bottom"),
                      yaxis=dict(showticklabels=False), hovermode="closest")
    return fig


def family_bars(composite: Composite) -> go.Figure:
    """Family scores as 0–100 bars around the neutral 50, red above / blue below."""
    fams = list(FAMILIES)
    vals = [to_index(composite.families[f]) if f in composite.families else np.nan for f in fams]
    fig = go.Figure(go.Bar(
        y=fams, x=[0 if np.isnan(v) else v - 50 for v in vals], base=50, orientation="h",
        marker=dict(color=[theme.UP if (v or 50) >= 50 else theme.DOWN for v in vals],
                    cornerradius=4),
        text=["no data" if np.isnan(v) else f"{v:.0f}" for v in vals], textposition="outside",
        cliponaxis=False,
        customdata=[FAMILY_NOTES[f] for f in fams],
        hovertemplate="%{y}: %{text}<br>%{customdata}<extra></extra>",
    ))
    fig.add_vline(x=50, line=dict(color=theme.BASELINE, width=1))
    fig.update_layout(height=260, hovermode="closest", margin=dict(l=10, r=40, t=10, b=30),
                      xaxis=dict(range=[0, 100], title="0 = bearish · 50 = neutral · 100 = bullish"),
                      yaxis=dict(autorange="reversed"))
    return fig


def compact_card(stock: engine.StockSentiment, mood: engine.MarketSentiment) -> None:
    """Small summary used on Company Analysis."""
    c = stock.composite
    gap = c.index - mood.latest if not (np.isnan(c.index) or np.isnan(mood.latest)) else np.nan
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Stock sentiment", "–" if np.isnan(c.index) else f"{c.index:.0f}",
              help="0 = extreme fear · 100 = extreme greed. Family-balanced composite.")
    k1.caption(c.label)
    k2.metric(f"{mood.name} mood", "–" if np.isnan(mood.latest) else f"{mood.latest:.0f}",
              help="Market Fear & Greed index — market-wide, not about this stock.")
    k2.caption(band(mood.latest))
    k3.metric("vs market", "–" if np.isnan(gap) else f"{gap:+.0f} pts",
              help="Stock sentiment minus market mood: the company-specific part.")
    k4.metric("Bullish share", "–" if np.isnan(c.bull_ratio) else f"{c.bull_ratio:.0%}",
              help="Bullish share of classified posts and headlines.")
    k4.caption(f"n = {c.bull_n} · {c.agreement_label.lower()}")
