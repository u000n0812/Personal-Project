"""Price-derived inputs for the Momentum group."""

from __future__ import annotations

import numpy as np
import pandas as pd

# label → trading days
HORIZONS: dict[str, int] = {"1M": 21, "3M": 63, "6M": 126, "12M": 252}


def trailing_returns(close: pd.DataFrame, horizons: dict[str, int] = HORIZONS) -> pd.DataFrame:
    """Trailing simple returns as of the last row of an aligned close panel.

    Returns a tickers × ``ret_<label>`` frame. A horizon longer than the
    available history — or a NaN price at either end — yields NaN rather
    than a return over a shorter window.
    """
    last = close.iloc[-1]
    out = {}
    for label, days in horizons.items():  # one vectorized column per horizon
        if len(close) > days:
            out[f"ret_{label}"] = last / close.iloc[-1 - days] - 1.0
        else:
            out[f"ret_{label}"] = pd.Series(np.nan, index=close.columns)
    return pd.DataFrame(out)


def price_momentum(returns: pd.DataFrame) -> pd.DataFrame:
    """Combine multi-horizon returns into one momentum score.

    1–3 month returns capture current attention; 6–12 month returns show
    whether it is a sustained trend. When they point the same way the signal
    is more reliable, so:

        score = 0.5 + (mean cross-sectional rank − 0.5) × agreement
        agreement = |#up − #down| / #horizons available   (0 … 1)

    Fully aligned horizons keep their full rank; a 2-up/2-down split is
    pulled all the way to neutral.
    """
    mean_rank = returns.rank(pct=True).mean(axis=1)
    n = returns.notna().sum(axis=1).replace(0, np.nan)
    agreement = np.sign(returns).sum(axis=1).abs() / n
    return pd.DataFrame({
        "price_momentum": 0.5 + (mean_rank - 0.5) * agreement,
        "trend_agreement": agreement,
    })
