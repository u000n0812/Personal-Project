"""Factor charts shared by the Market Leaders and Company Analysis pages."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from factors.definitions import GROUPS, by_group
from ui import theme

SUB_FACTOR_ORDER = [sf for g in GROUPS for sf in by_group(g)]


def subfactor_bars(percentiles: pd.Series, height: int = 520) -> go.Figure:
    """Horizontal bars of one stock's sub-factor percentiles, colored by group."""
    fig = go.Figure()
    for group in GROUPS:
        sfs = by_group(group)
        vals = [percentiles.get(sf.key, np.nan) * 100 for sf in sfs]
        fig.add_trace(go.Bar(
            # NaN → zero-length bar so the "n/a" label still renders
            y=[sf.label for sf in sfs], x=np.nan_to_num(vals), orientation="h", name=group,
            marker=dict(color=theme.GROUP_COLORS[group], cornerradius=4),
            text=["n/a" if np.isnan(v) else f"{v:.0f}" for v in vals],
            textposition="outside", cliponaxis=False,
            hovertemplate="%{y}: %{x:.0f}th percentile<extra>" + group + "</extra>",
        ))
    fig.add_vline(x=50, line=dict(color=theme.BASELINE, dash="dot", width=1))
    fig.update_layout(
        height=height, hovermode="closest", bargap=0.35,
        xaxis=dict(title="Percentile in universe (100 = best)", range=[0, 108]),
        yaxis=dict(categoryorder="array", categoryarray=[sf.label for sf in SUB_FACTOR_ORDER],
                   autorange="reversed"),
    )
    return fig
