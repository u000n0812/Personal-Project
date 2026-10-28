"""Daily peer snapshots: the top-N companies by market cap in each market,
with every factor input, saved as Parquet.

Ranking one company "against the market" needs fundamentals for hundreds of
peers. Fetching those on every page load would be slow and would hit Yahoo's
rate limits, so peers are built once per trading day (CLI below, or the
button on the Company Analysis page) and the page reads the latest file.
The *selected* company is always fetched live.

    python -m data.snapshot --market KOSPI NASDAQ          # top PEER_TOP_N each
    python -m data.snapshot --market NASDAQ --top 100

Schedule it after the close, e.g. cron (KST):
    0 17 * * 1-5  cd /path/to/app && python -m data.snapshot --market KOSPI
    0 7  * * 2-6  cd /path/to/app && python -m data.snapshot --market NASDAQ

No Streamlit imports here, so it runs standalone.
"""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from typing import Callable

import pandas as pd

import config
from data.providers import Provider, get_provider
from factors.price import trailing_returns

PRICE_HISTORY_DAYS = 400   # ~13 months → enough trading days for the 12M return
_RETRY_WAITS = (5, 20, 60)  # seconds, on rate-limit errors


def _with_retry(fn: Callable, *args):
    """Retry on provider rate limits with backoff; other errors propagate."""
    for wait in (*_RETRY_WAITS, None):
        try:
            return fn(*args)
        except Exception as err:  # noqa: BLE001
            if wait is None or "RateLimit" not in type(err).__name__:
                raise
            time.sleep(wait)


def build(
    provider: Provider,
    market: str,
    top_n: int = config.PEER_TOP_N,
    on_progress: Callable[[int, int, str], None] | None = None,
    workers: int = 4,
) -> tuple[pd.DataFrame, dict]:
    """Fetch the top-``top_n`` peers of ``market``. Returns (frame, meta).

    Frame: index ticker; columns name, name_local, sector, industry, currency,
    market_cap, FUNDAMENTAL_COLUMNS, ret_1M…ret_12M. Companies whose fetch
    fails are skipped and listed in ``meta["failed"]``.
    """
    listing = provider.listing(market).head(top_n)
    tickers = list(listing["ticker"])

    start = pd.Timestamp.today().normalize() - pd.Timedelta(days=PRICE_HISTORY_DAYS)
    close = _with_retry(provider.closes, tickers, market, start)
    close = close.ffill(limit=config.MAX_FFILL_DAYS)
    returns = trailing_returns(close)

    rows, failed = {}, {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_with_retry, provider.company, t, market): t for t in tickers}
        for done, future in enumerate(as_completed(futures), start=1):
            ticker = futures[future]
            try:
                data = future.result()
                row = {k: v for k, v in asdict(data).items() if k not in ("metrics", "notes")}
                rows[ticker] = {**row, **data.metrics}
            except Exception as err:  # noqa: BLE001
                failed[ticker] = f"{type(err).__name__}: {err}"[:200]
            if on_progress:
                on_progress(done, len(tickers), ticker)

    if not rows:
        sample = "; ".join(f"{t}: {e}" for t, e in list(failed.items())[:3])
        raise RuntimeError(f"Every {market} company fetch failed — e.g. {sample}")
    frame = pd.DataFrame.from_dict(rows, orient="index").drop(columns=["ticker", "market"],
                                                              errors="ignore")
    frame.index.name = "ticker"
    frame = frame.join(returns)
    # Listing name is the local one (Korean for KOSPI) — kept for search/display
    # next to the provider's (English) name.
    names = listing.set_index("ticker")["name"]
    frame["name_local"] = names.reindex(frame.index)
    frame["name"] = frame["name"].fillna(frame["name_local"])

    price_date = close.dropna(how="all").index.max()
    meta = {
        "market": market,
        "provider": provider.name,
        "top_n": top_n,
        "price_date": None if pd.isna(price_date) else price_date.date().isoformat(),
        "built_at": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"),
        "companies": len(frame),
        "failed": failed,
    }
    return frame, meta


def _dir(market: str) -> Path:
    return config.SNAPSHOT_DIR / market


def save(frame: pd.DataFrame, meta: dict) -> Path:
    """Write ``<SNAPSHOT_DIR>/<market>/<price_date>.parquet`` + a .json sidecar."""
    folder = _dir(meta["market"])
    folder.mkdir(parents=True, exist_ok=True)
    stem = meta["price_date"] or pd.Timestamp.today().date().isoformat()
    path = folder / f"{stem}.parquet"
    frame.to_parquet(path)
    path.with_suffix(".json").write_text(json.dumps(meta, indent=2))
    return path


def latest_path(market: str) -> Path | None:
    files = sorted(_dir(market).glob("*.parquet"))
    return files[-1] if files else None


def load(path: Path) -> tuple[pd.DataFrame, dict]:
    meta_path = path.with_suffix(".json")
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    return pd.read_parquet(path), meta


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--market", nargs="+", choices=list(config.MARKETS), required=True)
    parser.add_argument("--top", type=int, default=config.PEER_TOP_N)
    parser.add_argument("--provider", default="yahoo")
    args = parser.parse_args()

    provider = get_provider(args.provider)
    for market in args.market:
        t0 = time.time()

        def progress(done: int, total: int, ticker: str) -> None:
            if done % 25 == 0 or done == total:
                print(f"  {market}: {done}/{total} ({ticker})", flush=True)

        print(f"Building {market} peer snapshot (top {args.top}) from {provider.name}…")
        frame, meta = build(provider, market, args.top, on_progress=progress)
        path = save(frame, meta)
        print(f"  → {path}  ({meta['companies']} companies, {len(meta['failed'])} failed, "
              f"{time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
