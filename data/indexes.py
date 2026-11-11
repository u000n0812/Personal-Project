"""Index membership — currently the Nasdaq-100.

Membership changes (annual reconstitution each December, plus replacements
during the year), so it is fetched, not hardcoded:

1. Nasdaq's own constituent list (api.nasdaq.com)
2. Wikipedia's Nasdaq-100 article (constituents table)
3. The last list fetched successfully, cached next to the peer snapshots

One security per company: share-class duplicates (GOOG next to GOOGL) are
folded into a single line, so the list is the index's 100 companies.

Parsing is separated from fetching so it can be tested offline. No
Streamlit imports here (the snapshot CLI uses this module).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pandas as pd

import config

NASDAQ_100 = "NDX"
NASDAQ_API_URL = "https://api.nasdaq.com/api/quote/list-type/nasdaq100"
WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/Nasdaq-100"
_TIMEOUT = 20
_BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
_WIKI_UA = "PersonalProject-QuantDashboard/1.0 (local research tool)"

# Secondary share classes → the class kept as the company's one line.
SHARE_CLASS_ALIASES = {"GOOG": "GOOGL"}


@dataclass
class Members:
    frame: pd.DataFrame          # columns: ticker, name
    source: str                  # "Nasdaq" | "Wikipedia" | "cache (…)" | "synthetic"
    as_of: str                   # ISO date the list was fetched


# ---------------------------------------------------------------------------
# Parsing (pure)
# ---------------------------------------------------------------------------


def _find_rows(node: Any) -> list[dict]:
    """First list of dicts carrying a 'symbol' key anywhere in a JSON tree —
    robust to Nasdaq reshuffling the envelope around the rows."""
    if isinstance(node, list) and node and isinstance(node[0], dict) and "symbol" in node[0]:
        return node
    children = node.values() if isinstance(node, dict) else node if isinstance(node, list) else []
    for child in children:
        found = _find_rows(child)
        if found:
            return found
    return []


def normalize(frame: pd.DataFrame) -> pd.DataFrame:
    """Uppercase tickers, Yahoo-style class separator ('BRK.B' → 'BRK-B' is
    done later by the provider), fold share-class duplicates, drop blanks."""
    out = frame.copy()
    out["ticker"] = out["ticker"].astype(str).str.strip().str.upper()
    out = out[out["ticker"].str.len() > 0]
    out["ticker"] = out["ticker"].replace(SHARE_CLASS_ALIASES)
    out["name"] = out["name"].astype(str).str.strip()
    return out.drop_duplicates("ticker").reset_index(drop=True)[["ticker", "name"]]


def parse_nasdaq_json(payload: dict) -> pd.DataFrame:
    rows = _find_rows(payload)
    if not rows:
        raise ValueError("Nasdaq response has no constituent rows")
    frame = pd.DataFrame({"ticker": [r.get("symbol", "") for r in rows],
                          "name": [r.get("companyName") or r.get("name") or "" for r in rows]})
    return normalize(frame)


def parse_wikipedia_html(html: str) -> pd.DataFrame:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="constituents")
    if table is None:  # fall back to the first wikitable with a Ticker column
        table = next((t for t in soup.find_all("table", class_="wikitable")
                      if any(h.get_text(strip=True) in ("Ticker", "Symbol")
                             for h in t.find_all("th"))), None)
    if table is None:
        raise ValueError("No constituents table on the Wikipedia page")
    rows = table.find_all("tr")
    header = [c.get_text(strip=True) for c in rows[0].find_all(["th", "td"])]
    t_col = next(i for i, h in enumerate(header) if h in ("Ticker", "Symbol"))
    n_col = next((i for i, h in enumerate(header) if h in ("Company", "Security")), 0)
    records = []
    for row in rows[1:]:
        cells = [c.get_text(strip=True) for c in row.find_all(["th", "td"])]
        if len(cells) > max(t_col, n_col):
            records.append({"ticker": cells[t_col], "name": cells[n_col]})
    return normalize(pd.DataFrame(records, columns=["ticker", "name"]))


def check_size(frame: pd.DataFrame, source: str) -> pd.DataFrame:
    """A Nasdaq-100 list is ~100 companies; anything far off is a parse error."""
    if not 90 <= len(frame) <= 105:
        raise ValueError(f"{source} returned {len(frame)} companies, expected ~100")
    return frame


# ---------------------------------------------------------------------------
# Fetching + cache
# ---------------------------------------------------------------------------


def _cache_path():
    return config.SNAPSHOT_DIR / "NASDAQ" / "nasdaq100.json"


def _save(members: Members) -> None:
    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"source": members.source, "as_of": members.as_of,
                                "members": members.frame.to_dict("records")},
                               ensure_ascii=False, indent=1), encoding="utf-8")


def load_cached() -> Members | None:
    path = _cache_path()
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return Members(pd.DataFrame(data["members"]), f"cache ({data['source']})", data["as_of"])


def fetch_nasdaq100() -> Members:
    """Current Nasdaq-100 members; raises only if every source and the cache fail."""
    import requests

    today = pd.Timestamp.today().date().isoformat()
    errors = []
    try:
        r = requests.get(NASDAQ_API_URL, timeout=_TIMEOUT,
                         headers={"User-Agent": _BROWSER_UA, "Accept": "application/json"})
        r.raise_for_status()
        members = Members(check_size(parse_nasdaq_json(r.json()), "Nasdaq"), "Nasdaq", today)
        _save(members)
        return members
    except Exception as err:  # noqa: BLE001
        errors.append(f"Nasdaq: {type(err).__name__}: {err}"[:160])
    try:
        r = requests.get(WIKIPEDIA_URL, timeout=_TIMEOUT, headers={"User-Agent": _WIKI_UA})
        r.raise_for_status()
        members = Members(check_size(parse_wikipedia_html(r.text), "Wikipedia"), "Wikipedia", today)
        _save(members)
        return members
    except Exception as err:  # noqa: BLE001
        errors.append(f"Wikipedia: {type(err).__name__}: {err}"[:160])
    cached = load_cached()
    if cached is not None:
        return cached
    raise ConnectionError("Nasdaq-100 list unavailable — " + " | ".join(errors))
