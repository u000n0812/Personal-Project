"""Market-data providers for the Company Analysis page (see ``base.py``)."""

from __future__ import annotations

from data.providers.base import CompanyData, Provider, Quote, describe_freshness

PROVIDERS = ("yahoo", "synthetic")


def get_provider(name: str) -> Provider:
    """Instantiate a provider by name. Yahoo needs `yfinance` and
    `finance-datareader`; ImportError propagates so callers can fall back."""
    if name == "yahoo":
        from data.providers.yahoo import YahooProvider

        return YahooProvider()
    if name == "synthetic":
        from data.providers.demo import SyntheticProvider

        return SyntheticProvider()
    raise ValueError(f"Unknown provider {name!r}; expected one of {PROVIDERS}")


__all__ = ["CompanyData", "Provider", "Quote", "describe_freshness", "get_provider", "PROVIDERS"]
