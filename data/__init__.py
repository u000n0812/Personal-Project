"""Data-access layer.

All market data enters the app through :mod:`data.client`. It dispatches
between the live PyKis (KIS Open API) implementation and the deterministic
synthetic generator in :mod:`data.synthetic`, so every page works identically
with or without API credentials.
"""
