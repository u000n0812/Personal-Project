"""Chart palette, Plotly template, and shared page chrome.

Colors are a CVD-validated categorical set (fixed slot order — never cycle or
re-map when series count changes). P/L polarity follows the Korean market
convention: red = gain, blue = loss; every colored value also carries an
explicit sign so color is never the only encoding.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

import config
from data import client

# Categorical slots, fixed order (validated: worst adjacent CVD ΔE 24.2).
PALETTE = ["#2a78d6", "#1baf7a", "#eda100", "#008300",
           "#4a3aa7", "#e34948", "#e87ba4", "#eb6834"]

UP = "#e34948"      # gain — red (Korean convention)
DOWN = "#2a78d6"    # loss — blue
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"

# Diverging scale for signed values (blue ← gray → red, Korean polarity).
DIVERGING = [[0.0, DOWN], [0.5, "#f0efec"], [1.0, UP]]

# Sequential one-hue ramp for magnitudes such as percentiles (light → dark).
SEQUENTIAL = [[0.0, "#cde2fb"], [0.25, "#86b6ef"], [0.5, "#3987e5"],
              [0.75, "#1c5cab"], [1.0, "#0d366b"]]

# Factor groups → fixed categorical slots (same color on every chart).
GROUP_COLORS = {"Value": PALETTE[0], "Growth": PALETTE[1],
                "Momentum": PALETTE[2], "Quality": PALETTE[3]}

# Leader classes use slots that don't collide with group colors or P/L red.
LEADER_COLORS = {"All-round leader": PALETTE[4], "Standout leader": PALETTE[7],
                 "": MUTED}


def register_theme() -> None:
    """Install a project-wide Plotly template. Call once per page."""
    template = go.layout.Template()
    template.layout = go.Layout(
        font=dict(family='system-ui, -apple-system, "Segoe UI", sans-serif',
                  color=INK, size=13),
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        colorway=PALETTE,
        margin=dict(l=48, r=24, t=48, b=40),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="white", font_size=12),
        xaxis=dict(gridcolor=GRID, linecolor=BASELINE, zerolinecolor=BASELINE,
                   tickfont=dict(color=MUTED)),
        yaxis=dict(gridcolor=GRID, linecolor=BASELINE, zerolinecolor=BASELINE,
                   tickfont=dict(color=MUTED)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    pio.templates["quant"] = template
    pio.templates.default = "quant"


def sidebar_mode_badge(show_status: bool = True) -> str:
    """Render the data-source controls in the sidebar; return the KIS mode.

    ``show_status=False`` renders only the synthetic toggle, for pages that
    show their own data-source status.
    """
    with st.sidebar:
        st.toggle(
            "Force synthetic data",
            key="force_synthetic",
            # Off by default: without KIS keys the KIS pages fall back to synthetic
            # anyway, and the Company Analysis page needs no keys at all.
            value=st.session_state.get("force_synthetic", False),
            help="Run on the deterministic demo data even if live sources are available.",
        )
        mode = client.resolve_mode()
        if not show_status:
            return mode
        if mode == "live":
            st.success("Data source: **KIS live**", icon="🔌")
        else:
            st.info("Data source: **synthetic demo**", icon="🧪")
        if not config.has_credentials():
            st.caption("Add APP_KEY / APP_SECRET / ACCOUNT_NO to `.env` for live mode.")
    return mode


def krw(value: float) -> str:
    """₩ format with thousands separators, e.g. ₩12,345,678."""
    return f"₩{value:,.0f}"


def pct(value: float, digits: int = 2) -> str:
    return "–" if pd.isna(value) else f"{value:+.{digits}%}"
