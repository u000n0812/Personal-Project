"""Time-series momentum (TSMOM) reference strategy."""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_signal(prices: pd.DataFrame, params: dict) -> pd.Series:
    """Sign of the trailing ``lookback``-day return.

    +1 when the asset is above its price ``lookback`` trading days ago,
    -1 when below, 0 while there is not yet enough history.

    params:
        lookback (int): trailing window in trading days (default 120).
    """
    lookback = int(params.get("lookback", 120))
    close = prices["close"]
    trailing = close / close.shift(lookback) - 1.0
    return pd.Series(np.sign(trailing), index=prices.index).fillna(0.0)
