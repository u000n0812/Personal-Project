"""Strategy plug-in layer.

THE CONTRACT — to add your own strategy, write one pure function:

    def compute_signal(prices: pd.DataFrame, params: dict) -> pd.Series

* ``prices``  — daily history for ONE asset, indexed by trading day.
  Guaranteed column: ``close``. May also contain ``open/high/low/volume``
  and auxiliary columns such as ``carry``. NaN rows mean "no data that day".
* ``params``  — free-form dict; the UI passes at least ``{"lookback": int}``.
* returns     — float Series on ``prices.index``. Interpreted as desired
  exposure: +1 fully long, -1 fully short, 0 flat; fractional values are
  conviction weights. NaN is treated as 0.
* NO LOOKAHEAD: the value at date *t* may only use data up to and including
  *t* — the backtest engine shifts signals one day before applying them, so
  a signal computed at Monday's close trades into Tuesday.

Then register it below and it appears in the UI select box — nothing else
in the app needs to change.
"""

from __future__ import annotations

from typing import Callable

import pandas as pd

from strategies import carry, tsmom

SignalFn = Callable[[pd.DataFrame, dict], pd.Series]

# name shown in the UI → signal function
STRATEGIES: dict[str, SignalFn] = {
    "TSMOM": tsmom.compute_signal,
    "Carry": carry.compute_signal,
}


def build_signal_panel(
    history: dict[str, pd.DataFrame], fn: SignalFn, params: dict
) -> pd.DataFrame:
    """Apply a single-asset signal function to every ticker.

    ``history`` frames must already share one index (see
    ``data.client.align_history``); the result is a dates × tickers panel.
    """
    return pd.DataFrame({t: fn(df, params) for t, df in history.items()})
