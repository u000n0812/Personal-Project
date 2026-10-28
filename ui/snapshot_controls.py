"""Sidebar peer-snapshot status + build button, shared by pages that rank."""

from __future__ import annotations

import streamlit as st

import config
from data import company as company_data


def peer_status(source: str, market: str, meta: dict | None) -> None:
    """Render the snapshot state for ``market`` in the sidebar, with a button
    that (re)builds it from Yahoo. ``meta`` is None when no snapshot exists."""
    with st.sidebar:
        if meta is not None:
            st.caption(f"**{market}** · {meta.get('companies', '?'):,} largest companies · "
                       f"prices as of {meta.get('price_date', '?')} · {meta.get('provider', '')}")
            age = company_data.snapshot_age_days(meta)
            if source == "yahoo" and age is not None and age > config.SNAPSHOT_STALE_DAYS:
                st.warning(f"{market} snapshot is {age} days old — rebuild for current rankings.")
        else:
            st.warning(f"No {market} peer snapshot yet.")
        if source == "yahoo" and st.button(
            f"{'Rebuild' if meta else 'Build'} {market} snapshot (top {config.PEER_TOP_N})",
            key=f"build_{market}",
            help="Fetches every peer from Yahoo (a few minutes). "
                 "Or schedule `python -m data.snapshot`.",
        ):
            bar = st.progress(0.0, text="Fetching listing and prices…")
            try:
                built = company_data.rebuild_peers(market, bar)
                st.success(f"Built: {built['companies']} companies, {len(built['failed'])} failed.")
                st.rerun()
            except Exception as err:  # noqa: BLE001
                st.error(f"Snapshot build failed — {type(err).__name__}: {err}")
